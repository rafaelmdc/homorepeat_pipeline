#!/usr/bin/env python3
"""Translate normalized CDS rows into retained canonical protein inputs."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from homorepeat.acquisition.acquisition_validation import build_acquisition_validation, write_validation_json  # noqa: E402
from homorepeat.io.fasta_io import read_fasta, write_fasta  # noqa: E402
from homorepeat.core.ids import stable_id  # noqa: E402
from homorepeat.acquisition.translation import translate_cds as translate_sequence  # noqa: E402
from homorepeat.io.tsv_io import ContractError, read_tsv, write_tsv  # noqa: E402
from homorepeat.contracts.warnings import WARNING_FIELDNAMES, build_warning_row  # noqa: E402


SEQUENCES_REQUIRED = ["sequence_id", "genome_id", "sequence_name", "sequence_length", "sequence_path"]
PROTEINS_FIELDNAMES = [
    "protein_id",
    "sequence_id",
    "genome_id",
    "protein_name",
    "protein_length",
    "protein_path",
    "gene_symbol",
    "translation_method",
    "translation_status",
    "assembly_accession",
    "taxon_id",
    "gene_group",
    "protein_external_id",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences-tsv", required=True, help="Path to normalized sequences.tsv")
    parser.add_argument("--cds-fasta", required=True, help="Path to normalized cds.fna")
    parser.add_argument("--batch-id", required=True, help="Operational batch identifier")
    parser.add_argument("--outdir", required=True, help="Batch-local normalized output directory")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument("--warning-out", help="Optional explicit warning artifact path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outdir = Path(args.outdir)
    warning_path = Path(args.warning_out) if args.warning_out else outdir / "normalization_warnings.tsv"
    protein_fasta_path = outdir / "proteins.faa"
    proteins_tsv_path = outdir / "proteins.tsv"

    sequences_rows = read_tsv(args.sequences_tsv, required_columns=SEQUENCES_REQUIRED)
    cds_records = dict(read_fasta(args.cds_fasta))
    existing_warning_rows = read_tsv(warning_path) if warning_path.is_file() else []
    warning_rows = list(existing_warning_rows)

    translated_candidates: list[dict[str, object]] = []
    for row in sequences_rows:
        sequence_id = row.get("sequence_id", "")
        cds_sequence = cds_records.get(sequence_id)
        if cds_sequence is None:
            raise ContractError(f"Normalized CDS FASTA is missing sequence_id {sequence_id}")

        if row.get("partial_status", "") == "partial":
            warning_rows.append(
                build_warning_row(
                    "partial_cds",
                    "sequence",
                    "CDS is marked partial and is rejected before translation",
                    batch_id=args.batch_id,
                    genome_id=row.get("genome_id", ""),
                    sequence_id=sequence_id,
                    assembly_accession=row.get("assembly_accession", ""),
                    source_record_id=row.get("source_record_id", ""),
                )
            )
            continue

        result = translate_sequence(cds_sequence, row.get("translation_table", "1"))
        if not result.accepted:
            warning_rows.append(
                build_warning_row(
                    result.warning_code,
                    "sequence",
                    result.warning_message,
                    batch_id=args.batch_id,
                    genome_id=row.get("genome_id", ""),
                    sequence_id=sequence_id,
                    assembly_accession=row.get("assembly_accession", ""),
                    source_record_id=row.get("source_record_id", ""),
                )
            )
            continue

        protein_id = stable_id("prot", sequence_id)
        translated_candidates.append(
            {
                "protein_id": protein_id,
                "sequence_id": sequence_id,
                "genome_id": row.get("genome_id", ""),
                "protein_name": row.get("protein_external_id", "") or row.get("sequence_name", ""),
                "protein_length": len(result.protein_sequence),
                "protein_path": str(protein_fasta_path.resolve()),
                "gene_symbol": row.get("gene_symbol", ""),
                "translation_method": "local_cds_translation",
                "translation_status": "translated",
                "assembly_accession": row.get("assembly_accession", ""),
                "taxon_id": row.get("taxon_id", ""),
                "gene_group": row.get("gene_group", "") or row.get("gene_symbol", "") or sequence_id,
                "protein_external_id": row.get("protein_external_id", ""),
                "_protein_sequence": result.protein_sequence,
            }
        )

    retained_rows = retain_one_isoform_per_gene(translated_candidates)
    write_tsv(
        proteins_tsv_path,
        [{field: row.get(field, "") for field in PROTEINS_FIELDNAMES} for row in retained_rows],
        fieldnames=PROTEINS_FIELDNAMES,
    )
    write_fasta(protein_fasta_path, [(row["protein_id"], row["_protein_sequence"]) for row in retained_rows])
    write_tsv(warning_path, warning_rows, fieldnames=WARNING_FIELDNAMES)

    genomes_rows = read_tsv(outdir / "genomes.tsv") if (outdir / "genomes.tsv").is_file() else []
    download_manifest_rows = (
        read_tsv(outdir / "download_manifest.tsv") if (outdir / "download_manifest.tsv").is_file() else []
    )
    validation_payload = build_acquisition_validation(
        scope="batch",
        batch_id=args.batch_id,
        genomes_rows=genomes_rows,
        sequences_rows=sequences_rows,
        proteins_rows=[{field: str(row.get(field, "")) for field in PROTEINS_FIELDNAMES} for row in retained_rows],
        warning_rows=warning_rows,
        download_manifest_rows=download_manifest_rows,
    )
    write_validation_json(outdir / "acquisition_validation.json", validation_payload)
    return 0


def retain_one_isoform_per_gene(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Keep the longest translated protein per genome/gene group."""

    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = (str(row.get("genome_id", "")), str(row.get("gene_group", "")))
        grouped[key].append(row)

    retained: list[dict[str, object]] = []
    for _, candidates in sorted(grouped.items()):
        winner = sorted(
            candidates,
            key=lambda row: (-int(row.get("protein_length", 0)), str(row.get("protein_id", ""))),
        )[0]
        retained.append(winner)
    return sorted(retained, key=lambda row: str(row.get("protein_id", "")))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
