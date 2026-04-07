#!/usr/bin/env python3
"""Enumerate NCBI RefSeq assembly candidates for deterministic requests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from homorepeat.acquisition.ncbi_datasets import (  # noqa: E402
    build_no_candidate_row,
    project_assembly_record,
    summary_genome_accession,
    summary_genome_taxon,
)
from homorepeat.io.tsv_io import ContractError, parse_tsv_bool, read_tsv, write_lines, write_tsv  # noqa: E402


RESOLVED_REQUESTS_REQUIRED = [
    "request_id",
    "input_type",
    "normalized_input",
    "resolution_status",
    "review_required",
]
ASSEMBLY_INVENTORY_FIELDNAMES = [
    "request_id",
    "resolved_taxid",
    "resolved_name",
    "assembly_accession",
    "current_accession",
    "source_database",
    "assembly_level",
    "assembly_type",
    "assembly_status",
    "refseq_category",
    "annotation_status",
    "organism_name",
    "taxid",
    "selection_decision",
    "selection_reason",
    "request_input_type",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolved-requests", required=True, help="Path to resolved_requests.tsv")
    parser.add_argument("--outdir", required=True, help="Output directory for planning artifacts")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument("--api-key", help="NCBI API key")
    parser.add_argument(
        "--include-raw-jsonl",
        action="store_true",
        help="Also write assembly_inventory.jsonl",
    )
    parser.add_argument(
        "--datasets-bin",
        default="datasets",
        help="Path to the NCBI datasets executable",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resolved_rows = read_tsv(args.resolved_requests, required_columns=RESOLVED_REQUESTS_REQUIRED)

    inventory_rows: list[dict[str, str]] = []
    raw_jsonl_lines: list[str] = []
    for row in resolved_rows:
        if parse_tsv_bool(row.get("review_required")):
            continue

        row_input_type = row.get("input_type", "")
        if row_input_type == "assembly_accession":
            query_value = row.get("normalized_input", "") or row.get("original_input", "")
            records, jsonl_lines = summary_genome_accession(
                query_value,
                api_key=args.api_key,
                datasets_bin=args.datasets_bin,
            )
        else:
            matched_taxid = row.get("matched_taxid", "")
            if not matched_taxid:
                raise ContractError(
                    f"Deterministic request_id={row.get('request_id', '')} is missing matched_taxid"
                )
            records, jsonl_lines = summary_genome_taxon(
                matched_taxid,
                api_key=args.api_key,
                datasets_bin=args.datasets_bin,
            )

        if records:
            inventory_rows.extend(project_assembly_record(row, record) for record in records)
            raw_jsonl_lines.extend(_annotate_raw_lines(row.get("request_id", ""), jsonl_lines))
            continue

        inventory_rows.append(build_no_candidate_row(row))

    outdir = Path(args.outdir)
    write_tsv(outdir / "assembly_inventory.tsv", inventory_rows, fieldnames=ASSEMBLY_INVENTORY_FIELDNAMES)
    if args.include_raw_jsonl:
        write_lines(outdir / "assembly_inventory.jsonl", raw_jsonl_lines)
    return 0


def _annotate_raw_lines(request_id: str, raw_lines: list[str]) -> list[str]:
    annotated: list[str] = []
    for line in raw_lines:
        payload = json.loads(line)
        payload["_request_id"] = request_id
        annotated.append(json.dumps(payload, sort_keys=True))
    return annotated


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
