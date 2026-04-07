"""Shared helpers for repeat-call rows."""

from __future__ import annotations

from homorepeat.core.ids import stable_id
from homorepeat.io.tsv_io import ContractError


CALL_FIELDNAMES = [
    "call_id",
    "method",
    "genome_id",
    "taxon_id",
    "sequence_id",
    "protein_id",
    "start",
    "end",
    "length",
    "repeat_residue",
    "repeat_count",
    "non_repeat_count",
    "purity",
    "aa_sequence",
    "codon_sequence",
    "codon_metric_name",
    "codon_metric_value",
    "window_definition",
    "template_name",
    "merge_rule",
    "score",
    "source_file",
]


def build_call_row(
    *,
    method: str,
    genome_id: str,
    taxon_id: str,
    sequence_id: str,
    protein_id: str,
    repeat_residue: str,
    start: int,
    end: int,
    aa_sequence: str,
    source_file: str = "",
    window_definition: str = "",
    template_name: str = "",
    merge_rule: str = "",
    score: str = "",
) -> dict[str, object]:
    """Build one canonical repeat-call row."""

    if start < 1 or end < start:
        raise ContractError(f"Invalid call coordinates: start={start}, end={end}")

    normalized_residue = repeat_residue.strip().upper()
    if len(normalized_residue) != 1:
        raise ContractError(f"repeat_residue must be one amino-acid symbol: {repeat_residue!r}")

    sequence = aa_sequence.strip().upper()
    length = len(sequence)
    if length != end - start + 1:
        raise ContractError(
            "aa_sequence length does not match 1-based inclusive coordinates: "
            f"length={length}, start={start}, end={end}"
        )

    repeat_count = sum(1 for residue in sequence if residue == normalized_residue)
    non_repeat_count = length - repeat_count
    purity = repeat_count / length if length else 0.0
    call_id = stable_id(
        "call",
        method,
        protein_id,
        normalized_residue,
        start,
        end,
        sequence,
    )

    row = {
        "call_id": call_id,
        "method": method,
        "genome_id": genome_id,
        "taxon_id": taxon_id,
        "sequence_id": sequence_id,
        "protein_id": protein_id,
        "start": start,
        "end": end,
        "length": length,
        "repeat_residue": normalized_residue,
        "repeat_count": repeat_count,
        "non_repeat_count": non_repeat_count,
        "purity": f"{purity:.10f}",
        "aa_sequence": sequence,
        "codon_sequence": "",
        "codon_metric_name": "",
        "codon_metric_value": "",
        "window_definition": window_definition,
        "template_name": template_name,
        "merge_rule": merge_rule,
        "score": score,
        "source_file": source_file,
    }
    validate_call_row(row)
    return row


def validate_call_row(row: dict[str, object]) -> None:
    """Validate the core shared repeat-call invariants."""

    start = int(row.get("start", 0))
    end = int(row.get("end", 0))
    length = int(row.get("length", 0))
    repeat_count = int(row.get("repeat_count", 0))
    non_repeat_count = int(row.get("non_repeat_count", 0))
    aa_sequence = str(row.get("aa_sequence", ""))

    if start < 1 or end < start:
        raise ContractError(f"Invalid call coordinates in row: start={start}, end={end}")
    if length != end - start + 1:
        raise ContractError("Call length does not match 1-based inclusive coordinates")
    if repeat_count + non_repeat_count != length:
        raise ContractError("repeat_count + non_repeat_count must equal length")
    if len(aa_sequence) != length:
        raise ContractError("aa_sequence length must equal call length")
