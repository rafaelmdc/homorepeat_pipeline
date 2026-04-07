"""Seed-extend detection for interrupted homorepeat tracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SeedExtendTract:
    """One seed-extend tract in amino-acid coordinates."""

    start: int
    end: int
    aa_sequence: str


def find_seed_extend_tracts(
    protein_sequence: str,
    repeat_residue: str,
    *,
    seed_window_size: int = 8,
    seed_min_target_count: int = 6,
    extend_window_size: int = 12,
    extend_min_target_count: int = 8,
    min_total_length: int = 10,
) -> list[SeedExtendTract]:
    """Find long interrupted repeat tracts by growing seed-positive windows with looser extend windows."""

    sequence = protein_sequence.strip().upper()
    target = repeat_residue.strip().upper()
    if len(target) != 1:
        raise ValueError(f"repeat_residue must be one amino-acid symbol: {repeat_residue!r}")
    _validate_window_params(
        seed_window_size=seed_window_size,
        seed_min_target_count=seed_min_target_count,
        extend_window_size=extend_window_size,
        extend_min_target_count=extend_min_target_count,
        min_total_length=min_total_length,
    )

    if len(sequence) < seed_window_size:
        return []

    seed_windows = _find_qualifying_windows(
        sequence,
        target,
        window_size=seed_window_size,
        min_target_count=seed_min_target_count,
    )
    if not seed_windows:
        return []

    extend_windows = _find_qualifying_windows(
        sequence,
        target,
        window_size=extend_window_size,
        min_target_count=extend_min_target_count,
    )

    candidate_components = _merge_overlapping_or_adjacent(seed_windows + extend_windows)

    tracts: list[SeedExtendTract] = []
    seen_coordinates: set[tuple[int, int]] = set()
    for start_index, end_index in candidate_components:
        if not _component_contains_seed(start_index, end_index, seed_windows):
            continue
        trimmed_interval = _trim_to_target_edges(sequence, target, start_index, end_index)
        if trimmed_interval is None:
            continue

        trimmed_start, trimmed_end = trimmed_interval
        if trimmed_end - trimmed_start + 1 < min_total_length:
            continue

        coordinates = (trimmed_start, trimmed_end)
        if coordinates in seen_coordinates:
            continue
        seen_coordinates.add(coordinates)

        tracts.append(
            SeedExtendTract(
                start=trimmed_start + 1,
                end=trimmed_end + 1,
                aa_sequence=sequence[trimmed_start : trimmed_end + 1],
            )
        )

    tracts.sort(key=lambda tract: (tract.start, tract.end, tract.aa_sequence))
    return tracts


def _validate_window_params(
    *,
    seed_window_size: int,
    seed_min_target_count: int,
    extend_window_size: int,
    extend_min_target_count: int,
    min_total_length: int,
) -> None:
    if seed_window_size < 1:
        raise ValueError("seed_window_size must be positive")
    if seed_min_target_count < 1 or seed_min_target_count > seed_window_size:
        raise ValueError("seed_min_target_count must be between 1 and seed_window_size")
    if extend_window_size < 1:
        raise ValueError("extend_window_size must be positive")
    if extend_min_target_count < 1 or extend_min_target_count > extend_window_size:
        raise ValueError("extend_min_target_count must be between 1 and extend_window_size")
    if min_total_length < 1:
        raise ValueError("min_total_length must be positive")


def _find_qualifying_windows(
    sequence: str,
    target: str,
    *,
    window_size: int,
    min_target_count: int,
) -> list[tuple[int, int]]:
    if len(sequence) < window_size:
        return []

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

    ordered_windows = sorted(windows)
    merged: list[tuple[int, int]] = []
    current_start, current_end = ordered_windows[0]
    for start_index, end_index in ordered_windows[1:]:
        if start_index <= current_end + 1:
            current_end = max(current_end, end_index)
            continue
        merged.append((current_start, current_end))
        current_start, current_end = start_index, end_index
    merged.append((current_start, current_end))
    return merged


def _component_contains_seed(
    component_start: int,
    component_end: int,
    seed_windows: list[tuple[int, int]],
) -> bool:
    return any(
        seed_start <= component_end and component_start <= seed_end
        for seed_start, seed_end in seed_windows
    )


def _trim_to_target_edges(
    sequence: str,
    target: str,
    start_index: int,
    end_index: int,
) -> tuple[int, int] | None:
    left_index = start_index
    right_index = end_index

    while left_index <= right_index and sequence[left_index] != target:
        left_index += 1
    while right_index >= left_index and sequence[right_index] != target:
        right_index -= 1

    if left_index > right_index:
        return None
    return (left_index, right_index)
