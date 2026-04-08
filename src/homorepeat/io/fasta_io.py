"""Small FASTA helpers for normalized CDS and protein files."""

from __future__ import annotations

import re
from contextlib import contextmanager
from itertools import zip_longest
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from .tsv_io import ContractError, ensure_directory, iter_tsv


def read_fasta(path: Path | str) -> list[tuple[str, str]]:
    """Read a FASTA file into ``(header, sequence)`` tuples."""

    return list(iter_fasta(path))


def iter_fasta(path: Path | str) -> Iterator[tuple[str, str]]:
    """Yield ``(header, sequence)`` tuples from a FASTA file."""

    file_path = Path(path)
    header: str | None = None
    chunks: list[str] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    yield (header, "".join(chunks))
                header = line[1:].strip()
                chunks = []
                continue
            chunks.append(line)
    if header is not None:
        yield (header, "".join(chunks))


def iter_tsv_fasta_pairs(
    tsv_path: Path | str,
    fasta_path: Path | str,
    *,
    required_columns: Sequence[str],
    id_field: str,
) -> Iterator[tuple[dict[str, str], str]]:
    """Yield aligned TSV rows and FASTA sequences keyed by the same identifier."""

    fasta_file_path = Path(fasta_path)
    row_iter = iter_tsv(tsv_path, required_columns=required_columns)
    fasta_iter = iter_fasta(fasta_file_path)
    for row, record in zip_longest(row_iter, fasta_iter):
        if row is None:
            header, _sequence = record
            raise ContractError(f"{fasta_file_path} has unexpected FASTA record {header}")

        expected_id = row.get(id_field, "")
        if record is None:
            raise ContractError(f"{fasta_file_path} is missing {id_field} {expected_id}")

        header, sequence = record
        if header != expected_id:
            raise ContractError(
                f"{fasta_file_path} expected {id_field} {expected_id} but found FASTA header {header}"
            )

        yield row, sequence


def write_fasta(path: Path | str, records: Iterable[tuple[str, str]], *, width: int = 80) -> None:
    """Write FASTA records with wrapped sequence lines."""

    with open_fasta_writer(path, width=width) as writer:
        writer.write_records(records)


class FastaWriter:
    def __init__(self, handle, *, width: int = 80) -> None:
        self._handle = handle
        self._width = width

    def write_record(self, header: str, sequence: str) -> None:
        self._handle.write(f">{header}\n")
        for index in range(0, len(sequence), self._width):
            self._handle.write(f"{sequence[index:index + self._width]}\n")

    def write_records(self, records: Iterable[tuple[str, str]]) -> None:
        for header, sequence in records:
            self.write_record(header, sequence)


@contextmanager
def open_fasta_writer(
    path: Path | str,
    *,
    width: int = 80,
) -> Iterator[FastaWriter]:
    """Open a FASTA writer for incremental record writes."""

    file_path = Path(path)
    ensure_directory(file_path)
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        yield FastaWriter(handle, width=width)


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
