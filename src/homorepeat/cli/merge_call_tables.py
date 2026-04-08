#!/usr/bin/env python3
"""Publish canonical merged call and run-parameter tables."""

from __future__ import annotations

import argparse
import heapq
import sys
from pathlib import Path
from typing import Iterator

from homorepeat.contracts.repeat_features import CALL_FIELDNAMES
from homorepeat.contracts.run_params import RUN_PARAM_FIELDNAMES
from homorepeat.io.tsv_io import ContractError, iter_tsv, open_tsv_writer, write_tsv


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

    run_params_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for path in args.run_params_tsv:
        for row in iter_tsv(path, required_columns=RUN_PARAM_FIELDNAMES):
            key = (row.get("method", ""), row.get("repeat_residue", ""), row.get("param_name", ""))
            existing = run_params_by_key.get(key)
            if existing and existing.get("param_value", "") != row.get("param_value", ""):
                raise ContractError(
                    "Conflicting run_params rows for "
                    f"{key[0]}:{key[1]}:{key[2]} -> "
                    f"{existing.get('param_value', '')!r} vs {row.get('param_value', '')!r}"
                )
            run_params_by_key[key] = row
    run_param_rows = sorted(
        run_params_by_key.values(),
        key=lambda row: (row.get("method", ""), row.get("repeat_residue", ""), row.get("param_name", "")),
    )

    outdir = Path(args.outdir)
    with open_tsv_writer(outdir / "repeat_calls.tsv", fieldnames=CALL_FIELDNAMES) as call_writer:
        call_writer.write_rows(_iter_sorted_call_rows(args.call_tsv))
    write_tsv(outdir / "run_params.tsv", run_param_rows, fieldnames=RUN_PARAM_FIELDNAMES)
    return 0


def _iter_sorted_call_rows(paths: list[str]) -> Iterator[dict[str, str]]:
    heap: list[tuple[tuple[str, str, str, int, str], int, dict[str, str], Iterator[dict[str, str]]]] = []
    for path_index, path in enumerate(paths):
        iterator = iter_tsv(path, required_columns=CALL_FIELDNAMES)
        try:
            row = next(iterator)
        except StopIteration:
            continue
        heapq.heappush(heap, (_call_sort_key(row), path_index, row, iterator))

    while heap:
        _, path_index, row, iterator = heapq.heappop(heap)
        yield row
        try:
            next_row = next(iterator)
        except StopIteration:
            continue
        heapq.heappush(heap, (_call_sort_key(next_row), path_index, next_row, iterator))


def _call_sort_key(row: dict[str, str]) -> tuple[str, str, str, int, str]:
    return (
        row.get("method", ""),
        row.get("repeat_residue", ""),
        row.get("protein_id", ""),
        int(row.get("start", "0")),
        row.get("call_id", ""),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
