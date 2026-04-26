#!/usr/bin/env python3
"""Export compact repeat-call flanking context."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.contracts.publish_contract_v2 import REPEAT_CONTEXT_FIELDNAMES
from homorepeat.contracts.repeat_features import CALL_FIELDNAMES
from homorepeat.detection.repeat_context import (
    DEFAULT_AA_CONTEXT_WINDOW_SIZE,
    DEFAULT_NT_CONTEXT_WINDOW_SIZE,
    build_repeat_context_row,
)
from homorepeat.io.fasta_io import iter_fasta
from homorepeat.io.tsv_io import ContractError, iter_tsv, open_tsv_writer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat-calls-tsv", required=True, help="Path to canonical repeat_calls.tsv")
    parser.add_argument("--batch-dir", action="append", default=[], help="Path to one staged batch context directory")
    parser.add_argument("--outdir", required=True, help="Output directory for repeat_context.tsv")
    parser.add_argument("--aa-context-window-size", type=int, default=DEFAULT_AA_CONTEXT_WINDOW_SIZE)
    parser.add_argument("--nt-context-window-size", type=int, default=DEFAULT_NT_CONTEXT_WINDOW_SIZE)
    parser.add_argument("--log-file", help="Reserved log file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.batch_dir:
        raise ContractError("At least one --batch-dir input is required")
    if args.aa_context_window_size < 0:
        raise ContractError("--aa-context-window-size must be non-negative")
    if args.nt_context_window_size < 0:
        raise ContractError("--nt-context-window-size must be non-negative")

    calls_path = Path(args.repeat_calls_tsv)
    needed_sequence_ids, needed_protein_ids = _read_needed_ids(calls_path)
    cds_by_sequence_id = _read_needed_fasta_records(
        [Path(path) / "cds.fna" for path in args.batch_dir],
        needed_sequence_ids,
        label="sequence_id",
    )
    protein_by_id = _read_needed_fasta_records(
        [Path(path) / "proteins.faa" for path in args.batch_dir],
        needed_protein_ids,
        label="protein_id",
    )

    missing_sequence_ids = sorted(needed_sequence_ids - set(cds_by_sequence_id))
    if missing_sequence_ids:
        missing_ids = ", ".join(missing_sequence_ids[:5])
        raise ContractError(f"repeat_calls.tsv references missing CDS sequence_id values: {missing_ids}")
    missing_protein_ids = sorted(needed_protein_ids - set(protein_by_id))
    if missing_protein_ids:
        missing_ids = ", ".join(missing_protein_ids[:5])
        raise ContractError(f"repeat_calls.tsv references missing protein_id values: {missing_ids}")

    outdir = Path(args.outdir)
    with open_tsv_writer(outdir / "repeat_context.tsv", fieldnames=REPEAT_CONTEXT_FIELDNAMES) as writer:
        seen_call_ids: set[str] = set()
        for call_row in iter_tsv(calls_path, required_columns=CALL_FIELDNAMES):
            call_id = call_row.get("call_id", "")
            if call_id in seen_call_ids:
                raise ContractError(f"repeat_context.tsv would contain duplicate call_id {call_id}")
            seen_call_ids.add(call_id)
            writer.write_row(
                build_repeat_context_row(
                    call_row,
                    protein_sequence=protein_by_id[call_row.get("protein_id", "")],
                    cds_sequence=cds_by_sequence_id[call_row.get("sequence_id", "")],
                    aa_context_window_size=args.aa_context_window_size,
                    nt_context_window_size=args.nt_context_window_size,
                )
            )
    return 0


def _read_needed_ids(calls_path: Path) -> tuple[set[str], set[str]]:
    sequence_ids: set[str] = set()
    protein_ids: set[str] = set()
    for row in iter_tsv(calls_path, required_columns=CALL_FIELDNAMES):
        sequence_id = row.get("sequence_id", "")
        protein_id = row.get("protein_id", "")
        if not sequence_id:
            raise ContractError("repeat_calls.tsv contains an empty sequence_id")
        if not protein_id:
            raise ContractError("repeat_calls.tsv contains an empty protein_id")
        sequence_ids.add(sequence_id)
        protein_ids.add(protein_id)
    return sequence_ids, protein_ids


def _read_needed_fasta_records(paths: list[Path], needed_ids: set[str], *, label: str) -> dict[str, str]:
    records_by_id: dict[str, str] = {}
    for path in paths:
        for record_id, sequence in iter_fasta(path):
            if record_id not in needed_ids:
                continue
            if record_id in records_by_id:
                raise ContractError(f"Duplicate {label} FASTA record found for {record_id}")
            records_by_id[record_id] = sequence
    return records_by_id


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
