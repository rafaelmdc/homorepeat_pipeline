"""Batch and merged acquisition validation helpers."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

from homorepeat.io.tsv_io import ensure_directory


def build_acquisition_validation(
    *,
    scope: str,
    batch_id: str | None,
    genomes_rows: list[dict[str, str]],
    sequences_rows: list[dict[str, str]],
    proteins_rows: list[dict[str, str]],
    warning_rows: list[dict[str, str]],
    download_manifest_rows: list[dict[str, str]],
) -> dict[str, object]:
    """Summarize acquisition validation state for one batch or merged output."""

    genome_ids = {row.get("genome_id", "") for row in genomes_rows}
    sequence_ids = {row.get("sequence_id", "") for row in sequences_rows}
    failed_accessions = [
        row.get("assembly_accession", "")
        for row in download_manifest_rows
        if row.get("download_status") == "failed" and row.get("assembly_accession", "")
    ]
    checks = {
        "all_selected_accessions_accounted_for": bool(download_manifest_rows)
        and all(row.get("assembly_accession", "") for row in download_manifest_rows),
        "all_genomes_have_taxids": all(row.get("taxon_id", "") for row in genomes_rows),
        "all_proteins_belong_to_genomes": all(row.get("genome_id", "") in genome_ids for row in proteins_rows),
        "all_retained_proteins_trace_to_cds": all(
            row.get("sequence_id", "") in sequence_ids for row in proteins_rows
        ),
    }
    warning_summary = dict(
        sorted(Counter(row.get("warning_code", "") for row in warning_rows if row.get("warning_code", "")).items())
    )
    payload = build_acquisition_validation_from_summary(
        scope=scope,
        batch_id=batch_id,
        n_selected_assemblies=len({row.get("assembly_accession", "") for row in download_manifest_rows}),
        n_downloaded_packages=sum(
            1 for row in download_manifest_rows if row.get("download_status") in {"downloaded", "rehydrated"}
        ),
        n_genomes=len(genomes_rows),
        n_sequences=len(sequences_rows),
        n_proteins=len(proteins_rows),
        n_warning_rows=len(warning_rows),
        checks=checks,
        failed_accessions=sorted(set(filter(None, failed_accessions))),
        warning_summary=warning_summary,
    )
    return payload


def build_acquisition_validation_from_summary(
    *,
    scope: str,
    batch_id: str | None,
    n_selected_assemblies: int,
    n_downloaded_packages: int,
    n_genomes: int,
    n_sequences: int,
    n_proteins: int,
    n_warning_rows: int,
    checks: Mapping[str, bool],
    failed_accessions: Sequence[str],
    warning_summary: Mapping[str, int],
) -> dict[str, object]:
    """Build stable validation payloads from already-computed summary state."""

    status = "pass"
    if not all(checks.values()):
        status = "fail"
    elif n_warning_rows or failed_accessions:
        status = "warn"

    payload: dict[str, object] = {
        "status": status,
        "scope": scope,
        "counts": {
            "n_selected_assemblies": n_selected_assemblies,
            "n_downloaded_packages": n_downloaded_packages,
            "n_genomes": n_genomes,
            "n_sequences": n_sequences,
            "n_proteins": n_proteins,
            "n_warning_rows": n_warning_rows,
        },
        "checks": dict(checks),
        "failed_accessions": sorted(set(filter(None, failed_accessions))),
        "warning_summary": dict(sorted((key, value) for key, value in warning_summary.items() if key)),
        "notes": [],
    }
    if batch_id is not None:
        payload["batch_id"] = batch_id
    return payload


def write_validation_json(path: Path | str, payload: dict[str, object]) -> None:
    """Write stable acquisition validation JSON."""

    file_path = Path(path)
    ensure_directory(file_path)
    file_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
