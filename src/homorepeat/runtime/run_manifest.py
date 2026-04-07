"""Helpers for published run manifests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from homorepeat.io.tsv_io import ensure_directory


PUBLISHED_ARTIFACTS = {
    "acquisition": {
        "genomes_tsv": "acquisition/genomes.tsv",
        "taxonomy_tsv": "acquisition/taxonomy.tsv",
        "sequences_tsv": "acquisition/sequences.tsv",
        "proteins_tsv": "acquisition/proteins.tsv",
        "cds_fasta": "acquisition/cds.fna",
        "proteins_fasta": "acquisition/proteins.faa",
        "download_manifest_tsv": "acquisition/download_manifest.tsv",
        "normalization_warnings_tsv": "acquisition/normalization_warnings.tsv",
        "acquisition_validation_json": "acquisition/acquisition_validation.json",
    },
    "calls": {
        "repeat_calls_tsv": "calls/repeat_calls.tsv",
        "run_params_tsv": "calls/run_params.tsv",
    },
    "database": {
        "sqlite": "database/sqlite/homorepeat.sqlite",
        "sqlite_validation_json": "database/sqlite/sqlite_validation.json",
    },
    "reports": {
        "summary_by_taxon_tsv": "reports/summary_by_taxon.tsv",
        "regression_input_tsv": "reports/regression_input.tsv",
        "echarts_options_json": "reports/echarts_options.json",
        "echarts_report_html": "reports/echarts_report.html",
        "echarts_js": "reports/echarts.min.js",
        "nextflow_report_html": "reports/nextflow_report.html",
        "nextflow_timeline_html": "reports/nextflow_timeline.html",
        "nextflow_dag_html": "reports/nextflow_dag.html",
    },
    "internal": {
        "trace_txt": "internal/nextflow/trace.txt",
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
    nextflow_command: Path,
    started_at_utc: str,
    finished_at_utc: str,
    status: str,
) -> dict[str, object]:
    """Build a stable JSON payload describing one pipeline run."""

    return {
        "run_id": run_id,
        "status": status,
        "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc,
        "profile": profile,
        "git_revision": _git_revision(repo_root),
        "inputs": {
            "accessions_file": _relative_or_absolute(accessions_file, repo_root),
            "taxonomy_db": _relative_or_absolute(taxonomy_db, repo_root),
            "params_file": _relative_or_absolute(params_file, repo_root) if params_file else "",
        },
        "paths": {
            "run_root": _relative_or_absolute(run_root, repo_root),
            "publish_root": _relative_or_absolute(publish_root, repo_root),
            "nextflow_command": _relative_or_absolute(nextflow_command, repo_root),
        },
        "params": _manifest_params(publish_root=publish_root, params_file=params_file, run_root=run_root),
        "enabled_methods": _enabled_methods(publish_root),
        "repeat_residues": _repeat_residues(publish_root),
        "artifacts": _collect_artifacts(run_root=run_root, publish_root=publish_root),
    }


def write_run_manifest(path: Path | str, payload: dict[str, object]) -> None:
    """Write the run manifest JSON with stable formatting."""

    file_path = Path(path)
    ensure_directory(file_path)
    file_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _collect_artifacts(*, run_root: Path, publish_root: Path) -> dict[str, dict[str, str]]:
    artifacts: dict[str, dict[str, str]] = {}
    for section, files in PUBLISHED_ARTIFACTS.items():
        section_payload: dict[str, str] = {}
        for key, relative_path in files.items():
            base_root = run_root if section == "internal" else publish_root
            candidate = (base_root / relative_path).resolve()
            if candidate.exists():
                section_payload[key] = str(candidate.relative_to(run_root))
        artifacts[section] = section_payload
    return artifacts


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


def _manifest_params(*, publish_root: Path, params_file: Path | None, run_root: Path) -> dict[str, object]:
    payload: dict[str, object] = {
        "run_root": str(run_root.resolve()),
        "publish_root": str(publish_root.resolve()),
        "params_file_values": {},
        "detection": _read_method_params(publish_root),
    }
    if params_file and params_file.is_file():
        try:
            payload["params_file_values"] = json.loads(params_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload["params_file_values"] = {}
    return payload


def _enabled_methods(publish_root: Path) -> list[str]:
    return sorted(_read_method_params(publish_root).keys())


def _repeat_residues(publish_root: Path) -> list[str]:
    residues = {
        params.get("repeat_residue", "")
        for params in _read_method_params(publish_root).values()
        if params.get("repeat_residue", "")
    }
    return sorted(residues)


def _read_method_params(publish_root: Path) -> dict[str, dict[str, str]]:
    run_params_path = publish_root / "calls" / "run_params.tsv"
    if not run_params_path.is_file():
        return {}

    rows = _read_tsv_rows(run_params_path)
    payload: dict[str, dict[str, str]] = {}
    for row in rows:
        method = row.get("method", "")
        param_name = row.get("param_name", "")
        if not method or not param_name:
            continue
        payload.setdefault(method, {})[param_name] = row.get("param_value", "")
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
