"""Helpers for published run manifests."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from homorepeat.io.tsv_io import ensure_directory


CURRENT_PUBLISH_CONTRACT_VERSION = 1


MERGED_ACQUISITION_ARTIFACTS = {
    "genomes_tsv": "acquisition/genomes.tsv",
    "taxonomy_tsv": "acquisition/taxonomy.tsv",
    "sequences_tsv": "acquisition/sequences.tsv",
    "proteins_tsv": "acquisition/proteins.tsv",
    "cds_fasta": "acquisition/cds.fna",
    "proteins_fasta": "acquisition/proteins.faa",
    "download_manifest_tsv": "acquisition/download_manifest.tsv",
    "normalization_warnings_tsv": "acquisition/normalization_warnings.tsv",
    "acquisition_validation_json": "acquisition/acquisition_validation.json",
}

PUBLISHED_ARTIFACTS = {
    "calls": {
        "repeat_calls_tsv": "calls/repeat_calls.tsv",
        "run_params_tsv": "calls/run_params.tsv",
        "finalized_root": "calls/finalized",
    },
    "database": {
        "sqlite": "database/homorepeat.sqlite",
        "sqlite_validation_json": "database/sqlite_validation.json",
    },
    "reports": {
        "summary_by_taxon_tsv": "reports/summary_by_taxon.tsv",
        "regression_input_tsv": "reports/regression_input.tsv",
        "echarts_options_json": "reports/echarts_options.json",
        "echarts_report_html": "reports/echarts_report.html",
        "echarts_js": "reports/echarts.min.js",
    },
    "status": {
        "accession_status_tsv": "status/accession_status.tsv",
        "accession_call_counts_tsv": "status/accession_call_counts.tsv",
        "status_summary_json": "status/status_summary.json",
    },
    "tables": {
        "genomes_tsv": "tables/genomes.tsv",
        "taxonomy_tsv": "tables/taxonomy.tsv",
        "matched_sequences_tsv": "tables/matched_sequences.tsv",
        "matched_proteins_tsv": "tables/matched_proteins.tsv",
        "repeat_call_codon_usage_tsv": "tables/repeat_call_codon_usage.tsv",
        "repeat_context_tsv": "tables/repeat_context.tsv",
        "download_manifest_tsv": "tables/download_manifest.tsv",
        "normalization_warnings_tsv": "tables/normalization_warnings.tsv",
        "accession_status_tsv": "tables/accession_status.tsv",
        "accession_call_counts_tsv": "tables/accession_call_counts.tsv",
    },
    "summaries": {
        "status_summary_json": "summaries/status_summary.json",
        "acquisition_validation_json": "summaries/acquisition_validation.json",
    },
    "metadata": {
        "launch_metadata_json": "metadata/launch_metadata.json",
        "nextflow_report_html": "metadata/nextflow/report.html",
        "nextflow_timeline_html": "metadata/nextflow/timeline.html",
        "nextflow_dag_html": "metadata/nextflow/dag.html",
        "trace_txt": "metadata/nextflow/trace.txt",
    },
}


def build_run_manifest(
    *,
    repo_root: Path,
    run_id: str,
    run_root: Path,
    publish_root: Path,
    profile: str,
    accessions_file: Path,
    taxonomy_db: Path,
    params_file: Path | None,
    launch_metadata: Path,
    started_at_utc: str,
    finished_at_utc: str,
    status: str,
    acquisition_publish_mode: str,
    effective_params: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a stable JSON payload describing one pipeline run."""

    normalized_publish_mode = _normalize_acquisition_publish_mode(acquisition_publish_mode)
    return {
        "run_id": run_id,
        "status": status,
        "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc,
        "profile": profile,
        "publish_contract_version": CURRENT_PUBLISH_CONTRACT_VERSION,
        "acquisition_publish_mode": normalized_publish_mode,
        "git_revision": _git_revision(repo_root),
        "inputs": {
            "accessions_file": _relative_or_absolute(accessions_file, repo_root),
            "taxonomy_db": _relative_or_absolute(taxonomy_db, repo_root),
            "params_file": _relative_or_absolute(params_file, repo_root) if params_file else "",
        },
        "paths": {
            "run_root": _relative_or_absolute(run_root, repo_root),
            "publish_root": _relative_or_absolute(publish_root, repo_root),
        },
        "params": _manifest_params(
            publish_root=publish_root,
            params_file=params_file,
            run_root=run_root,
            effective_params=effective_params,
        ),
        "enabled_methods": _enabled_methods(publish_root),
        "repeat_residues": _repeat_residues(publish_root),
        "artifacts": _collect_artifacts(
            run_root=run_root,
            publish_root=publish_root,
            acquisition_publish_mode=normalized_publish_mode,
        ),
    }


def write_run_manifest(path: Path | str, payload: dict[str, object]) -> None:
    """Write the run manifest JSON with stable formatting."""

    file_path = Path(path)
    ensure_directory(file_path)
    file_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _collect_artifacts(
    *,
    run_root: Path,
    publish_root: Path,
    acquisition_publish_mode: str,
) -> dict[str, dict[str, str]]:
    artifacts: dict[str, dict[str, str]] = {}
    acquisition_payload: dict[str, str] = {}
    if acquisition_publish_mode == "raw":
        batches_root = publish_root / "acquisition" / "batches"
        if os.path.lexists(batches_root):
            acquisition_payload["batches_root"] = _relative_or_absolute(batches_root, run_root)
    else:
        for key, relative_path in MERGED_ACQUISITION_ARTIFACTS.items():
            candidate = publish_root / relative_path
            if os.path.lexists(candidate):
                acquisition_payload[key] = _relative_or_absolute(candidate, run_root)
    artifacts["acquisition"] = acquisition_payload

    for section, files in PUBLISHED_ARTIFACTS.items():
        section_payload: dict[str, str] = {}
        for key, relative_path in files.items():
            candidate = publish_root / relative_path
            if os.path.lexists(candidate):
                section_payload[key] = _relative_or_absolute(candidate, run_root)
        artifacts[section] = section_payload
    return artifacts


def _normalize_acquisition_publish_mode(mode: str) -> str:
    normalized = (mode or "raw").strip().lower()
    if normalized not in {"raw", "merged"}:
        raise ValueError("acquisition_publish_mode must be one of: raw, merged")
    return normalized


def _git_revision(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _manifest_params(
    *,
    publish_root: Path,
    params_file: Path | None,
    run_root: Path,
    effective_params: dict[str, object] | None,
) -> dict[str, object]:
    params_file_values: dict[str, object] = {}
    if params_file and params_file.is_file():
        try:
            params_file_values = json.loads(params_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            params_file_values = {}

    payload: dict[str, object] = {
        "run_root": str(run_root.resolve()),
        "publish_root": str(publish_root.resolve()),
        "params_file_values": params_file_values,
        "effective_values": effective_params if effective_params is not None else params_file_values,
        "detection": _read_method_params(publish_root),
    }
    return payload


def _enabled_methods(publish_root: Path) -> list[str]:
    return sorted(_read_method_params(publish_root).keys())


def _repeat_residues(publish_root: Path) -> list[str]:
    residues = {
        repeat_residue
        for method_payload in _read_method_params(publish_root).values()
        for repeat_residue in method_payload.keys()
        if repeat_residue
    }
    return sorted(residues)


def _read_method_params(publish_root: Path) -> dict[str, dict[str, dict[str, str]]]:
    run_params_path = publish_root / "calls" / "run_params.tsv"
    if not run_params_path.is_file():
        return {}

    rows = _read_tsv_rows(run_params_path)
    payload: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        method = row.get("method", "")
        repeat_residue = row.get("repeat_residue", "")
        param_name = row.get("param_name", "")
        if not method or not repeat_residue or not param_name:
            continue
        payload.setdefault(method, {}).setdefault(repeat_residue, {})[param_name] = row.get("param_value", "")
    return payload


def _read_tsv_rows(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        values = line.split("\t")
        rows.append({key: values[index] if index < len(values) else "" for index, key in enumerate(header)})
    return rows
