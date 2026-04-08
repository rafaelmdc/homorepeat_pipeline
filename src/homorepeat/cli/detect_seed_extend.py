#!/usr/bin/env python3
"""Detect long interrupted homorepeat tracts with the seed-extend method."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, build_call_row  # noqa: E402
from homorepeat.contracts.run_params import write_run_params  # noqa: E402
from homorepeat.detection.detect_seed_extend import find_seed_extend_tracts  # noqa: E402
from homorepeat.io.fasta_io import iter_tsv_fasta_pairs  # noqa: E402
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

METHOD_NAME = "seed_extend"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proteins-tsv", required=True, help="Path to canonical proteins.tsv")
    parser.add_argument("--proteins-fasta", required=True, help="Path to canonical proteins.faa")
    parser.add_argument("--repeat-residue", required=True, help="Target amino-acid residue")
    parser.add_argument("--outdir", required=True, help="Output directory for seed-extend artifacts")
    parser.add_argument("--batch-id", default="", help="Optional batch identifier for stage-status output")
    parser.add_argument("--seed-window-size", type=int, default=8, help="Strict seed window size")
    parser.add_argument(
        "--seed-min-target-count",
        type=int,
        default=6,
        help="Minimum target-residue count in a seed window",
    )
    parser.add_argument("--extend-window-size", type=int, default=12, help="Looser extend window size")
    parser.add_argument(
        "--extend-min-target-count",
        type=int,
        default=8,
        help="Minimum target-residue count in an extend window",
    )
    parser.add_argument("--min-total-length", type=int, default=10, help="Minimum final tract length")
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

    outdir = Path(args.outdir)

    window_definition = (
        f"seed:{repeat_residue}{args.seed_min_target_count}/{args.seed_window_size}"
        f"|extend:{repeat_residue}{args.extend_min_target_count}/{args.extend_window_size}"
    )
    merge_rule = "seed_extend_connected_windows"

    with open_tsv_writer(outdir / f"{METHOD_NAME}_calls.tsv", fieldnames=CALL_FIELDNAMES) as call_writer:
        for row, protein_sequence in iter_tsv_fasta_pairs(
            args.proteins_tsv,
            args.proteins_fasta,
            required_columns=PROTEINS_REQUIRED,
            id_field="protein_id",
        ):
            protein_id = row.get("protein_id", "")
            try:
                tracts = find_seed_extend_tracts(
                    protein_sequence,
                    repeat_residue,
                    seed_window_size=args.seed_window_size,
                    seed_min_target_count=args.seed_min_target_count,
                    extend_window_size=args.extend_window_size,
                    extend_min_target_count=args.extend_min_target_count,
                    min_total_length=args.min_total_length,
                )
            except ValueError as exc:
                raise ContractError(str(exc)) from exc

            for tract in tracts:
                call_writer.write_row(
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
                        window_definition=window_definition,
                        merge_rule=merge_rule,
                    )
                )
    write_run_params(
        outdir / "run_params.tsv",
        METHOD_NAME,
        repeat_residue,
        {
            "seed_window_size": args.seed_window_size,
            "seed_min_target_count": args.seed_min_target_count,
            "extend_window_size": args.extend_window_size,
            "extend_min_target_count": args.extend_min_target_count,
            "min_total_length": args.min_total_length,
        },
    )


def _write_failed_outputs(args: argparse.Namespace) -> None:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    write_tsv(outdir / f"{METHOD_NAME}_calls.tsv", [], fieldnames=CALL_FIELDNAMES)
    write_run_params(
        outdir / "run_params.tsv",
        METHOD_NAME,
        args.repeat_residue.strip().upper(),
        {
            "seed_window_size": args.seed_window_size,
            "seed_min_target_count": args.seed_min_target_count,
            "extend_window_size": args.extend_window_size,
            "extend_min_target_count": args.extend_min_target_count,
            "min_total_length": args.min_total_length,
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
            method=METHOD_NAME,
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
