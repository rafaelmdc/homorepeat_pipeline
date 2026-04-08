"""Helpers for summarizing benchmark runs from Nextflow trace output."""

from __future__ import annotations

import csv
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from homorepeat.io.tsv_io import ContractError


TRACE_REQUIRED_COLUMNS = ["name", "status", "submit", "realtime", "peak_rss"]
TRACE_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
SIZE_PATTERN = re.compile(r"^\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[KMGT]?B)\s*$")
DURATION_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)(?P<unit>ms|s|m|h|d)")
SIZE_UNITS = {
    "B": 1,
    "KB": 1024,
    "MB": 1024**2,
    "GB": 1024**3,
    "TB": 1024**4,
}


def summarize_benchmark_run(
    *,
    trace_path: Path,
    accessions_file: Path | None = None,
    size_paths: list[Path] | None = None,
) -> dict[str, object]:
    trace_rows = _read_trace_rows(trace_path)
    if not trace_rows:
        raise ContractError(f"Trace file is empty: {trace_path}")

    started_candidates = [row["submit_at"] for row in trace_rows if row["submit_at"] is not None]
    started_at = min(started_candidates) if started_candidates else None
    completed_rows = [row for row in trace_rows if row["completed_at"] is not None]
    finished_at = max((row["completed_at"] for row in completed_rows), default=None)

    process_summary: dict[str, dict[str, object]] = {}
    for row in trace_rows:
        process_name = row["base_name"]
        summary = process_summary.setdefault(
            process_name,
            {
                "n_tasks": 0,
                "n_completed_tasks": 0,
                "max_peak_rss_bytes": None,
                "max_peak_rss": "",
                "first_completed_at": None,
            },
        )
        summary["n_tasks"] = int(summary["n_tasks"]) + 1
        if row["status"] == "COMPLETED":
            summary["n_completed_tasks"] = int(summary["n_completed_tasks"]) + 1
        peak_rss_bytes = row["peak_rss_bytes"]
        if peak_rss_bytes is not None and (
            summary["max_peak_rss_bytes"] is None or peak_rss_bytes > summary["max_peak_rss_bytes"]
        ):
            summary["max_peak_rss_bytes"] = peak_rss_bytes
            summary["max_peak_rss"] = format_bytes(peak_rss_bytes)
        completed_at = row["completed_at"]
        if completed_at is not None and (
            summary["first_completed_at"] is None or completed_at < summary["first_completed_at"]
        ):
            summary["first_completed_at"] = completed_at

    peak_rss_by_process = {
        process_name: {
            "n_tasks": summary["n_tasks"],
            "n_completed_tasks": summary["n_completed_tasks"],
            "max_peak_rss_bytes": summary["max_peak_rss_bytes"],
            "max_peak_rss": summary["max_peak_rss"],
        }
        for process_name, summary in sorted(process_summary.items())
    }

    milestones = {
        "time_to_first_normalize_completion_seconds": _seconds_from_start(
            started_at,
            _first_completion(process_summary, contains="NORMALIZE_CDS_BATCH"),
        ),
        "time_to_first_translate_completion_seconds": _seconds_from_start(
            started_at,
            _first_completion(process_summary, contains="TRANSLATE_CDS_BATCH"),
        ),
        "time_to_first_detection_completion_seconds": _seconds_from_start(
            started_at,
            _first_completion(process_summary, contains="DETECT_"),
        ),
    }

    payload: dict[str, object] = {
        "trace": {
            "path": str(trace_path),
            "n_tasks": len(trace_rows),
            "n_completed_tasks": sum(1 for row in trace_rows if row["status"] == "COMPLETED"),
            "started_at": _format_datetime(started_at),
            "finished_at": _format_datetime(finished_at),
            "elapsed_seconds_estimate": _seconds_between(started_at, finished_at),
            "peak_rss_by_process": peak_rss_by_process,
            "milestones": milestones,
        },
        "checklist": [
            "peak RSS by process",
            "total work-dir or run-root size",
            "time to first translated batch",
            "time to first detection output",
        ],
    }
    if accessions_file is not None:
        payload["benchmark_input"] = {
            "path": str(accessions_file),
            "n_accessions": count_nonempty_lines(accessions_file),
        }
    if size_paths:
        size_summary: dict[str, dict[str, object]] = {}
        for path in size_paths:
            size_bytes = measure_path_size(path)
            size_summary[str(path)] = {
                "bytes": size_bytes,
                "human": format_bytes(size_bytes),
            }
        payload["sizes"] = size_summary
    return payload


def count_nonempty_lines(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            if raw_line.strip():
                count += 1
    return count


def measure_path_size(path: Path) -> int:
    if path.is_symlink():
        return 0
    if path.is_file():
        return path.stat().st_size
    if not path.exists():
        raise ContractError(f"Size path does not exist: {path}")
    total = 0
    with os.scandir(path) as entries:
        for entry in entries:
            entry_path = Path(entry.path)
            if entry.is_symlink():
                continue
            if entry.is_file(follow_symlinks=False):
                total += entry.stat(follow_symlinks=False).st_size
                continue
            if entry.is_dir(follow_symlinks=False):
                total += measure_path_size(entry_path)
    return total


def parse_human_size_bytes(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    match = SIZE_PATTERN.match(text)
    if match is None:
        raise ContractError(f"Unsupported size value in trace: {value!r}")
    amount = float(match.group("value"))
    unit = match.group("unit")
    return int(amount * SIZE_UNITS[unit])


def parse_human_duration(value: str) -> timedelta | None:
    text = value.strip()
    if not text:
        return None
    total_seconds = 0.0
    for part in text.split():
        match = DURATION_PATTERN.fullmatch(part)
        if match is None:
            raise ContractError(f"Unsupported duration value in trace: {value!r}")
        amount = float(match.group("value"))
        unit = match.group("unit")
        if unit == "ms":
            total_seconds += amount / 1000.0
        elif unit == "s":
            total_seconds += amount
        elif unit == "m":
            total_seconds += amount * 60.0
        elif unit == "h":
            total_seconds += amount * 3600.0
        elif unit == "d":
            total_seconds += amount * 86400.0
    return timedelta(seconds=total_seconds)


def format_bytes(value: int | None) -> str:
    if value is None:
        return ""
    if value < 1024:
        return f"{value} B"
    units = ["KB", "MB", "GB", "TB"]
    scaled = float(value)
    for unit in units:
        scaled /= 1024.0
        if scaled < 1024.0 or unit == units[-1]:
            return f"{scaled:.1f} {unit}"
    return f"{value} B"


def _read_trace_rows(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        header = list(reader.fieldnames or [])
        missing = [column for column in TRACE_REQUIRED_COLUMNS if column not in header]
        if missing:
            raise ContractError(f"{path} is missing required trace columns: {', '.join(missing)}")
        rows: list[dict[str, object]] = []
        for raw_row in reader:
            name = raw_row.get("name", "")
            submit_at = _parse_trace_datetime(raw_row.get("submit", ""))
            realtime = parse_human_duration(raw_row.get("realtime", ""))
            completed_at = submit_at + realtime if submit_at is not None and realtime is not None else None
            rows.append(
                {
                    "name": name,
                    "base_name": name.split(" (", 1)[0],
                    "status": raw_row.get("status", ""),
                    "submit_at": submit_at,
                    "completed_at": completed_at,
                    "peak_rss_bytes": parse_human_size_bytes(raw_row.get("peak_rss", "")),
                }
            )
    return rows


def _parse_trace_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    return datetime.strptime(text, TRACE_TIMESTAMP_FORMAT)


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat(timespec="milliseconds") if value is not None else None


def _first_completion(
    process_summary: dict[str, dict[str, object]],
    *,
    contains: str,
) -> datetime | None:
    first_completed = None
    for process_name, summary in process_summary.items():
        if contains not in process_name:
            continue
        completed_at = summary["first_completed_at"]
        if completed_at is None:
            continue
        if first_completed is None or completed_at < first_completed:
            first_completed = completed_at
    return first_completed


def _seconds_from_start(started_at: datetime | None, completed_at: datetime | None) -> float | None:
    return _seconds_between(started_at, completed_at)


def _seconds_between(started_at: datetime | None, completed_at: datetime | None) -> float | None:
    if started_at is None or completed_at is None:
        return None
    return round((completed_at - started_at).total_seconds(), 3)
