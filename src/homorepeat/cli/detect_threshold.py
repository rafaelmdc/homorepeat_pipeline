#!/usr/bin/env python3
"""Detect threshold-method repeat tracts from canonical protein inputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.detection.detect_threshold import find_threshold_tracts  # noqa: E402
from homorepeat.io.fasta_io import read_fasta  # noqa: E402
from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, build_call_row  # noqa: E402
from homorepeat.contracts.run_params import write_run_params  # noqa: E402
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proteins-tsv", required=True, help="Path to canonical proteins.tsv")
    parser.add_argument("--proteins-fasta", required=True, help="Path to canonical proteins.faa")
    parser.add_argument("--repeat-residue", required=True, help="Target amino-acid residue")
    parser.add_argument("--outdir", required=True, help="Output directory for threshold detection artifacts")
    parser.add_argument("--window-size", type=int, default=8, help="Sliding window size")
    parser.add_argument(
        "--min-target-count",
        type=int,
        default=6,
        help="Minimum target count inside a qualifying sliding window",
    )
    parser.add_argument("--log-file", help="Reserved log file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repeat_residue = args.repeat_residue.strip().upper()
    if len(repeat_residue) != 1:
        raise ContractError(f"--repeat-residue must be one amino-acid symbol: {args.repeat_residue!r}")
    if args.window_size < 1:
        raise ContractError("--window-size must be positive")
    if args.min_target_count < 1 or args.min_target_count > args.window_size:
        raise ContractError("--min-target-count must be between 1 and --window-size")

    proteins_rows = read_tsv(args.proteins_tsv, required_columns=PROTEINS_REQUIRED)
    protein_records = dict(read_fasta(args.proteins_fasta))
    outdir = Path(args.outdir)

    window_definition = f"{repeat_residue}{args.min_target_count}/{args.window_size}"
    merge_rule = "merge_adjacent_or_overlap"

    call_rows: list[dict[str, object]] = []
    for row in proteins_rows:
        protein_id = row.get("protein_id", "")
        protein_sequence = protein_records.get(protein_id)
        if protein_sequence is None:
            raise ContractError(f"Protein FASTA is missing protein_id {protein_id}")

        for tract in find_threshold_tracts(
            protein_sequence,
            repeat_residue,
            window_size=args.window_size,
            min_target_count=args.min_target_count,
        ):
            call_rows.append(
                build_call_row(
                    method="threshold",
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
    write_tsv(outdir / "threshold_calls.tsv", call_rows, fieldnames=CALL_FIELDNAMES)
    write_run_params(
        outdir / "run_params.tsv",
        "threshold",
        {
            "repeat_residue": repeat_residue,
            "window_size": args.window_size,
            "min_target_count": args.min_target_count,
        },
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
