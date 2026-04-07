"""Small FASTA helpers for normalized CDS and protein files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .tsv_io import ensure_directory


def read_fasta(path: Path | str) -> list[tuple[str, str]]:
    """Read a FASTA file into ``(header, sequence)`` tuples."""

    file_path = Path(path)
    records: list[tuple[str, str]] = []
    header: str | None = None
    chunks: list[str] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    records.append((header, "".join(chunks)))
                header = line[1:].strip()
                chunks = []
                continue
            chunks.append(line)
    if header is not None:
        records.append((header, "".join(chunks)))
    return records


def write_fasta(path: Path | str, records: Iterable[tuple[str, str]], *, width: int = 80) -> None:
    """Write FASTA records with wrapped sequence lines."""

    file_path = Path(path)
    ensure_directory(file_path)
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        for header, sequence in records:
            handle.write(f">{header}\n")
            for index in range(0, len(sequence), width):
                handle.write(f"{sequence[index:index + width]}\n")


def parse_ncbi_fasta_header(header: str) -> dict[str, str]:
    """Parse the primary identifier and bracketed key-value metadata."""

    matches = list(re.finditer(r" \[([^\]=]+)=", header))
    prefix = header[: matches[0].start()] if matches else header
    primary_token = prefix.split()[0].strip()
    record_id = primary_token.split("|")[-1] if "|" in primary_token else primary_token
    metadata: dict[str, str] = {"raw_header": header, "record_id": record_id}

    for index, match in enumerate(matches):
        key = match.group(1).strip()
        value_start = match.end()
        value_end = matches[index + 1].start() if index + 1 < len(matches) else len(header)
        raw_value = header[value_start:value_end]
        if raw_value.endswith("]"):
            raw_value = raw_value[:-1]
        metadata[key] = raw_value.strip()
    return metadata


def extract_ncbi_molecule_accession(record_id: str) -> str:
    """Extract the source molecule accession from an NCBI CDS record id."""

    if "_cds_" in record_id:
        return record_id.split("_cds_", 1)[0]
    return ""
