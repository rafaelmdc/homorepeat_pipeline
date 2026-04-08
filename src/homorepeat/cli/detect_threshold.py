#!/usr/bin/env python3
"""Detect threshold-method repeat tracts from canonical protein inputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.detection.detect_threshold import find_threshold_tracts  # noqa: E402
from homorepeat.io.fasta_io import iter_tsv_fasta_pairs  # noqa: E402
from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, build_call_row  # noqa: E402
from homorepeat.contracts.run_params import write_run_params  # noqa: E402
from homorepeat.io.tsv_io import ContractError, open_tsv_writer, write_tsv  # noqa: E402
from homorepeat.runtime.stage_status import build_stage_status, write_stage_status  # noqa: E402


PROTEINS_REQUIRED = [
    "protein_id",
    "sequence_id",
    "genome_id",
    "protein_name",
    "protein_length",
    "taxon_id",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proteins-tsv", required=True, help="Path to canonical proteins.tsv")
    parser.add_argument("--proteins-fasta", required=True, help="Path to canonical proteins.faa")
    parser.add_argument("--repeat-residue", required=True, help="Target amino-acid residue")
    parser.add_argument("--outdir", required=True, help="Output directory for threshold detection artifacts")
    parser.add_argument("--batch-id", default="", help="Optional batch identifier for stage-status output")
    parser.add_argument("--window-size", type=int, default=8, help="Sliding window size")
    parser.add_argument(
        "--min-target-count",
        type=int,
        default=6,
        help="Minimum target count inside a qualifying sliding window",
    )
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
    repeat_residue = args.repeat_residue.strip().upper()
    if len(repeat_residue) != 1:
        raise ContractError(f"--repeat-residue must be one amino-acid symbol: {args.repeat_residue!r}")
    if args.window_size < 1:
        raise ContractError("--window-size must be positive")
    if args.min_target_count < 1 or args.min_target_count > args.window_size:
        raise ContractError("--min-target-count must be between 1 and --window-size")

    outdir = Path(args.outdir)

    window_definition = f"{repeat_residue}{args.min_target_count}/{args.window_size}"
    merge_rule = "merge_adjacent_or_overlap"

    with open_tsv_writer(outdir / "threshold_calls.tsv", fieldnames=CALL_FIELDNAMES) as call_writer:
        for row, protein_sequence in iter_tsv_fasta_pairs(
            args.proteins_tsv,
            args.proteins_fasta,
            required_columns=PROTEINS_REQUIRED,
            id_field="protein_id",
        ):
            protein_id = row.get("protein_id", "")
            for tract in find_threshold_tracts(
                protein_sequence,
                repeat_residue,
                window_size=args.window_size,
                min_target_count=args.min_target_count,
            ):
                call_writer.write_row(
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
                        window_definition=window_definition,
                        merge_rule=merge_rule,
                    )
                )
    write_run_params(
        outdir / "run_params.tsv",
        "threshold",
        repeat_residue,
        {
            "window_size": args.window_size,
            "min_target_count": args.min_target_count,
        },
    )


def _write_failed_outputs(args: argparse.Namespace) -> None:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    write_tsv(outdir / "threshold_calls.tsv", [], fieldnames=CALL_FIELDNAMES)
    write_run_params(
        outdir / "run_params.tsv",
        "threshold",
        args.repeat_residue.strip().upper(),
        {
            "window_size": args.window_size,
            "min_target_count": args.min_target_count,
        },
    )


def _write_status(args: argparse.Namespace, *, status: str, message: str = "") -> None:
    if not args.status_out:
        return
    write_stage_status(
        args.status_out,
        build_stage_status(
            stage="detect",
            status=status,
            batch_id=args.batch_id,
            method="threshold",
            repeat_residue=args.repeat_residue.strip().upper(),
            message=message,
        ),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
