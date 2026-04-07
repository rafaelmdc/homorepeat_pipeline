"""Deterministic batch planning helpers."""

from __future__ import annotations

from itertools import groupby

from homorepeat.core.ids import batch_id
from homorepeat.io.tsv_io import ContractError


def derive_batches(
    selected_rows: list[dict[str, str]],
    *,
    target_batch_size: int,
    max_batches: int | None = None,
) -> list[dict[str, str]]:
    """Split selected assemblies into deterministic operational batches."""

    if target_batch_size <= 0:
        raise ContractError("target_batch_size must be greater than zero")

    sorted_rows = sorted(
        selected_rows,
        key=lambda row: (
            row.get("request_id", ""),
            row.get("taxid", ""),
            row.get("assembly_accession", ""),
        ),
    )
    duplicate_accessions = _find_duplicates(row.get("assembly_accession", "") for row in sorted_rows)
    if duplicate_accessions:
        duplicates = ", ".join(sorted(duplicate_accessions))
        raise ContractError(f"selected_assemblies.tsv contains duplicate accessions: {duplicates}")

    batched_rows: list[dict[str, str]] = []
    batch_index = 1
    for request_id, request_group_iter in groupby(sorted_rows, key=lambda row: row.get("request_id", "")):
        request_group = list(request_group_iter)
        if len(request_group) <= target_batch_size:
            rows = _shape_batch_rows(
                request_group,
                batch_id(batch_index),
                batch_reason="single_small_taxon_batch",
            )
            batched_rows.extend(rows)
            batch_index += 1
            continue

        for offset in range(0, len(request_group), target_batch_size):
            chunk = request_group[offset : offset + target_batch_size]
            rows = _shape_batch_rows(
                chunk,
                batch_id(batch_index),
                batch_reason="split_large_taxon_fixed_size",
            )
            batched_rows.extend(rows)
            batch_index += 1

    if max_batches is not None and len({row["batch_id"] for row in batched_rows}) > max_batches:
        raise ContractError(
            f"batch planning would create more than {max_batches} batches under the current policy"
        )

    return batched_rows


def _shape_batch_rows(
    rows: list[dict[str, str]],
    current_batch_id: str,
    *,
    batch_reason: str,
) -> list[dict[str, str]]:
    shaped_rows: list[dict[str, str]] = []
    for row in rows:
        shaped_rows.append(
            {
                "batch_id": current_batch_id,
                "request_id": row.get("request_id", ""),
                "assembly_accession": row.get("assembly_accession", ""),
                "taxon_id": row.get("taxid", ""),
                "batch_reason": batch_reason,
                "resolved_name": row.get("resolved_name", ""),
                "refseq_category": row.get("refseq_category", ""),
                "assembly_level": row.get("assembly_level", ""),
                "annotation_status": row.get("annotation_status", ""),
            }
        )
    return shaped_rows


def _find_duplicates(values: list[str] | tuple[str, ...] | object) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        text = str(value)
        if not text:
            continue
        if text in seen:
            duplicates.add(text)
        seen.add(text)
    return duplicates
