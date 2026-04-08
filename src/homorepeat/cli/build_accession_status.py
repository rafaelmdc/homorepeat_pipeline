#!/usr/bin/env python3
"""Build published per-accession pipeline status artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from homorepeat.io.tsv_io import ContractError, read_tsv, write_tsv  # noqa: E402
from homorepeat.runtime.accession_status import (  # noqa: E402
    ACCESSION_CALL_COUNTS_FIELDNAMES,
    ACCESSION_STATUS_FIELDNAMES,
    BATCH_TABLE_REQUIRED,
    build_accession_status_tables,
    build_status_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-table", required=True, help="Path to accession_batches.tsv")
    parser.add_argument("--batch-dir", action="append", default=[], help="Path to one translated batch directory")
    parser.add_argument(
        "--detect-status-json",
        action="append",
        default=[],
        help="Path to one detect stage status JSON",
    )
    parser.add_argument(
        "--finalize-status-json",
        action="append",
        default=[],
        help="Path to one finalize stage status JSON",
    )
    parser.add_argument("--call-tsv", action="append", default=[], help="Path to one finalized call TSV fragment")
    parser.add_argument("--outdir", required=True, help="Output directory for published status artifacts")
    parser.add_argument("--log-file", help="Reserved log file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch_table_rows = read_tsv(args.batch_table, required_columns=BATCH_TABLE_REQUIRED)
    status_rows, count_rows = build_accession_status_tables(
        batch_table_rows=batch_table_rows,
        batch_dirs=[Path(path) for path in args.batch_dir],
        detect_status_paths=[Path(path) for path in args.detect_status_json],
        finalize_status_paths=[Path(path) for path in args.finalize_status_json],
        call_tsv_paths=[Path(path) for path in args.call_tsv],
    )
    summary_payload = build_status_summary(status_rows)

    outdir = Path(args.outdir)
    write_tsv(outdir / "accession_status.tsv", status_rows, fieldnames=ACCESSION_STATUS_FIELDNAMES)
    write_tsv(outdir / "accession_call_counts.tsv", count_rows, fieldnames=ACCESSION_CALL_COUNTS_FIELDNAMES)
    (outdir / "status_summary.json").write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
