"""Structured warning-row helpers."""

from __future__ import annotations

from typing import Iterable


WARNING_FIELDNAMES = [
    "warning_code",
    "warning_scope",
    "warning_message",
    "batch_id",
    "genome_id",
    "sequence_id",
    "protein_id",
    "assembly_accession",
    "source_file",
    "source_record_id",
]


def build_warning_row(
    warning_code: str,
    warning_scope: str,
    warning_message: str,
    **extra_fields: object,
) -> dict[str, object]:
    """Build one warning row using the canonical column order."""

    row: dict[str, object] = {
        "warning_code": warning_code,
        "warning_scope": warning_scope,
        "warning_message": warning_message,
    }
    for fieldname in WARNING_FIELDNAMES[3:]:
        row[fieldname] = extra_fields.get(fieldname, "")
    return row


def join_warning_values(values: Iterable[object]) -> str:
    """Join stable warning values into one human-readable TSV field."""

    items = []
    for value in values:
        text = str(value).strip()
        if text:
            items.append(text)
    return "; ".join(items)
