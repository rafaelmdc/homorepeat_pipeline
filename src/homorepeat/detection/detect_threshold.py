"""Threshold-method repeat detection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThresholdTract:
    """One threshold-method tract in amino-acid coordinates."""

    start: int
    end: int
    aa_sequence: str


def find_threshold_tracts(
    protein_sequence: str,
    repeat_residue: str,
    *,
    window_size: int = 8,
    min_target_count: int = 6,
) -> list[ThresholdTract]:
    """Find threshold-method tracts using qualifying sliding windows."""

    sequence = protein_sequence.strip().upper()
    target = repeat_residue.strip().upper()
    if len(target) != 1:
        raise ValueError(f"repeat_residue must be one amino-acid symbol: {repeat_residue!r}")
    if window_size < 1:
        raise ValueError("window_size must be positive")
    if min_target_count < 1 or min_target_count > window_size:
        raise ValueError("min_target_count must be between 1 and window_size")
    if len(sequence) < window_size:
        return []

    qualifying_windows = _find_qualifying_windows(
        sequence,
        target,
        window_size=window_size,
        min_target_count=min_target_count,
    )
    merged_candidates = _merge_overlapping_or_adjacent(qualifying_windows)

    tracts: list[ThresholdTract] = []
    seen_coordinates: set[tuple[int, int]] = set()
    for start_index, end_index in merged_candidates:
        trimmed_interval = _trim_to_target_edges(sequence, target, start_index, end_index)
        if trimmed_interval is None:
            continue
        trimmed_start, trimmed_end = trimmed_interval
        coordinates = (trimmed_start, trimmed_end)
        if coordinates in seen_coordinates:
            continue
        seen_coordinates.add(coordinates)
        tracts.append(
            ThresholdTract(
                start=trimmed_start + 1,
                end=trimmed_end + 1,
                aa_sequence=sequence[trimmed_start : trimmed_end + 1],
            )
        )

    tracts.sort(key=lambda tract: (tract.start, tract.end, tract.aa_sequence))
    return tracts


def _find_qualifying_windows(
    sequence: str,
    target: str,
    *,
    window_size: int,
    min_target_count: int,
) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    target_count = sum(1 for residue in sequence[:window_size] if residue == target)
    if target_count >= min_target_count:
        windows.append((0, window_size - 1))

    for start_index in range(1, len(sequence) - window_size + 1):
        left_residue = sequence[start_index - 1]
        right_residue = sequence[start_index + window_size - 1]
        if left_residue == target:
            target_count -= 1
        if right_residue == target:
            target_count += 1
        if target_count >= min_target_count:
            windows.append((start_index, start_index + window_size - 1))
    return windows


def _merge_overlapping_or_adjacent(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not windows:
        return []

    merged: list[tuple[int, int]] = []
    current_start, current_end = windows[0]
    for start_index, end_index in windows[1:]:
        if start_index <= current_end + 1:
            current_end = max(current_end, end_index)
            continue
        merged.append((current_start, current_end))
        current_start, current_end = start_index, end_index
    merged.append((current_start, current_end))
    return merged


def _trim_to_target_edges(sequence: str, target: str, start_index: int, end_index: int) -> tuple[int, int] | None:
    left_index = start_index
    right_index = end_index

    while left_index <= right_index and sequence[left_index] != target:
        left_index += 1
    while right_index >= left_index and sequence[right_index] != target:
        right_index -= 1

    if left_index > right_index:
        return None
    return (left_index, right_index)
