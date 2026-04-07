#!/usr/bin/env python3
"""Download one batch of NCBI annotation-focused genome packages."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.acquisition.ncbi_datasets import (  # noqa: E402
    download_genome_batch,
    rehydrate_package,
    unzip_package,
)
from homorepeat.acquisition.package_layout import find_package_root, load_assembly_report  # noqa: E402
from homorepeat.io.tsv_io import ContractError, read_tsv, write_lines, write_tsv  # noqa: E402


SELECTED_BATCHES_REQUIRED = ["batch_id", "assembly_accession"]
DOWNLOAD_MANIFEST_FIELDNAMES = [
    "batch_id",
    "assembly_accession",
    "download_status",
    "package_mode",
    "download_path",
    "rehydrated_path",
    "checksum",
    "file_size_bytes",
    "download_started_at",
    "download_finished_at",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-manifest", required=True, help="Path to selected_batches.tsv")
    parser.add_argument("--batch-id", required=True, help="Operational batch identifier")
    parser.add_argument("--outdir", required=True, help="Batch-local raw output directory")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument("--api-key", help="NCBI API key")
    parser.add_argument("--cache-dir", help="Optional cache directory for downloaded archives")
    parser.add_argument("--dehydrated", action="store_true", help="Use dehydrated package mode")
    parser.add_argument("--rehydrate", action="store_true", help="Run datasets rehydrate after extraction")
    parser.add_argument(
        "--rehydrate-workers",
        type=int,
        help="Optional max worker count for datasets rehydrate",
    )
    parser.add_argument(
        "--datasets-bin",
        default="datasets",
        help="Path to the NCBI datasets executable",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch_rows = read_tsv(args.batch_manifest, required_columns=SELECTED_BATCHES_REQUIRED)
    selected_rows = [row for row in batch_rows if row.get("batch_id", "") == args.batch_id]
    if not selected_rows:
        raise ContractError(f"Batch {args.batch_id} has zero matching rows in {args.batch_manifest}")

    accessions = [row.get("assembly_accession", "") for row in selected_rows]
    if any(not accession for accession in accessions):
        raise ContractError(f"Batch {args.batch_id} contains an empty assembly accession")
    if len(set(accessions)) != len(accessions):
        raise ContractError(f"Batch {args.batch_id} contains duplicate assembly accessions")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    accessions_file = outdir / "selected_accessions.txt"
    write_lines(accessions_file, accessions)

    archive_dir = Path(args.cache_dir) if args.cache_dir else outdir
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{args.batch_id}_ncbi_dataset.zip"
    package_extract_dir = outdir / "ncbi_package"

    download_genome_batch(
        accessions_file,
        archive_path,
        api_key=args.api_key,
        datasets_bin=args.datasets_bin,
        dehydrated=args.dehydrated,
    )
    unzip_package(archive_path, package_extract_dir)
    if args.rehydrate:
        rehydrate_package(
            package_extract_dir,
            api_key=args.api_key,
            datasets_bin=args.datasets_bin,
            max_workers=args.rehydrate_workers,
        )

    package_root = find_package_root(package_extract_dir)
    downloaded_records = load_assembly_report(package_root)
    downloaded_accessions = {record.get("accession", "") for record in downloaded_records}

    manifest_rows: list[dict[str, object]] = []
    success_status = "rehydrated" if args.rehydrate else "downloaded"
    package_mode = "dehydrated" if args.dehydrated else "direct_zip"
    for accession in accessions:
        if accession in downloaded_accessions:
            manifest_rows.append(
                {
                    "batch_id": args.batch_id,
                    "assembly_accession": accession,
                    "download_status": success_status,
                    "package_mode": package_mode,
                    "download_path": str(archive_path.resolve()),
                    "rehydrated_path": str(package_root.resolve()) if args.rehydrate else "",
                    "checksum": "",
                    "file_size_bytes": archive_path.stat().st_size,
                    "download_started_at": "",
                    "download_finished_at": "",
                    "notes": "",
                }
            )
            continue
        manifest_rows.append(
            {
                "batch_id": args.batch_id,
                "assembly_accession": accession,
                "download_status": "failed",
                "package_mode": package_mode,
                "download_path": str(archive_path.resolve()),
                "rehydrated_path": "",
                "checksum": "",
                "file_size_bytes": archive_path.stat().st_size if archive_path.exists() else "",
                "download_started_at": "",
                "download_finished_at": "",
                "notes": "selected accession missing from downloaded package",
            }
        )

    write_tsv(outdir / "download_manifest.tsv", manifest_rows, fieldnames=DOWNLOAD_MANIFEST_FIELDNAMES)
    if not any(row["download_status"] in {"downloaded", "rehydrated"} for row in manifest_rows):
        raise ContractError(f"Batch {args.batch_id} produced no successful package records")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
