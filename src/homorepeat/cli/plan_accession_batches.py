#!/usr/bin/env python3
"""Plan deterministic acquisition batches from a plain accession list."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.acquisition.ncbi_datasets import resolve_download_accession  # noqa: E402
from homorepeat.io.tsv_io import ContractError, write_lines, write_tsv  # noqa: E402


ACCESSION_BATCH_FIELDNAMES = ["batch_id", "assembly_accession"]
ACCESSION_RESOLUTION_FIELDNAMES = [
    "requested_accession",
    "resolved_accession",
    "resolution_reason",
    "source_database",
    "current_accession",
    "paired_accession",
    "annotation_status",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--accessions-file",
        required=True,
        help="Path to a plain-text accession list, one accession per line",
    )
    parser.add_argument("--outdir", required=True, help="Output directory for planning artifacts")
    parser.add_argument(
        "--target-batch-size",
        type=int,
        default=100,
        help="Target number of accessions per operational batch",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        help="Optional maximum batch count before hard-failing",
    )
    parser.add_argument("--api-key", help="NCBI API key")
    parser.add_argument(
        "--datasets-bin",
        default="datasets",
        help="Path to the NCBI datasets executable",
    )
    parser.add_argument(
        "--resolve-accessions",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Resolve requested assembly accessions to the preferred downloadable accession before batching",
    )
    parser.add_argument("--log-file", help="Reserved log file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.target_batch_size < 1:
        raise ContractError("--target-batch-size must be positive")

    requested_accessions = load_accessions(args.accessions_file)
    if not requested_accessions:
        raise ContractError(f"No accession IDs were found in {args.accessions_file}")
    accessions, resolution_rows = resolve_accessions(
        requested_accessions,
        resolve_requested_accessions=args.resolve_accessions,
        api_key=args.api_key,
        datasets_bin=args.datasets_bin,
    )

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    batch_manifest_dir = outdir / "batch_manifests"
    batch_manifest_dir.mkdir(parents=True, exist_ok=True)

    write_lines(outdir / "selected_accessions.txt", accessions)
    write_tsv(
        outdir / "accession_resolution.tsv",
        resolution_rows,
        fieldnames=ACCESSION_RESOLUTION_FIELDNAMES,
    )

    all_batch_rows: list[dict[str, object]] = []
    batch_count = 0
    for start_index in range(0, len(accessions), args.target_batch_size):
        batch_count += 1
        if args.max_batches is not None and batch_count > args.max_batches:
            raise ContractError(
                f"Batch planning would create {batch_count} batches, exceeding --max-batches={args.max_batches}"
            )

        batch_id = f"batch_{batch_count:04d}"
        batch_accessions = accessions[start_index : start_index + args.target_batch_size]
        batch_rows = [
            {
                "batch_id": batch_id,
                "assembly_accession": accession,
            }
            for accession in batch_accessions
        ]
        all_batch_rows.extend(batch_rows)
        write_tsv(
            batch_manifest_dir / f"{batch_id}.tsv",
            batch_rows,
            fieldnames=ACCESSION_BATCH_FIELDNAMES,
        )

    write_tsv(outdir / "accession_batches.tsv", all_batch_rows, fieldnames=ACCESSION_BATCH_FIELDNAMES)
    return 0


def load_accessions(path: str | Path) -> list[str]:
    """Load one accession per non-empty, non-comment line."""

    ordered_accessions: list[str] = []
    seen: set[str] = set()
    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line in seen:
                continue
            ordered_accessions.append(line)
            seen.add(line)
    return ordered_accessions


def resolve_accessions(
    accessions: list[str],
    *,
    resolve_requested_accessions: bool,
    api_key: str | None,
    datasets_bin: str,
) -> tuple[list[str], list[dict[str, str]]]:
    resolution_rows: list[dict[str, str]] = []
    resolved_accessions: list[str] = []
    seen_resolved_accessions: set[str] = set()

    for accession in accessions:
        if resolve_requested_accessions:
            normalized_accession = accession.upper()
            if normalized_accession.startswith("GCF_"):
                resolution_row = {
                    "requested_accession": accession,
                    "resolved_accession": accession,
                    "resolution_reason": "kept_refseq_accession",
                    "source_database": "REFSEQ",
                    "current_accession": accession,
                    "paired_accession": "",
                    "annotation_status": "",
                }
            else:
                resolution_row = resolve_download_accession(
                    accession,
                    api_key=api_key,
                    datasets_bin=datasets_bin,
                )
        else:
            resolution_row = {
                "requested_accession": accession,
                "resolved_accession": accession,
                "resolution_reason": "resolution_disabled",
                "source_database": "",
                "current_accession": accession,
                "paired_accession": "",
                "annotation_status": "",
            }

        resolution_rows.append(resolution_row)
        resolved_accession = resolution_row["resolved_accession"] or accession
        if resolved_accession in seen_resolved_accessions:
            continue
        resolved_accessions.append(resolved_accession)
        seen_resolved_accessions.add(resolved_accession)

    return resolved_accessions, resolution_rows


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
