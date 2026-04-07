#!/usr/bin/env python3
"""Attach codon sequences conservatively to one finalized call table."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.detection.codon_extract import extract_call_codons  # noqa: E402
from homorepeat.io.fasta_io import read_fasta  # noqa: E402
from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, validate_call_row  # noqa: E402
from homorepeat.io.tsv_io import ContractError, read_tsv, write_tsv  # noqa: E402
from homorepeat.contracts.warnings import WARNING_FIELDNAMES, build_warning_row  # noqa: E402


CALLS_REQUIRED = [
    "call_id",
    "method",
    "genome_id",
    "taxon_id",
    "sequence_id",
    "protein_id",
    "start",
    "end",
    "length",
    "repeat_residue",
    "repeat_count",
    "non_repeat_count",
    "purity",
    "aa_sequence",
]
SEQUENCES_REQUIRED = [
    "sequence_id",
    "genome_id",
    "sequence_name",
    "sequence_length",
    "sequence_path",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls-tsv", required=True, help="Path to one finalized call table")
    parser.add_argument("--sequences-tsv", required=True, help="Path to canonical sequences.tsv")
    parser.add_argument("--cds-fasta", required=True, help="Path to canonical normalized cds.fna")
    parser.add_argument("--outdir", required=True, help="Output directory for codon-enriched artifacts")
    parser.add_argument("--warning-out", help="Optional explicit warning artifact path")
    parser.add_argument("--log-file", help="Reserved log file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    calls_path = Path(args.calls_tsv)
    output_calls_path = outdir / calls_path.name
    warning_path = (
        Path(args.warning_out)
        if args.warning_out
        else outdir / f"{calls_path.stem}_codon_warnings.tsv"
    )

    call_rows = read_tsv(calls_path, required_columns=CALLS_REQUIRED)
    sequence_rows = read_tsv(args.sequences_tsv, required_columns=SEQUENCES_REQUIRED)
    cds_records = dict(read_fasta(args.cds_fasta))

    sequence_rows_by_id = {row.get("sequence_id", ""): row for row in sequence_rows}
    enriched_rows: list[dict[str, object]] = []
    warning_rows: list[dict[str, object]] = []

    for row in call_rows:
        output_row = {field: row.get(field, "") for field in CALL_FIELDNAMES}
        output_row["codon_sequence"] = ""
        output_row["codon_metric_name"] = ""
        output_row["codon_metric_value"] = ""

        sequence_id = str(row.get("sequence_id", ""))
        sequence_row = sequence_rows_by_id.get(sequence_id)
        if sequence_row is None:
            warning_rows.append(
                build_warning_row(
                    "codon_slice_failed",
                    "call",
                    "No canonical CDS row was found for the call sequence_id",
                    genome_id=row.get("genome_id", ""),
                    sequence_id=sequence_id,
                    protein_id=row.get("protein_id", ""),
                    source_file=str(calls_path.resolve()),
                )
            )
            validate_call_row(output_row)
            enriched_rows.append(output_row)
            continue

        cds_sequence = cds_records.get(sequence_id)
        if cds_sequence is None:
            warning_rows.append(
                build_warning_row(
                    "codon_slice_failed",
                    "call",
                    "Normalized CDS FASTA is missing the call sequence_id",
                    genome_id=row.get("genome_id", ""),
                    sequence_id=sequence_id,
                    protein_id=row.get("protein_id", ""),
                    source_file=str(Path(args.cds_fasta).resolve()),
                )
            )
            validate_call_row(output_row)
            enriched_rows.append(output_row)
            continue

        result = extract_call_codons(
            cds_sequence,
            aa_start=int(row.get("start", 0)),
            aa_end=int(row.get("end", 0)),
            aa_sequence=str(row.get("aa_sequence", "")),
            translation_table=sequence_row.get("translation_table", "1"),
        )
        if result.accepted:
            output_row["codon_sequence"] = result.codon_sequence
        else:
            warning_rows.append(
                build_warning_row(
                    "codon_slice_failed",
                    "call",
                    result.warning_message,
                    genome_id=row.get("genome_id", ""),
                    sequence_id=sequence_id,
                    protein_id=row.get("protein_id", ""),
                    assembly_accession=sequence_row.get("assembly_accession", ""),
                    source_file=str(Path(args.cds_fasta).resolve()),
                    source_record_id=sequence_row.get("source_record_id", ""),
                )
            )

        validate_call_row(output_row)
        enriched_rows.append(output_row)

    write_tsv(output_calls_path, enriched_rows, fieldnames=CALL_FIELDNAMES)
    write_tsv(warning_path, warning_rows, fieldnames=WARNING_FIELDNAMES)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
