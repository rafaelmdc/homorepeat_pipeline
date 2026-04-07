#!/usr/bin/env python3
"""Apply the settled RefSeq assembly-selection policy to an inventory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from homorepeat.io.tsv_io import ContractError, read_tsv, write_lines, write_tsv  # noqa: E402


ASSEMBLY_INVENTORY_REQUIRED = [
    "request_id",
    "assembly_accession",
    "current_accession",
    "source_database",
    "assembly_status",
    "refseq_category",
    "annotation_status",
]
OUTPUT_FIELDNAMES = [
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
    parser.add_argument("--assembly-inventory", required=True, help="Path to assembly_inventory.tsv")
    parser.add_argument("--outdir", required=True, help="Output directory for planning artifacts")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument(
        "--allow-refseq-representative",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow RefSeq representative assemblies in addition to reference rows",
    )
    parser.add_argument(
        "--require-annotation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require annotation presence for automatic selection",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory_rows = read_tsv(args.assembly_inventory, required_columns=ASSEMBLY_INVENTORY_REQUIRED)
    selected_rows: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []
    seen_selected_accessions: dict[str, str] = {}

    for row in sorted(
        inventory_rows,
        key=lambda item: (
            item.get("assembly_accession", ""),
            item.get("request_id", ""),
        ),
    ):
        decision, reason = classify_inventory_row(
            row,
            allow_refseq_representative=args.allow_refseq_representative,
            require_annotation=args.require_annotation,
        )
        candidate = dict(row)
        candidate["selection_decision"] = decision
        candidate["selection_reason"] = reason

        accession = candidate.get("assembly_accession", "")
        if decision == "selected":
            previous_request_id = seen_selected_accessions.get(accession)
            if previous_request_id is not None:
                candidate["selection_decision"] = "excluded"
                candidate["selection_reason"] = f"duplicate_selected_under_request_{previous_request_id}"
                excluded_rows.append(candidate)
                continue
            seen_selected_accessions[accession] = candidate.get("request_id", "")
            selected_rows.append(candidate)
            continue
        excluded_rows.append(candidate)

    outdir = Path(args.outdir)
    write_tsv(outdir / "selected_assemblies.tsv", selected_rows, fieldnames=OUTPUT_FIELDNAMES)
    write_tsv(outdir / "excluded_assemblies.tsv", excluded_rows, fieldnames=OUTPUT_FIELDNAMES)
    write_lines(
        outdir / "selected_accessions.txt",
        (row["assembly_accession"] for row in sorted(selected_rows, key=lambda item: item["assembly_accession"])),
    )
    return 0


def classify_inventory_row(
    row: dict[str, str],
    *,
    allow_refseq_representative: bool,
    require_annotation: bool,
) -> tuple[str, str]:
    accession = row.get("assembly_accession", "")
    if not accession:
        return "excluded", row.get("selection_reason", "") or "no_candidate_assemblies_returned"

    if row.get("source_database", "").upper() != "REFSEQ":
        return "excluded", "excluded_non_refseq_source"

    if row.get("assembly_status", "").lower() != "current":
        return "excluded", "excluded_noncurrent_assembly"

    current_accession = row.get("current_accession", "") or accession
    if current_accession != accession:
        return "excluded", "excluded_superseded_accession"

    annotation_status = row.get("annotation_status", "")
    if require_annotation and not annotation_status.startswith("annotated"):
        return "excluded", "excluded_missing_required_annotation"

    category = row.get("refseq_category", "").strip().lower()
    if category == "reference genome":
        return "selected", "selected_refseq_reference_annotated"
    if category == "representative genome":
        if allow_refseq_representative:
            return "selected", "selected_refseq_representative_annotated"
        return "excluded", "excluded_representative_disallowed"

    return "selected", "selected_refseq_annotated_uncategorized"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
