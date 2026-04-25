#!/usr/bin/env python3
"""Publish canonical merged repeat-call codon-usage tables."""

from __future__ import annotations

import argparse
import heapq
import sys
from pathlib import Path
from typing import Iterator

from homorepeat.contracts.publish_contract_v2 import (
    REPEAT_CALL_CODON_USAGE_FIELDNAMES,
    validate_repeat_call_codon_usage_row,
)
from homorepeat.io.tsv_io import ContractError, iter_tsv, open_tsv_writer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codon-usage-tsv",
        action="append",
        default=[],
        help="Path to one finalized codon-usage TSV fragment",
    )
    parser.add_argument("--outdir", required=True, help="Output directory for the canonical merged table")
    parser.add_argument("--log-file", help="Reserved log file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.codon_usage_tsv:
        raise ContractError("At least one --codon-usage-tsv input is required")

    outdir = Path(args.outdir)
    with open_tsv_writer(
        outdir / "repeat_call_codon_usage.tsv",
        fieldnames=REPEAT_CALL_CODON_USAGE_FIELDNAMES,
    ) as writer:
        writer.write_rows(_iter_sorted_codon_usage_rows(args.codon_usage_tsv))
    return 0


def _iter_sorted_codon_usage_rows(paths: list[str]) -> Iterator[dict[str, str]]:
    heap: list[tuple[tuple[str, str, str, str, str], int, dict[str, str], Iterator[dict[str, str]]]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for path_index, path in enumerate(paths):
        iterator = iter_tsv(path, required_columns=REPEAT_CALL_CODON_USAGE_FIELDNAMES)
        try:
            row = next(iterator)
        except StopIteration:
            continue
        heapq.heappush(heap, (_codon_usage_sort_key(row), path_index, row, iterator))

    while heap:
        _, path_index, row, iterator = heapq.heappop(heap)
        validate_repeat_call_codon_usage_row(row)
        usage_key = (row.get("call_id", ""), row.get("amino_acid", ""), row.get("codon", ""))
        if usage_key in seen_keys:
            raise ContractError(
                "Duplicate codon-usage row for "
                f"call_id={usage_key[0]!r}, amino_acid={usage_key[1]!r}, codon={usage_key[2]!r}"
            )
        seen_keys.add(usage_key)
        yield row
        try:
            next_row = next(iterator)
        except StopIteration:
            continue
        heapq.heappush(heap, (_codon_usage_sort_key(next_row), path_index, next_row, iterator))


def _codon_usage_sort_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("method", ""),
        row.get("repeat_residue", ""),
        row.get("call_id", ""),
        row.get("amino_acid", ""),
        row.get("codon", ""),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
