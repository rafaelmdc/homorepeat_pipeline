"""Helpers for per-stage batch/task status markers."""

from __future__ import annotations

import json
from pathlib import Path

from homorepeat.io.tsv_io import ensure_directory


def build_stage_status(
    *,
    stage: str,
    status: str,
    batch_id: str,
    method: str = "",
    repeat_residue: str = "",
    message: str = "",
) -> dict[str, str]:
    """Build one stable stage-status payload."""

    return {
        "stage": stage,
        "status": status,
        "batch_id": batch_id,
        "method": method,
        "repeat_residue": repeat_residue,
        "message": message,
    }


def write_stage_status(path: Path | str, payload: dict[str, str]) -> None:
    """Write a stage-status payload as stable JSON."""

    file_path = Path(path)
    ensure_directory(file_path)
    file_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_stage_status(path: Path | str) -> dict[str, str]:
    """Read one stage-status payload."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Stage status payload is not a JSON object: {path}")
    return {
        "stage": str(payload.get("stage", "")),
        "status": str(payload.get("status", "")),
        "batch_id": str(payload.get("batch_id", "")),
        "method": str(payload.get("method", "")),
        "repeat_residue": str(payload.get("repeat_residue", "")),
        "message": str(payload.get("message", "")),
    }
