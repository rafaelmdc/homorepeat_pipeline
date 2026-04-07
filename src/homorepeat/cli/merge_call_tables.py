#!/usr/bin/env python3
"""Publish canonical merged call and run-parameter tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.contracts.repeat_features import CALL_FIELDNAMES
from homorepeat.contracts.run_params import RUN_PARAM_FIELDNAMES
from homorepeat.io.tsv_io import ContractError, read_tsv, write_tsv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--call-tsv", action="append", default=[], help="Path to one finalized call table")
    parser.add_argument(
        "--run-params-tsv",
        action="append",
        default=[],
        help="Path to one finalized run_params.tsv fragment",
    )
    parser.add_argument("--outdir", required=True, help="Output directory for canonical merged call artifacts")
    parser.add_argument("--log-file", help="Reserved log file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.call_tsv:
        raise ContractError("At least one --call-tsv input is required")
    if not args.run_params_tsv:
        raise ContractError("At least one --run-params-tsv input is required")

    call_rows: list[dict[str, str]] = []
    for path in args.call_tsv:
        call_rows.extend(read_tsv(path, required_columns=CALL_FIELDNAMES))
    call_rows.sort(
        key=lambda row: (
            row.get("method", ""),
            row.get("repeat_residue", ""),
            row.get("protein_id", ""),
            int(row.get("start", "0")),
            row.get("call_id", ""),
        )
    )

    run_params_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for path in args.run_params_tsv:
        for row in read_tsv(path, required_columns=RUN_PARAM_FIELDNAMES):
            key = (row.get("method", ""), row.get("param_name", ""))
            existing = run_params_by_key.get(key)
            if existing and existing.get("param_value", "") != row.get("param_value", ""):
                raise ContractError(
                    "Conflicting run_params rows for "
                    f"{key[0]}:{key[1]} -> {existing.get('param_value', '')!r} vs {row.get('param_value', '')!r}"
                )
            run_params_by_key[key] = row
    run_param_rows = sorted(
        run_params_by_key.values(),
        key=lambda row: (row.get("method", ""), row.get("param_name", "")),
    )

    outdir = Path(args.outdir)
    write_tsv(outdir / "repeat_calls.tsv", call_rows, fieldnames=CALL_FIELDNAMES)
    write_tsv(outdir / "run_params.tsv", run_param_rows, fieldnames=RUN_PARAM_FIELDNAMES)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
