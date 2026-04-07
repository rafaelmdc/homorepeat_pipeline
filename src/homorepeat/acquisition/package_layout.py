"""Helpers for locating expected files inside NCBI package directories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homorepeat.io.tsv_io import ContractError


def find_package_root(path: Path | str) -> Path:
    """Return the package root that contains ``ncbi_dataset/data``."""

    candidate = Path(path)
    if (candidate / "ncbi_dataset" / "data").is_dir():
        return candidate
    if candidate.name == "ncbi_dataset" and (candidate / "data").is_dir():
        return candidate.parent
    raise ContractError(f"Package directory does not contain ncbi_dataset/data: {candidate}")


def load_assembly_report(package_dir: Path | str) -> list[dict[str, Any]]:
    """Load the assembly JSONL report shipped in an NCBI package."""

    package_root = find_package_root(package_dir)
    report_path = package_root / "ncbi_dataset" / "data" / "assembly_data_report.jsonl"
    if not report_path.is_file():
        raise ContractError(f"Missing assembly_data_report.jsonl under {package_root}")

    records: list[dict[str, Any]] = []
    with report_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ContractError("assembly_data_report.jsonl contains a non-object JSON line")
            records.append(payload)
    return records


def load_sequence_report(package_dir: Path | str, accession: str) -> list[dict[str, Any]]:
    """Load one accession-specific sequence report when the package includes it."""

    package_root = find_package_root(package_dir)
    candidates = [
        package_root / "ncbi_dataset" / "data" / accession / "sequence_report.jsonl",
        package_root / "ncbi_dataset" / "data" / accession / f"{accession}_sequence_report.jsonl",
    ]
    report_path = next((path for path in candidates if path.is_file()), None)
    if report_path is None:
        return []

    records: list[dict[str, Any]] = []
    with report_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ContractError("sequence_report.jsonl contains a non-object JSON line")
            records.append(payload)
    return records


def build_allowed_primary_sequence_accessions(sequence_rows: list[dict[str, Any]]) -> set[str]:
    """Return the default primary-assembly accession allowlist from a sequence report."""

    allowed: set[str] = set()
    for row in sequence_rows:
        assembly_unit = str(row.get("assemblyUnit", ""))
        if assembly_unit not in {"Primary Assembly", "non-nuclear"}:
            continue
        for key in ("refseqAccession", "genbankAccession"):
            accession = str(row.get(key, "")).strip()
            if accession:
                allowed.add(accession)
    return allowed


def find_annotation_file(package_dir: Path | str, accession: str, *, kind: str) -> Path | None:
    """Locate one accession-specific annotation file by a broad pattern."""

    package_root = find_package_root(package_dir)
    data_dir = package_root / "ncbi_dataset" / "data"
    accession_dir = data_dir / accession
    search_root = accession_dir if accession_dir.is_dir() else data_dir

    if kind == "gff":
        patterns = ["**/*genomic.gff", "**/*.gff", "**/*.gff3"]
    elif kind == "cds":
        patterns = ["**/*cds*.fna", "**/*cds*.fa", "**/*.fna"]
    else:
        raise ValueError(f"Unsupported annotation file kind: {kind}")

    candidates: list[Path] = []
    for pattern in patterns:
        for path in search_root.glob(pattern):
            if accession in str(path.parent) or accession in path.name:
                candidates.append(path)
    if not candidates:
        return None
    return sorted(candidates)[0]
