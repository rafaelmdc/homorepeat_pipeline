#!/usr/bin/env python3
"""Attach codon sequences conservatively to one finalized call table."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.detection.codon_extract import (  # noqa: E402
    CODON_USAGE_FIELDNAMES,
    build_codon_usage_rows,
    extract_call_codons,
)
from homorepeat.io.fasta_io import iter_fasta  # noqa: E402
from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, validate_call_row  # noqa: E402
from homorepeat.io.tsv_io import ContractError, iter_tsv, open_tsv_writer, write_tsv  # noqa: E402
from homorepeat.contracts.warnings import WARNING_FIELDNAMES, build_warning_row  # noqa: E402
from homorepeat.runtime.stage_status import build_stage_status, write_stage_status  # noqa: E402


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
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls-tsv", required=True, help="Path to one finalized call table")
    parser.add_argument("--sequences-tsv", required=True, help="Path to canonical sequences.tsv")
    parser.add_argument("--cds-fasta", required=True, help="Path to canonical normalized cds.fna")
    parser.add_argument("--outdir", required=True, help="Output directory for codon-enriched artifacts")
    parser.add_argument("--batch-id", default="", help="Optional batch identifier for stage-status output")
    parser.add_argument("--method", default="", help="Optional method name for stage-status output")
    parser.add_argument("--repeat-residue", default="", help="Optional repeat residue for stage-status output")
    parser.add_argument("--warning-out", help="Optional explicit warning artifact path")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument("--status-out", help="Optional stage-status JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        _run(args)
    except Exception as exc:
        _write_failure_artifacts(args, str(exc))
        raise
    _write_status(args, status="success")
    return 0


def _write_failure_artifacts(args: argparse.Namespace, message: str) -> None:
    try:
        _write_failed_outputs(args)
    except Exception:
        pass
    try:
        _write_status(args, status="failed", message=message)
    except Exception:
        pass


def _run(args: argparse.Namespace) -> None:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    calls_path = Path(args.calls_tsv)
    output_calls_path = outdir / calls_path.name
    warning_path = (
        Path(args.warning_out)
        if args.warning_out
        else outdir / f"{calls_path.stem}_codon_warnings.tsv"
    )
    codon_usage_path = outdir / f"{calls_path.stem}_codon_usage.tsv"

    needed_sequence_ids = {
        row.get("sequence_id", "")
        for row in iter_tsv(calls_path, required_columns=CALLS_REQUIRED)
        if row.get("sequence_id", "")
    }
    sequence_rows_by_id = {
        row.get("sequence_id", ""): row
        for row in iter_tsv(args.sequences_tsv, required_columns=SEQUENCES_REQUIRED)
        if row.get("sequence_id", "") in needed_sequence_ids
    }
    cds_records = {
        sequence_id: cds_sequence
        for sequence_id, cds_sequence in iter_fasta(args.cds_fasta)
        if sequence_id in needed_sequence_ids
    }

    with (
        open_tsv_writer(output_calls_path, fieldnames=CALL_FIELDNAMES) as calls_writer,
        open_tsv_writer(warning_path, fieldnames=WARNING_FIELDNAMES) as warning_writer,
        open_tsv_writer(codon_usage_path, fieldnames=CODON_USAGE_FIELDNAMES) as codon_usage_writer,
    ):
        for row in iter_tsv(calls_path, required_columns=CALLS_REQUIRED):
            output_row = {field: row.get(field, "") for field in CALL_FIELDNAMES}
            output_row["codon_sequence"] = ""
            output_row["codon_metric_name"] = ""
            output_row["codon_metric_value"] = ""

            sequence_id = str(row.get("sequence_id", ""))
            sequence_row = sequence_rows_by_id.get(sequence_id)
            if sequence_row is None:
                warning_writer.write_row(
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
                calls_writer.write_row(output_row)
                continue

            cds_sequence = cds_records.get(sequence_id)
            if cds_sequence is None:
                warning_writer.write_row(
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
                calls_writer.write_row(output_row)
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
                codon_usage_writer.write_rows(
                    build_codon_usage_rows(
                        output_row,
                        translation_table=sequence_row.get("translation_table", "1"),
                    )
                )
            else:
                warning_writer.write_row(
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
            calls_writer.write_row(output_row)


def _write_failed_outputs(args: argparse.Namespace) -> None:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    calls_path = Path(args.calls_tsv)
    output_calls_path = outdir / calls_path.name
    warning_path = Path(args.warning_out) if args.warning_out else outdir / f"{calls_path.stem}_codon_warnings.tsv"
    codon_usage_path = outdir / f"{calls_path.stem}_codon_usage.tsv"
    write_tsv(output_calls_path, [], fieldnames=CALL_FIELDNAMES)
    write_tsv(warning_path, [], fieldnames=WARNING_FIELDNAMES)
    write_tsv(codon_usage_path, [], fieldnames=CODON_USAGE_FIELDNAMES)


def _write_status(args: argparse.Namespace, *, status: str, message: str = "") -> None:
    if not args.status_out:
        return
    write_stage_status(
        args.status_out,
        build_stage_status(
            stage="finalize",
            status=status,
            batch_id=args.batch_id,
            method=args.method,
            repeat_residue=args.repeat_residue,
            message=message,
        ),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
