#!/usr/bin/env python3
"""Detect pure-method repeat tracts from canonical protein inputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.detection.detect_pure import find_pure_tracts  # noqa: E402
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
    parser.add_argument("--outdir", required=True, help="Output directory for pure detection artifacts")
    parser.add_argument("--min-repeat-count", type=int, default=6, help="Minimum target-residue count")
    parser.add_argument("--log-file", help="Reserved log file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repeat_residue = args.repeat_residue.strip().upper()
    if len(repeat_residue) != 1:
        raise ContractError(f"--repeat-residue must be one amino-acid symbol: {args.repeat_residue!r}")
    if args.min_repeat_count < 1:
        raise ContractError("--min-repeat-count must be positive")

    proteins_rows = read_tsv(args.proteins_tsv, required_columns=PROTEINS_REQUIRED)
    protein_records = dict(read_fasta(args.proteins_fasta))
    outdir = Path(args.outdir)

    call_rows: list[dict[str, object]] = []
    for row in proteins_rows:
        protein_id = row.get("protein_id", "")
        protein_sequence = protein_records.get(protein_id)
        if protein_sequence is None:
            raise ContractError(f"Protein FASTA is missing protein_id {protein_id}")

        for tract in find_pure_tracts(
            protein_sequence,
            repeat_residue,
            min_repeat_count=args.min_repeat_count,
        ):
            call_rows.append(
                build_call_row(
                    method="pure",
                    genome_id=row.get("genome_id", ""),
                    taxon_id=row.get("taxon_id", ""),
                    sequence_id=row.get("sequence_id", ""),
                    protein_id=protein_id,
                    repeat_residue=repeat_residue,
                    start=tract.start,
                    end=tract.end,
                    aa_sequence=tract.aa_sequence,
                    source_file=row.get("protein_path", ""),
                    merge_rule="contiguous_run",
                )
            )

    call_rows.sort(
        key=lambda row: (
            str(row.get("protein_id", "")),
            int(row.get("start", 0)),
            str(row.get("call_id", "")),
        )
    )
    write_tsv(outdir / "pure_calls.tsv", call_rows, fieldnames=CALL_FIELDNAMES)
    write_run_params(
        outdir / "run_params.tsv",
        "pure",
        {
            "repeat_residue": repeat_residue,
            "min_repeat_count": args.min_repeat_count,
        },
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
