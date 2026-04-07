#!/usr/bin/env python3
"""Resolve user taxon requests into deterministic planning artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.taxonomy.ncbi import (  # noqa: E402
    get_build_version,
    inspect_lineage,
    lineage_to_string,
    resolve_name,
    terminal_lineage_entry,
)
from homorepeat.io.tsv_io import ContractError, parse_tsv_bool, read_tsv, write_tsv  # noqa: E402
from homorepeat.contracts.warnings import join_warning_values  # noqa: E402


REQUESTED_TAXA_REQUIRED = ["request_id", "input_value", "input_type"]
RESOLVED_FIELDNAMES = [
    "request_id",
    "original_input",
    "normalized_input",
    "input_type",
    "provided_rank",
    "selection_policy",
    "resolution_status",
    "resolver_status",
    "review_required",
    "matched_taxid",
    "matched_name",
    "matched_rank",
    "lineage",
    "warnings",
    "taxonomy_build_version",
    "notes",
]
REVIEW_QUEUE_FIELDNAMES = [
    "request_id",
    "original_input",
    "normalized_input",
    "resolution_status",
    "review_required",
    "warnings",
    "taxonomy_build_version",
    "matched_taxid",
    "matched_name",
    "matched_rank",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requested-taxa", required=True, help="Path to requested_taxa.tsv")
    parser.add_argument("--taxonomy-db", required=True, help="Path to the taxon-weaver SQLite DB")
    parser.add_argument("--outdir", required=True, help="Output directory for planning artifacts")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument(
        "--fail-on-review-queue",
        action="store_true",
        help="Exit non-zero when one or more rows require review after outputs are written",
    )
    parser.add_argument(
        "--taxon-weaver-bin",
        default="taxon-weaver",
        help="Path to the taxon-weaver executable",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requested_rows = read_tsv(args.requested_taxa, required_columns=REQUESTED_TAXA_REQUIRED)
    taxonomy_build_version = get_build_version(
        args.taxonomy_db,
        taxon_weaver_bin=args.taxon_weaver_bin,
    )

    resolved_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    for row in requested_rows:
        resolved_row = resolve_request_row(
            row,
            taxonomy_db=args.taxonomy_db,
            taxonomy_build_version=taxonomy_build_version,
            taxon_weaver_bin=args.taxon_weaver_bin,
        )
        resolved_rows.append(resolved_row)
        if parse_tsv_bool(str(resolved_row["review_required"])):
            review_rows.append({field: resolved_row.get(field, "") for field in REVIEW_QUEUE_FIELDNAMES})

    outdir = Path(args.outdir)
    write_tsv(outdir / "resolved_requests.tsv", resolved_rows, fieldnames=RESOLVED_FIELDNAMES)
    write_tsv(outdir / "taxonomy_review_queue.tsv", review_rows, fieldnames=REVIEW_QUEUE_FIELDNAMES)

    if args.fail_on_review_queue and review_rows:
        return 3
    return 0


def resolve_request_row(
    row: dict[str, str],
    *,
    taxonomy_db: str,
    taxonomy_build_version: str,
    taxon_weaver_bin: str,
) -> dict[str, object]:
    input_type = (row.get("input_type", "") or "").strip()
    input_value = (row.get("input_value", "") or "").strip()
    provided_rank = (row.get("provided_rank", "") or "").strip()

    if not input_value:
        raise ContractError(f"request_id={row.get('request_id', '')} has an empty input_value")

    if input_type == "taxid":
        return resolve_taxid_row(
            row,
            input_value=input_value,
            taxonomy_db=taxonomy_db,
            taxonomy_build_version=taxonomy_build_version,
            taxon_weaver_bin=taxon_weaver_bin,
        )
    if input_type in {"scientific_name", "common_name"}:
        return resolve_name_row(
            row,
            input_value=input_value,
            provided_rank=provided_rank or None,
            taxonomy_db=taxonomy_db,
            taxonomy_build_version=taxonomy_build_version,
            taxon_weaver_bin=taxon_weaver_bin,
        )
    if input_type == "assembly_accession":
        return {
            "request_id": row.get("request_id", ""),
            "original_input": input_value,
            "normalized_input": input_value.upper(),
            "input_type": input_type,
            "provided_rank": provided_rank,
            "selection_policy": row.get("selection_policy", ""),
            "resolution_status": "resolved_direct_accession",
            "resolver_status": "resolved_direct_accession",
            "review_required": False,
            "matched_taxid": "",
            "matched_name": "",
            "matched_rank": "",
            "lineage": "",
            "warnings": "",
            "taxonomy_build_version": taxonomy_build_version,
            "notes": row.get("notes", ""),
        }
    raise ContractError(f"Unsupported input_type: {input_type}")


def resolve_taxid_row(
    row: dict[str, str],
    *,
    input_value: str,
    taxonomy_db: str,
    taxonomy_build_version: str,
    taxon_weaver_bin: str,
) -> dict[str, object]:
    try:
        taxid = int(input_value)
    except ValueError as exc:
        raise ContractError(f"Invalid taxid input: {input_value!r}") from exc

    lineage = inspect_lineage(taxid, taxonomy_db, taxon_weaver_bin=taxon_weaver_bin)
    matched_entry = terminal_lineage_entry(lineage)
    return {
        "request_id": row.get("request_id", ""),
        "original_input": input_value,
        "normalized_input": input_value,
        "input_type": row.get("input_type", ""),
        "provided_rank": row.get("provided_rank", ""),
        "selection_policy": row.get("selection_policy", ""),
        "resolution_status": "resolved",
        "resolver_status": "resolved_taxid_input",
        "review_required": False,
        "matched_taxid": input_value,
        "matched_name": matched_entry.get("name", ""),
        "matched_rank": matched_entry.get("rank", ""),
        "lineage": lineage_to_string(lineage),
        "warnings": "",
        "taxonomy_build_version": taxonomy_build_version,
        "notes": row.get("notes", ""),
    }


def resolve_name_row(
    row: dict[str, str],
    *,
    input_value: str,
    provided_rank: str | None,
    taxonomy_db: str,
    taxonomy_build_version: str,
    taxon_weaver_bin: str,
) -> dict[str, object]:
    payload = resolve_name(
        input_value,
        taxonomy_db,
        provided_level=provided_rank,
        allow_fuzzy=True,
        taxon_weaver_bin=taxon_weaver_bin,
    )
    review_required = bool(payload.get("review_required"))
    return {
        "request_id": row.get("request_id", ""),
        "original_input": input_value,
        "normalized_input": payload.get("normalized_name", input_value),
        "input_type": row.get("input_type", ""),
        "provided_rank": row.get("provided_rank", ""),
        "selection_policy": row.get("selection_policy", ""),
        "resolution_status": "review_required" if review_required else "resolved",
        "resolver_status": payload.get("status", ""),
        "review_required": review_required,
        "matched_taxid": payload.get("matched_taxid", ""),
        "matched_name": payload.get("matched_name", ""),
        "matched_rank": payload.get("matched_rank", ""),
        "lineage": lineage_to_string(payload.get("lineage", [])),
        "warnings": join_warning_values(payload.get("warnings", [])),
        "taxonomy_build_version": payload.get("taxonomy_build_version", taxonomy_build_version),
        "notes": row.get("notes", ""),
    }


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
