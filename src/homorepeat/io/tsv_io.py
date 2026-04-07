"""Small TSV helpers for contract-driven pipeline artifacts."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class ContractError(ValueError):
    """Raised when a file does not satisfy a documented contract."""


def ensure_directory(path: Path) -> None:
    """Create the parent directory for a file path."""

    path.parent.mkdir(parents=True, exist_ok=True)


def require_columns(
    fieldnames: Sequence[str] | None,
    required_columns: Sequence[str],
    *,
    context: str,
) -> None:
    """Assert that the required columns exist in a header."""

    header = list(fieldnames or [])
    missing = [column for column in required_columns if column not in header]
    if missing:
        missing_text = ", ".join(missing)
        raise ContractError(f"{context} is missing required columns: {missing_text}")


def read_tsv(
    path: Path | str,
    *,
    required_columns: Sequence[str] | None = None,
) -> list[dict[str, str]]:
    """Read a UTF-8 TSV file into ordered row dictionaries."""

    file_path = Path(path)
    with file_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if required_columns:
            require_columns(reader.fieldnames, required_columns, context=str(file_path))
        return [dict(row) for row in reader]


def write_tsv(
    path: Path | str,
    rows: Iterable[Mapping[str, object]],
    *,
    fieldnames: Sequence[str],
) -> None:
    """Write ordered rows to a UTF-8 TSV file."""

    file_path = Path(path)
    ensure_directory(file_path)
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            delimiter="\t",
            fieldnames=list(fieldnames),
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _stringify_tsv_value(row.get(name, "")) for name in fieldnames})


def write_lines(path: Path | str, lines: Iterable[str]) -> None:
    """Write newline-terminated UTF-8 text lines."""

    file_path = Path(path)
    ensure_directory(file_path)
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        for line in lines:
            handle.write(line)
            if not line.endswith("\n"):
                handle.write("\n")


def parse_tsv_bool(value: str | bool | None) -> bool:
    """Parse lowercase TSV booleans plus a few empty/legacy forms."""

    if isinstance(value, bool):
        return value
    normalized = (value or "").strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no", ""}:
        return False
    raise ContractError(f"Cannot parse TSV boolean value: {value!r}")


def _stringify_tsv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
