"""Small helpers for invoking and projecting NCBI Datasets genome summaries."""

from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from homorepeat.io.tsv_io import ensure_directory


class DatasetsCommandError(RuntimeError):
    """Raised when the `datasets` CLI exits unsuccessfully."""


def summary_genome_taxon(
    taxon: str,
    *,
    api_key: str | None = None,
    datasets_bin: str = "datasets",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Query genome metadata by taxon using the Datasets CLI."""

    command = [
        "summary",
        "genome",
        "taxon",
        str(taxon),
        "--annotated",
        "--assembly-source",
        "RefSeq",
        "--assembly-version",
        "latest",
        "--as-json-lines",
    ]
    return run_datasets_jsonl(command, api_key=api_key, datasets_bin=datasets_bin)


def summary_genome_accession(
    accession: str,
    *,
    api_key: str | None = None,
    datasets_bin: str = "datasets",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Query genome metadata by assembly accession using the Datasets CLI."""

    command = [
        "summary",
        "genome",
        "accession",
        str(accession),
        "--annotated",
        "--assembly-source",
        "RefSeq",
        "--assembly-version",
        "latest",
        "--as-json-lines",
    ]
    return run_datasets_jsonl(command, api_key=api_key, datasets_bin=datasets_bin)


def download_genome_batch(
    accessions_file: Path | str,
    output_zip: Path | str,
    *,
    include: str = "cds,gff3,seq-report",
    api_key: str | None = None,
    datasets_bin: str = "datasets",
    dehydrated: bool = False,
) -> None:
    """Run ``datasets download genome accession`` for one batch."""

    command = [
        "download",
        "genome",
        "accession",
        "--inputfile",
        str(accessions_file),
        "--include",
        include,
        "--filename",
        str(output_zip),
    ]
    if dehydrated:
        command.append("--dehydrated")
    run_datasets_command(command, api_key=api_key, datasets_bin=datasets_bin)


def rehydrate_package(
    package_dir: Path | str,
    *,
    api_key: str | None = None,
    datasets_bin: str = "datasets",
    max_workers: int | None = None,
) -> None:
    """Run ``datasets rehydrate`` against an extracted package directory."""

    command = ["rehydrate", "--directory", str(package_dir)]
    if max_workers is not None:
        command.extend(["--max-workers", str(max_workers)])
    run_datasets_command(command, api_key=api_key, datasets_bin=datasets_bin)


def unzip_package(zip_path: Path | str, output_dir: Path | str) -> None:
    """Extract a downloaded package zip."""

    archive_path = Path(zip_path)
    destination = Path(output_dir)
    ensure_directory(destination / ".keep")
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(destination)


def run_datasets_jsonl(
    arguments: list[str],
    *,
    api_key: str | None = None,
    datasets_bin: str = "datasets",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Run a `datasets` JSONL command and parse the returned objects."""

    command = [datasets_bin, *arguments]
    if api_key:
        command.extend(["--api-key", api_key])
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "no stderr"
        raise DatasetsCommandError(f"datasets failed: {' '.join(command)} :: {stderr}")

    raw_lines = [line for line in result.stdout.splitlines() if line.strip()]
    records: list[dict[str, Any]] = []
    for line in raw_lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetsCommandError("datasets returned invalid JSON Lines output") from exc
        if not isinstance(payload, dict):
            raise DatasetsCommandError("datasets returned a non-object JSON line")
        records.append(payload)
    return records, raw_lines


def run_datasets_command(
    arguments: list[str],
    *,
    api_key: str | None = None,
    datasets_bin: str = "datasets",
) -> None:
    """Run a non-JSON ``datasets`` command and hard-fail on non-zero exit."""

    command = [datasets_bin, *arguments]
    if api_key:
        command.extend(["--api-key", api_key])
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "no stderr"
        raise DatasetsCommandError(f"datasets failed: {' '.join(command)} :: {stderr}")


def project_assembly_record(
    request_row: dict[str, str],
    record: dict[str, Any],
) -> dict[str, str]:
    """Project one assembly report into the planning inventory contract."""

    assembly_info = _mapping(_get(record, "assemblyInfo", "assembly_info"))
    annotation_info = _mapping(_get(record, "annotationInfo", "annotation_info"))
    organism = _mapping(record.get("organism"))

    accession = _text(record.get("accession"))
    current_accession = _text(_get(record, "currentAccession", "current_accession")) or accession
    taxid = _text(_get(organism, "taxId", "tax_id"))
    return {
        "request_id": request_row.get("request_id", ""),
        "resolved_taxid": request_row.get("matched_taxid", ""),
        "resolved_name": request_row.get("matched_name", "") or request_row.get("normalized_input", ""),
        "assembly_accession": accession,
        "current_accession": current_accession,
        "source_database": _normalize_source_database(_get(record, "sourceDatabase", "source_database")),
        "assembly_level": _text(_get(assembly_info, "assemblyLevel", "assembly_level")),
        "assembly_type": _text(_get(assembly_info, "assemblyType", "assembly_type")),
        "assembly_status": _text(_get(assembly_info, "assemblyStatus", "assembly_status")),
        "refseq_category": _text(_get(assembly_info, "refseqCategory", "refseq_category")),
        "annotation_status": _annotation_status(annotation_info),
        "organism_name": _text(_get(organism, "organismName", "organism_name")),
        "taxid": taxid,
        "selection_decision": "pending",
        "selection_reason": "",
        "request_input_type": request_row.get("input_type", ""),
    }


def build_no_candidate_row(request_row: dict[str, str]) -> dict[str, str]:
    """Create an auditable placeholder when no assemblies are returned."""

    return {
        "request_id": request_row.get("request_id", ""),
        "resolved_taxid": request_row.get("matched_taxid", ""),
        "resolved_name": request_row.get("matched_name", "") or request_row.get("normalized_input", ""),
        "assembly_accession": "",
        "current_accession": "",
        "source_database": "REFSEQ",
        "assembly_level": "",
        "assembly_type": "",
        "assembly_status": "",
        "refseq_category": "",
        "annotation_status": "not_found",
        "organism_name": "",
        "taxid": request_row.get("matched_taxid", ""),
        "selection_decision": "excluded",
        "selection_reason": "no_candidate_assemblies_returned",
        "request_input_type": request_row.get("input_type", ""),
    }


def _annotation_status(annotation_info: dict[str, Any]) -> str:
    if not annotation_info:
        return "not_annotated"
    status = _text(annotation_info.get("status"))
    if status:
        return f"annotated:{status}"
    return "annotated"


def _normalize_source_database(value: Any) -> str:
    text = _text(value)
    if text.startswith("SOURCE_DATABASE_"):
        return text.removeprefix("SOURCE_DATABASE_")
    return text


def _get(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
