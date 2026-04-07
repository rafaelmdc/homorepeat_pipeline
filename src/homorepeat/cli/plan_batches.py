#!/usr/bin/env python3
"""Derive deterministic execution batches from a frozen selection manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.acquisition.batching import derive_batches  # noqa: E402
from homorepeat.io.tsv_io import ContractError, read_tsv, write_tsv  # noqa: E402


SELECTED_ASSEMBLIES_REQUIRED = [
    "request_id",
    "resolved_name",
    "assembly_accession",
    "taxid",
    "refseq_category",
    "assembly_level",
    "annotation_status",
]
SELECTED_BATCHES_FIELDNAMES = [
    "batch_id",
    "request_id",
    "assembly_accession",
    "taxon_id",
    "batch_reason",
    "resolved_name",
    "refseq_category",
    "assembly_level",
    "annotation_status",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected-assemblies", required=True, help="Path to selected_assemblies.tsv")
    parser.add_argument("--outdir", required=True, help="Output directory for planning artifacts")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument(
        "--target-batch-size",
        type=int,
        default=100,
        help="Target number of assemblies per operational batch",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        help="Optional maximum number of batches before hard-failing",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_rows = read_tsv(args.selected_assemblies, required_columns=SELECTED_ASSEMBLIES_REQUIRED)
    batch_rows = derive_batches(
        selected_rows,
        target_batch_size=args.target_batch_size,
        max_batches=args.max_batches,
    )
    outdir = Path(args.outdir)
    write_tsv(outdir / "selected_batches.tsv", batch_rows, fieldnames=SELECTED_BATCHES_FIELDNAMES)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
