#!/usr/bin/env python3
"""Merge validated batch-local acquisition outputs into canonical merged artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.acquisition.acquisition_validation import build_acquisition_validation, write_validation_json  # noqa: E402
from homorepeat.io.fasta_io import read_fasta, write_fasta  # noqa: E402
from homorepeat.io.tsv_io import ContractError, read_tsv, write_tsv  # noqa: E402
from homorepeat.contracts.warnings import WARNING_FIELDNAMES  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-inputs",
        required=True,
        action="append",
        help="Batch-local normalized directory. Repeat for multiple batches.",
    )
    parser.add_argument("--outdir", required=True, help="Merged acquisition output directory")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument(
        "--strict-taxonomy-merge",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Hard-fail if two taxonomy rows with the same taxon_id disagree materially",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch_dirs = sorted({str(Path(path).resolve()) for path in args.batch_inputs})
    if not batch_dirs:
        raise ContractError("No batch inputs were provided")

    merged_genomes: list[dict[str, str]] = []
    merged_sequences: list[dict[str, str]] = []
    merged_proteins: list[dict[str, str]] = []
    merged_warnings: list[dict[str, str]] = []
    merged_manifest: list[dict[str, str]] = []
    merged_cds_records: list[tuple[str, str]] = []
    merged_protein_records: list[tuple[str, str]] = []
    taxonomy_by_id: dict[str, dict[str, str]] = {}

    for batch_dir_text in batch_dirs:
        batch_dir = Path(batch_dir_text)
        merged_genomes.extend(read_tsv(batch_dir / "genomes.tsv"))
        merged_sequences.extend(read_tsv(batch_dir / "sequences.tsv"))
        merged_proteins.extend(read_tsv(batch_dir / "proteins.tsv"))
        if (batch_dir / "normalization_warnings.tsv").is_file():
            merged_warnings.extend(read_tsv(batch_dir / "normalization_warnings.tsv"))
        if (batch_dir / "download_manifest.tsv").is_file():
            merged_manifest.extend(read_tsv(batch_dir / "download_manifest.tsv"))
        if (batch_dir / "cds.fna").is_file():
            merged_cds_records.extend(read_fasta(batch_dir / "cds.fna"))
        if (batch_dir / "proteins.faa").is_file():
            merged_protein_records.extend(read_fasta(batch_dir / "proteins.faa"))

        for taxonomy_row in read_tsv(batch_dir / "taxonomy.tsv"):
            taxon_id = taxonomy_row.get("taxon_id", "")
            if not taxon_id:
                continue
            existing = taxonomy_by_id.get(taxon_id)
            if existing is None:
                taxonomy_by_id[taxon_id] = taxonomy_row
                continue
            if args.strict_taxonomy_merge and materially_differs(existing, taxonomy_row):
                raise ContractError(f"Conflicting taxonomy rows found for taxon_id {taxon_id}")

    _assert_unique_key(merged_genomes, "genome_id", "genomes.tsv")
    _assert_unique_key(merged_sequences, "sequence_id", "sequences.tsv")
    _assert_unique_key(merged_proteins, "protein_id", "proteins.tsv")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    write_tsv(outdir / "genomes.tsv", merged_genomes, fieldnames=list(merged_genomes[0].keys()) if merged_genomes else [])
    write_tsv(
        outdir / "taxonomy.tsv",
        [taxonomy_by_id[key] for key in sorted(taxonomy_by_id)],
        fieldnames=list(next(iter(taxonomy_by_id.values())).keys()) if taxonomy_by_id else [],
    )
    write_tsv(
        outdir / "sequences.tsv",
        merged_sequences,
        fieldnames=list(merged_sequences[0].keys()) if merged_sequences else [],
    )
    write_tsv(
        outdir / "proteins.tsv",
        merged_proteins,
        fieldnames=list(merged_proteins[0].keys()) if merged_proteins else [],
    )
    write_tsv(outdir / "download_manifest.tsv", merged_manifest, fieldnames=list(merged_manifest[0].keys()) if merged_manifest else [])
    write_tsv(outdir / "normalization_warnings.tsv", merged_warnings, fieldnames=WARNING_FIELDNAMES)
    write_fasta(outdir / "cds.fna", merged_cds_records)
    write_fasta(outdir / "proteins.faa", merged_protein_records)

    validation_payload = build_acquisition_validation(
        scope="merged",
        batch_id=None,
        genomes_rows=merged_genomes,
        sequences_rows=merged_sequences,
        proteins_rows=merged_proteins,
        warning_rows=merged_warnings,
        download_manifest_rows=merged_manifest,
    )
    write_validation_json(outdir / "acquisition_validation.json", validation_payload)
    return 0


def materially_differs(left: dict[str, str], right: dict[str, str]) -> bool:
    """Return whether two taxonomy rows disagree on stable values."""

    keys = {"taxon_name", "parent_taxon_id", "rank", "source"}
    return any((left.get(key, "") or "") != (right.get(key, "") or "") for key in keys)


def _assert_unique_key(rows: list[dict[str, str]], key_name: str, label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        key = row.get(key_name, "")
        if not key:
            continue
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    if duplicates:
        duplicate_text = ", ".join(sorted(duplicates))
        raise ContractError(f"{label} contains duplicate {key_name} values: {duplicate_text}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
