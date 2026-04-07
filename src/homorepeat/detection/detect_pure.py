"""Pure-method repeat detection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PureTract:
    """One pure-method tract in amino-acid coordinates."""

    start: int
    end: int
    aa_sequence: str


def find_pure_tracts(
    protein_sequence: str,
    repeat_residue: str,
    *,
    min_repeat_count: int = 6,
) -> list[PureTract]:
    """Find maximal contiguous pure-method tracts."""

    sequence = protein_sequence.strip().upper()
    target = repeat_residue.strip().upper()
    if len(target) != 1:
        raise ValueError(f"repeat_residue must be one amino-acid symbol: {repeat_residue!r}")
    if min_repeat_count < 1:
        raise ValueError("min_repeat_count must be positive")

    tracts: list[PureTract] = []
    start_index: int | None = None

    for index, residue in enumerate(sequence):
        if residue == target:
            if start_index is None:
                start_index = index
            continue

        if start_index is None:
            continue

        _append_tract_if_qualifying(
            tracts,
            sequence,
            start_index=start_index,
            end_index=index - 1,
            min_repeat_count=min_repeat_count,
        )
        start_index = None

    if start_index is not None:
        _append_tract_if_qualifying(
            tracts,
            sequence,
            start_index=start_index,
            end_index=len(sequence) - 1,
            min_repeat_count=min_repeat_count,
        )

    return tracts


def _append_tract_if_qualifying(
    tracts: list[PureTract],
    sequence: str,
    *,
    start_index: int | None,
    end_index: int | None,
    min_repeat_count: int,
) -> None:
    if start_index is None or end_index is None or end_index < start_index:
        return

    aa_sequence = sequence[start_index : end_index + 1]
    if len(aa_sequence) < min_repeat_count:
        return

    tracts.append(
        PureTract(
            start=start_index + 1,
            end=end_index + 1,
            aa_sequence=aa_sequence,
        )
    )
