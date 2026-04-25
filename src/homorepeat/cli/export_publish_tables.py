#!/usr/bin/env python3
"""Export the additive publish-contract v2 flat tables and summaries."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.io.tsv_io import ContractError
from homorepeat.runtime.publish_contract_v2 import export_publish_tables, read_batch_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-table", required=True, help="Path to accession_batches.tsv")
    parser.add_argument("--batch-dir", action="append", default=[], help="Path to one staged batch export directory")
    parser.add_argument("--repeat-calls-tsv", required=True, help="Path to canonical repeat_calls.tsv")
    parser.add_argument("--accession-status-tsv", required=True, help="Path to accession_status.tsv")
    parser.add_argument("--accession-call-counts-tsv", required=True, help="Path to accession_call_counts.tsv")
    parser.add_argument("--status-summary-json", required=True, help="Path to status_summary.json")
    parser.add_argument("--outdir", required=True, help="Output directory for the flat publish tables")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument(
        "--strict-taxonomy-merge",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Hard-fail if two taxonomy rows with the same taxon_id disagree materially",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch_table_rows = read_batch_table(args.batch_table)
    export_publish_tables(
        batch_table_rows=batch_table_rows,
        batch_dirs=[Path(path) for path in args.batch_dir],
        repeat_calls_tsv=Path(args.repeat_calls_tsv),
        accession_status_tsv=Path(args.accession_status_tsv),
        accession_call_counts_tsv=Path(args.accession_call_counts_tsv),
        status_summary_json=Path(args.status_summary_json),
        outdir=Path(args.outdir),
        strict_taxonomy_merge=args.strict_taxonomy_merge,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
