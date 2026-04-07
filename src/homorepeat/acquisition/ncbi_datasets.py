"""Small helpers for invoking and projecting NCBI Datasets genome summaries."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Iterable

from homorepeat.io.tsv_io import ensure_directory


class DatasetsCommandError(RuntimeError):
    """Raised when the `datasets` CLI exits unsuccessfully."""


DEFAULT_DATASETS_API_BASE_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2"


def summary_genome_taxon(
    taxon: str,
    *,
    api_key: str | None = None,
    datasets_bin: str = "datasets",
    max_attempts: int = 3,
    retry_delay_seconds: float = 5.0,
    api_base_url: str = DEFAULT_DATASETS_API_BASE_URL,
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
    try:
        return run_datasets_jsonl(
            command,
            api_key=api_key,
            datasets_bin=datasets_bin,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )
    except DatasetsCommandError as cli_error:
        request = {
            "taxons": [str(taxon)],
            "filters": _build_refseq_annotated_filters(),
            "page_size": 1000,
            "returned_content": "COMPLETE",
        }
        try:
            return rest_summary_genome_reports(
                request,
                api_key=api_key,
                api_base_url=api_base_url,
                max_attempts=max_attempts,
                retry_delay_seconds=retry_delay_seconds,
            )
        except DatasetsCommandError as rest_error:
            raise DatasetsCommandError(f"{cli_error}; REST fallback failed: {rest_error}") from rest_error


def summary_genome_accession(
    accession: str,
    *,
    api_key: str | None = None,
    datasets_bin: str = "datasets",
    max_attempts: int = 3,
    retry_delay_seconds: float = 5.0,
    api_base_url: str = DEFAULT_DATASETS_API_BASE_URL,
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
    try:
        return run_datasets_jsonl(
            command,
            api_key=api_key,
            datasets_bin=datasets_bin,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )
    except DatasetsCommandError as cli_error:
        request = {
            "accessions": [str(accession)],
            "filters": _build_refseq_annotated_filters(),
            "page_size": 1000,
            "returned_content": "COMPLETE",
        }
        try:
            return rest_summary_genome_reports(
                request,
                api_key=api_key,
                api_base_url=api_base_url,
                max_attempts=max_attempts,
                retry_delay_seconds=retry_delay_seconds,
            )
        except DatasetsCommandError as rest_error:
            raise DatasetsCommandError(f"{cli_error}; REST fallback failed: {rest_error}") from rest_error


def download_genome_batch(
    accessions_file: Path | str,
    output_zip: Path | str,
    *,
    include: str = "cds,gff3,seq-report",
    api_key: str | None = None,
    datasets_bin: str = "datasets",
    dehydrated: bool = False,
    max_attempts: int = 3,
    retry_delay_seconds: float = 5.0,
    api_base_url: str = DEFAULT_DATASETS_API_BASE_URL,
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
    try:
        run_datasets_command(
            command,
            api_key=api_key,
            datasets_bin=datasets_bin,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
            cleanup_paths=[output_zip],
        )
    except DatasetsCommandError as cli_error:
        try:
            download_genome_batch_via_rest(
                accessions_file,
                output_zip,
                include=include,
                api_key=api_key,
                dehydrated=dehydrated,
                api_base_url=api_base_url,
                max_attempts=max_attempts,
                retry_delay_seconds=retry_delay_seconds,
            )
        except DatasetsCommandError as rest_error:
            raise DatasetsCommandError(f"{cli_error}; REST fallback failed: {rest_error}") from rest_error


def rehydrate_package(
    package_dir: Path | str,
    *,
    api_key: str | None = None,
    datasets_bin: str = "datasets",
    max_workers: int | None = None,
    max_attempts: int = 3,
    retry_delay_seconds: float = 5.0,
) -> None:
    """Run ``datasets rehydrate`` against an extracted package directory."""

    command = ["rehydrate", "--directory", str(package_dir)]
    if max_workers is not None:
        command.extend(["--max-workers", str(max_workers)])
    run_datasets_command(
        command,
        api_key=api_key,
        datasets_bin=datasets_bin,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
    )


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
    max_attempts: int = 3,
    retry_delay_seconds: float = 5.0,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Run a `datasets` JSONL command and parse the returned objects."""

    command = [datasets_bin, *arguments]
    if api_key:
        command.extend(["--api-key", api_key])
    result = _run_datasets_subprocess(
        command,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
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
    max_attempts: int = 3,
    retry_delay_seconds: float = 5.0,
    cleanup_paths: Iterable[Path | str] = (),
) -> None:
    """Run a non-JSON ``datasets`` command and hard-fail on non-zero exit."""

    command = [datasets_bin, *arguments]
    if api_key:
        command.extend(["--api-key", api_key])
    result = _run_datasets_subprocess(
        command,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
        cleanup_paths=cleanup_paths,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "no stderr"
        raise DatasetsCommandError(f"datasets failed: {' '.join(command)} :: {stderr}")


def _run_datasets_subprocess(
    command: list[str],
    *,
    max_attempts: int,
    retry_delay_seconds: float,
    cleanup_paths: Iterable[Path | str] = (),
) -> subprocess.CompletedProcess[str]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if retry_delay_seconds < 0:
        raise ValueError("retry_delay_seconds must be non-negative")

    cleanup_targets = tuple(Path(path) for path in cleanup_paths)
    last_result: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, max_attempts + 1):
        _cleanup_retry_artifacts(cleanup_targets)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        last_result = result
        if result.returncode == 0:
            return result
        if attempt >= max_attempts or not _is_retryable_datasets_error(result.stderr):
            return result
        if retry_delay_seconds > 0:
            time.sleep(retry_delay_seconds)

    if last_result is None:
        raise DatasetsCommandError(f"datasets failed before executing: {' '.join(command)}")
    return last_result


def _is_retryable_datasets_error(stderr: str) -> bool:
    normalized = stderr.strip().lower()
    if not normalized:
        return False
    retryable_patterns = [
        "[gateway]",
        "giving up after",
        "timed out",
        "timeout",
        "temporary failure",
        "temporarily unavailable",
        "connection reset",
        "connection refused",
        "bad gateway",
        "service unavailable",
        "invalid zip archive",
        "502",
        "503",
        "504",
    ]
    return any(pattern in normalized for pattern in retryable_patterns)


def _cleanup_retry_artifacts(paths: Iterable[Path]) -> None:
    for path in paths:
        if not path.exists():
            continue
        if path.is_dir():
            continue
        path.unlink()


def download_genome_batch_via_rest(
    accessions_file: Path | str,
    output_zip: Path | str,
    *,
    include: str = "cds,gff3,seq-report",
    api_key: str | None = None,
    dehydrated: bool = False,
    api_base_url: str = DEFAULT_DATASETS_API_BASE_URL,
    max_attempts: int = 3,
    retry_delay_seconds: float = 5.0,
) -> None:
    """Download a genome package directly from the Datasets REST API."""

    request_body: dict[str, Any] = {
        "accessions": _read_accessions_file(accessions_file),
    }
    include_types = _map_include_annotation_types(include)
    if include_types:
        request_body["include_annotation_type"] = include_types
    if dehydrated:
        request_body["hydrated"] = "DATA_REPORT_ONLY"
    _request_rest_zip(
        "/genome/download",
        request_body,
        output_zip,
        api_key=api_key,
        api_base_url=api_base_url,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
    )


def rest_summary_genome_reports(
    request_body: dict[str, Any],
    *,
    api_key: str | None = None,
    api_base_url: str = DEFAULT_DATASETS_API_BASE_URL,
    max_attempts: int = 3,
    retry_delay_seconds: float = 5.0,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Retrieve genome assembly reports directly from the Datasets REST API."""

    records: list[dict[str, Any]] = []
    raw_lines: list[str] = []
    next_page_token = ""
    while True:
        page_request = dict(request_body)
        if next_page_token:
            page_request["page_token"] = next_page_token
        page = _request_rest_json(
            "/genome/dataset_report",
            page_request,
            api_key=api_key,
            api_base_url=api_base_url,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )
        reports = page.get("reports", [])
        if not isinstance(reports, list):
            raise DatasetsCommandError("REST fallback returned a non-list genome report payload")
        for report in reports:
            if not isinstance(report, dict):
                raise DatasetsCommandError("REST fallback returned a non-object genome report")
            records.append(report)
            raw_lines.append(json.dumps(report, sort_keys=True))
        next_page_token = str(page.get("next_page_token", "")).strip()
        if not next_page_token:
            break
    return records, raw_lines


def _request_rest_json(
    path: str,
    request_body: dict[str, Any],
    *,
    api_key: str | None = None,
    api_base_url: str = DEFAULT_DATASETS_API_BASE_URL,
    max_attempts: int = 3,
    retry_delay_seconds: float = 5.0,
) -> dict[str, Any]:
    response_bytes = _request_rest_bytes(
        path,
        request_body,
        accept="application/json",
        api_key=api_key,
        api_base_url=api_base_url,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
    )
    try:
        payload = json.loads(response_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetsCommandError("REST fallback returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise DatasetsCommandError("REST fallback returned a non-object JSON payload")
    return payload


def _request_rest_zip(
    path: str,
    request_body: dict[str, Any],
    output_zip: Path | str,
    *,
    api_key: str | None = None,
    api_base_url: str = DEFAULT_DATASETS_API_BASE_URL,
    max_attempts: int = 3,
    retry_delay_seconds: float = 5.0,
) -> None:
    archive_path = Path(output_zip)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = archive_path.with_name(f"{archive_path.name}.part")
    url = f"{_normalize_api_base_url(api_base_url)}{path}"
    payload = json.dumps(request_body).encode("utf-8")
    headers = _build_rest_headers(accept="application/zip", api_key=api_key)
    for attempt in range(1, max_attempts + 1):
        _cleanup_retry_artifacts([archive_path, temp_path])
        request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=600) as response, temp_path.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            temp_path.replace(archive_path)
            return
        except urllib.error.HTTPError as exc:
            error_payload = exc.read()
            if attempt < max_attempts and _is_retryable_rest_error(exc.code, error_payload):
                time.sleep(_compute_retry_delay(exc.headers, attempt, retry_delay_seconds))
                continue
            raise DatasetsCommandError(_format_rest_error(url, exc.code, error_payload)) from exc
        except urllib.error.URLError as exc:
            if attempt < max_attempts:
                time.sleep(max(retry_delay_seconds * attempt, retry_delay_seconds))
                continue
            raise DatasetsCommandError(f"REST fallback failed: POST {url} :: {exc.reason}") from exc
    raise DatasetsCommandError(f"REST fallback failed after {max_attempts} attempt(s): POST {url}")


def _request_rest_bytes(
    path: str,
    request_body: dict[str, Any],
    *,
    accept: str,
    api_key: str | None = None,
    api_base_url: str = DEFAULT_DATASETS_API_BASE_URL,
    max_attempts: int = 3,
    retry_delay_seconds: float = 5.0,
) -> bytes:
    url = f"{_normalize_api_base_url(api_base_url)}{path}"
    payload = json.dumps(request_body).encode("utf-8")
    headers = _build_rest_headers(accept=accept, api_key=api_key)
    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            error_payload = exc.read()
            if attempt < max_attempts and _is_retryable_rest_error(exc.code, error_payload):
                time.sleep(_compute_retry_delay(exc.headers, attempt, retry_delay_seconds))
                continue
            raise DatasetsCommandError(_format_rest_error(url, exc.code, error_payload)) from exc
        except urllib.error.URLError as exc:
            if attempt < max_attempts:
                time.sleep(max(retry_delay_seconds * attempt, retry_delay_seconds))
                continue
            raise DatasetsCommandError(f"REST fallback failed: POST {url} :: {exc.reason}") from exc
    raise DatasetsCommandError(f"REST fallback failed after {max_attempts} attempt(s): POST {url}")


def _build_rest_headers(*, accept: str, api_key: str | None) -> dict[str, str]:
    headers = {
        "accept": accept,
        "content-type": "application/json",
    }
    if api_key:
        headers["api-key"] = api_key
    return headers


def _normalize_api_base_url(api_base_url: str) -> str:
    return api_base_url.rstrip("/")


def _format_rest_error(url: str, status_code: int, payload: bytes) -> str:
    message = payload.decode("utf-8", errors="replace").strip() or "no response body"
    return f"REST fallback failed: POST {url} :: HTTP {status_code} :: {message}"


def _compute_retry_delay(headers: Any, attempt: int, retry_delay_seconds: float) -> float:
    retry_after = getattr(headers, "get", lambda _name, _default=None: None)("Retry-After")
    if retry_after is None:
        return max(retry_delay_seconds * attempt, retry_delay_seconds)
    try:
        return max(float(retry_after), retry_delay_seconds)
    except (TypeError, ValueError):
        return max(retry_delay_seconds * attempt, retry_delay_seconds)


def _is_retryable_rest_error(status_code: int, payload: bytes) -> bool:
    if status_code in {429, 500, 502, 503, 504}:
        return True
    message = payload.decode("utf-8", errors="replace").lower()
    retryable_patterns = [
        "too many requests",
        "gateway",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "temporary failure",
        "connection reset",
        "connection refused",
        "service unavailable",
    ]
    return any(pattern in message for pattern in retryable_patterns)


def _map_include_annotation_types(include: str) -> list[str]:
    include_tokens = [token.strip().lower() for token in include.split(",") if token.strip()]
    include_map = {
        "genome": "GENOME_FASTA",
        "rna": "RNA_FASTA",
        "protein": "PROT_FASTA",
        "cds": "CDS_FASTA",
        "gff3": "GENOME_GFF",
        "gtf": "GENOME_GTF",
        "gbff": "GENOME_GBFF",
        "seq-report": "SEQUENCE_REPORT",
    }
    if include_tokens == ["none"]:
        return []
    if include_tokens == ["all"]:
        return [
            "GENOME_FASTA",
            "RNA_FASTA",
            "PROT_FASTA",
            "CDS_FASTA",
            "GENOME_GFF",
            "GENOME_GTF",
            "GENOME_GBFF",
            "SEQUENCE_REPORT",
        ]
    try:
        return [include_map[token] for token in include_tokens]
    except KeyError as exc:
        raise DatasetsCommandError(f"Unsupported include token for REST fallback: {exc.args[0]}") from exc


def _read_accessions_file(accessions_file: Path | str) -> list[str]:
    accessions = [line.strip() for line in Path(accessions_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not accessions:
        raise DatasetsCommandError(f"Accessions file is empty: {accessions_file}")
    return accessions


def _build_refseq_annotated_filters() -> dict[str, Any]:
    return {
        "assembly_source": "refseq",
        "assembly_version": "current",
        "has_annotation": True,
    }


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
