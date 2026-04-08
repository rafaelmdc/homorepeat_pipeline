#!/usr/bin/env python3
"""Summarize one benchmark run from a Nextflow trace and selected size paths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from homorepeat.io.tsv_io import ContractError  # noqa: E402
from homorepeat.runtime.benchmark_summary import summarize_benchmark_run  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", required=True, help="Path to a Nextflow trace.txt file")
    parser.add_argument("--accessions-file", help="Optional benchmark accession list")
    parser.add_argument(
        "--size-path",
        action="append",
        default=[],
        help="Path to measure for disk footprint. Repeat to include both run root and work dir.",
    )
    parser.add_argument("--outpath", help="Optional JSON output path. Defaults to stdout.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = summarize_benchmark_run(
        trace_path=Path(args.trace),
        accessions_file=Path(args.accessions_file) if args.accessions_file else None,
        size_paths=[Path(path) for path in args.size_path],
    )
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.outpath:
        outpath = Path(args.outpath)
        outpath.parent.mkdir(parents=True, exist_ok=True)
        outpath.write_text(serialized, encoding="utf-8")
    else:
        sys.stdout.write(serialized)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
