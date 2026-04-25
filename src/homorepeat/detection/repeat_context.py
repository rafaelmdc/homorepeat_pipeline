"""Compact flanking-context helpers for repeat-call exports."""

from __future__ import annotations

from homorepeat.contracts.publish_contract_v2 import validate_repeat_context_row
from homorepeat.io.tsv_io import ContractError


DEFAULT_AA_CONTEXT_WINDOW_SIZE = 20
DEFAULT_NT_CONTEXT_WINDOW_SIZE = 60


def build_repeat_context_row(
    call_row: dict[str, str],
    *,
    protein_sequence: str,
    cds_sequence: str,
    aa_context_window_size: int = DEFAULT_AA_CONTEXT_WINDOW_SIZE,
    nt_context_window_size: int = DEFAULT_NT_CONTEXT_WINDOW_SIZE,
) -> dict[str, object]:
    """Build one compact repeat-context row from a validated repeat-call coordinate."""

    if aa_context_window_size < 0:
        raise ContractError("aa_context_window_size must be non-negative")
    if nt_context_window_size < 0:
        raise ContractError("nt_context_window_size must be non-negative")

    try:
        aa_start = int(call_row.get("start", "0"))
        aa_end = int(call_row.get("end", "0"))
    except ValueError as exc:
        raise ContractError("repeat call contains non-integer start/end coordinates") from exc

    normalized_protein = protein_sequence.strip().upper()
    normalized_cds = cds_sequence.strip().upper().replace("U", "T")
    if aa_start < 1 or aa_end < aa_start:
        raise ContractError(f"Invalid repeat-call coordinates: start={aa_start}, end={aa_end}")
    if aa_end > len(normalized_protein):
        raise ContractError(f"repeat call exceeds protein length for call_id {call_row.get('call_id', '')}")

    nt_start = (aa_start - 1) * 3
    nt_end = aa_end * 3
    if nt_end > len(normalized_cds):
        raise ContractError(f"repeat call exceeds CDS length for call_id {call_row.get('call_id', '')}")

    left_aa_start = max(0, aa_start - 1 - aa_context_window_size)
    right_aa_end = min(len(normalized_protein), aa_end + aa_context_window_size)
    left_nt_start = max(0, nt_start - nt_context_window_size)
    right_nt_end = min(len(normalized_cds), nt_end + nt_context_window_size)

    row = {
        "call_id": call_row.get("call_id", ""),
        "protein_id": call_row.get("protein_id", ""),
        "sequence_id": call_row.get("sequence_id", ""),
        "aa_left_flank": normalized_protein[left_aa_start : aa_start - 1],
        "aa_right_flank": normalized_protein[aa_end:right_aa_end],
        "nt_left_flank": normalized_cds[left_nt_start:nt_start],
        "nt_right_flank": normalized_cds[nt_end:right_nt_end],
        "aa_context_window_size": aa_context_window_size,
        "nt_context_window_size": nt_context_window_size,
    }
    validate_repeat_context_row(row)
    return row
