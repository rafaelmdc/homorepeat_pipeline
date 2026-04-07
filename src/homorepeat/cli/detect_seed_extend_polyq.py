#!/usr/bin/env python3
"""Detect long polyQ tracts with the seed-extend method from canonical protein inputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, build_call_row  # noqa: E402
from homorepeat.contracts.run_params import write_run_params  # noqa: E402
from homorepeat.detection.detect_seed_extend_polyq import find_seed_extend_polyq_tracts  # noqa: E402
from homorepeat.io.fasta_io import read_fasta  # noqa: E402
from homorepeat.io.tsv_io import ContractError, read_tsv, write_tsv  # noqa: E402


PROTEINS_REQUIRED = [
    "protein_id",
    "sequence_id",
    "genome_id",
    "protein_name",
    "protein_length",
    "protein_path",
    "taxon_id",
]

METHOD_NAME = "seed_extend_polyq"
REPEAT_RESIDUE = "Q"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proteins-tsv", required=True, help="Path to canonical proteins.tsv")
    parser.add_argument("--proteins-fasta", required=True, help="Path to canonical proteins.faa")
    parser.add_argument(
        "--repeat-residue",
        default=REPEAT_RESIDUE,
        help="Target amino-acid residue. Only Q is currently supported.",
    )
    parser.add_argument("--outdir", required=True, help="Output directory for seed-extend polyQ artifacts")
    parser.add_argument("--seed-window-size", type=int, default=8, help="Strict seed window size")
    parser.add_argument("--seed-min-q-count", type=int, default=6, help="Minimum Q count in a seed window")
    parser.add_argument("--extend-window-size", type=int, default=12, help="Looser extend window size")
    parser.add_argument("--extend-min-q-count", type=int, default=8, help="Minimum Q count in an extend window")
    parser.add_argument("--min-total-length", type=int, default=10, help="Minimum final tract length")
    parser.add_argument("--log-file", help="Reserved log file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repeat_residue = args.repeat_residue.strip().upper()
    if repeat_residue != REPEAT_RESIDUE:
        raise ContractError(f"--repeat-residue must be {REPEAT_RESIDUE!r} for {METHOD_NAME}: {args.repeat_residue!r}")

    proteins_rows = read_tsv(args.proteins_tsv, required_columns=PROTEINS_REQUIRED)
    protein_records = dict(read_fasta(args.proteins_fasta))
    outdir = Path(args.outdir)

    window_definition = (
        f"seed:{repeat_residue}{args.seed_min_q_count}/{args.seed_window_size}"
        f"|extend:{repeat_residue}{args.extend_min_q_count}/{args.extend_window_size}"
    )
    merge_rule = "seed_extend_connected_windows"

    call_rows: list[dict[str, object]] = []
    for row in proteins_rows:
        protein_id = row.get("protein_id", "")
        protein_sequence = protein_records.get(protein_id)
        if protein_sequence is None:
            raise ContractError(f"Protein FASTA is missing protein_id {protein_id}")

        try:
            tracts = find_seed_extend_polyq_tracts(
                protein_sequence,
                seed_window_size=args.seed_window_size,
                seed_min_q_count=args.seed_min_q_count,
                extend_window_size=args.extend_window_size,
                extend_min_q_count=args.extend_min_q_count,
                min_total_length=args.min_total_length,
            )
        except ValueError as exc:
            raise ContractError(str(exc)) from exc

        for tract in tracts:
            call_rows.append(
                build_call_row(
                    method=METHOD_NAME,
                    genome_id=row.get("genome_id", ""),
                    taxon_id=row.get("taxon_id", ""),
                    sequence_id=row.get("sequence_id", ""),
                    protein_id=protein_id,
                    repeat_residue=repeat_residue,
                    start=tract.start,
                    end=tract.end,
                    aa_sequence=tract.aa_sequence,
                    source_file=row.get("protein_path", ""),
                    window_definition=window_definition,
                    merge_rule=merge_rule,
                )
            )

    call_rows.sort(
        key=lambda row: (
            str(row.get("protein_id", "")),
            int(row.get("start", 0)),
            str(row.get("call_id", "")),
        )
    )
    write_tsv(outdir / f"{METHOD_NAME}_calls.tsv", call_rows, fieldnames=CALL_FIELDNAMES)
    write_run_params(
        outdir / "run_params.tsv",
        METHOD_NAME,
        {
            "repeat_residue": repeat_residue,
            "seed_window_size": args.seed_window_size,
            "seed_min_q_count": args.seed_min_q_count,
            "extend_window_size": args.extend_window_size,
            "extend_min_q_count": args.extend_min_q_count,
            "min_total_length": args.min_total_length,
        },
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
