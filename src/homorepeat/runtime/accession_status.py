"""Helpers for published per-accession pipeline status artifacts."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Sequence

from homorepeat.io.tsv_io import ContractError, read_tsv
from homorepeat.runtime.stage_status import read_stage_status


ACCESSION_STATUS_FIELDNAMES = [
    "assembly_accession",
    "batch_id",
    "download_status",
    "normalize_status",
    "translate_status",
    "detect_status",
    "finalize_status",
    "terminal_status",
    "failure_stage",
    "failure_reason",
    "n_genomes",
    "n_proteins",
    "n_repeat_calls",
    "notes",
]
ACCESSION_CALL_COUNTS_FIELDNAMES = [
    "assembly_accession",
    "batch_id",
    "method",
    "repeat_residue",
    "detect_status",
    "finalize_status",
    "n_repeat_calls",
]

BATCH_TABLE_REQUIRED = ["batch_id", "assembly_accession"]
DOWNLOAD_MANIFEST_REQUIRED = ["batch_id", "assembly_accession", "download_status", "notes"]
GENOMES_REQUIRED = ["genome_id", "accession"]
PROTEINS_REQUIRED = ["protein_id", "genome_id", "assembly_accession"]
SEQUENCES_REQUIRED = ["sequence_id", "assembly_accession"]
CALLS_REQUIRED = ["genome_id", "method", "repeat_residue"]

SUCCESSFUL_DOWNLOAD_STATUSES = {"downloaded", "rehydrated"}


def build_accession_status_rows(
    *,
    batch_table_rows: Sequence[dict[str, str]],
    batch_dirs: Sequence[Path],
    detect_status_paths: Sequence[Path],
    finalize_status_paths: Sequence[Path],
    call_tsv_paths: Sequence[Path],
) -> list[dict[str, object]]:
    """Build one published accession status row per requested accession."""

    batch_rows = list(batch_table_rows)
    batch_info_by_id = _load_batch_info(batch_dirs)
    detect_status_by_batch = _group_stage_status_by_batch(detect_status_paths)
    finalize_status_by_batch = _group_stage_status_by_batch(finalize_status_paths)
    accession_by_genome_id = _accession_by_genome_id(batch_info_by_id.values())
    repeat_calls_by_accession = _count_repeat_calls(call_tsv_paths, accession_by_genome_id)

    status_rows: list[dict[str, object]] = []
    for row in sorted(batch_rows, key=lambda item: (item.get("batch_id", ""), item.get("assembly_accession", ""))):
        batch_id = row.get("batch_id", "")
        accession = row.get("assembly_accession", "")
        batch_info = batch_info_by_id.get(batch_id, {})
        download_row = batch_info.get("download_rows_by_accession", {}).get(accession, {})
        n_genomes = int(batch_info.get("genome_counts_by_accession", {}).get(accession, 0))
        n_sequences = int(batch_info.get("sequence_counts_by_accession", {}).get(accession, 0))
        n_proteins = int(batch_info.get("protein_counts_by_accession", {}).get(accession, 0))
        n_repeat_calls = repeat_calls_by_accession.get(accession, 0)

        download_status = _download_status(download_row)
        normalize_status = _normalize_status(download_status, batch_info, accession, n_genomes, n_sequences)
        translate_status = _translate_status(normalize_status, batch_info, n_proteins)
        detect_status = _downstream_stage_status(
            translate_status,
            n_proteins,
            detect_status_by_batch.get(batch_id, []),
        )
        finalize_status = _finalize_stage_status(
            detect_status,
            n_repeat_calls,
            finalize_status_by_batch.get(batch_id, []),
        )

        failure_stage, failure_reason = _failure_details(
            download_status=download_status,
            normalize_status=normalize_status,
            translate_status=translate_status,
            detect_status=detect_status,
            finalize_status=finalize_status,
            download_row=download_row,
            batch_info=batch_info,
            detect_status_rows=detect_status_by_batch.get(batch_id, []),
            finalize_status_rows=finalize_status_by_batch.get(batch_id, []),
        )
        terminal_status = _terminal_status(
            download_status=download_status,
            normalize_status=normalize_status,
            translate_status=translate_status,
            detect_status=detect_status,
            finalize_status=finalize_status,
            n_repeat_calls=n_repeat_calls,
        )

        status_rows.append(
            {
                "assembly_accession": accession,
                "batch_id": batch_id,
                "download_status": download_status,
                "normalize_status": normalize_status,
                "translate_status": translate_status,
                "detect_status": detect_status,
                "finalize_status": finalize_status,
                "terminal_status": terminal_status,
                "failure_stage": failure_stage,
                "failure_reason": failure_reason,
                "n_genomes": n_genomes,
                "n_proteins": n_proteins,
                "n_repeat_calls": n_repeat_calls,
                "notes": str(download_row.get("notes", "")),
            }
        )
    return status_rows


def build_accession_call_count_rows(
    *,
    batch_table_rows: Sequence[dict[str, str]],
    batch_dirs: Sequence[Path],
    detect_status_paths: Sequence[Path],
    finalize_status_paths: Sequence[Path],
    call_tsv_paths: Sequence[Path],
) -> list[dict[str, object]]:
    """Build one published accession-method-residue status row per requested accession."""

    batch_rows = list(batch_table_rows)
    batch_info_by_id = _load_batch_info(batch_dirs)
    detect_status_by_key = _group_stage_status_by_batch_method_residue(detect_status_paths)
    finalize_status_by_key = _group_stage_status_by_batch_method_residue(finalize_status_paths)
    accession_by_genome_id = _accession_by_genome_id(batch_info_by_id.values())
    repeat_calls_by_key = _count_repeat_calls_by_accession_method_residue(call_tsv_paths, accession_by_genome_id)
    method_residue_pairs = _observed_method_residue_pairs(
        detect_status_paths=detect_status_paths,
        finalize_status_paths=finalize_status_paths,
        call_tsv_paths=call_tsv_paths,
    )

    count_rows: list[dict[str, object]] = []
    for row in sorted(batch_rows, key=lambda item: (item.get("batch_id", ""), item.get("assembly_accession", ""))):
        batch_id = row.get("batch_id", "")
        accession = row.get("assembly_accession", "")
        batch_info = batch_info_by_id.get(batch_id, {})
        download_row = batch_info.get("download_rows_by_accession", {}).get(accession, {})
        n_genomes = int(batch_info.get("genome_counts_by_accession", {}).get(accession, 0))
        n_sequences = int(batch_info.get("sequence_counts_by_accession", {}).get(accession, 0))
        n_proteins = int(batch_info.get("protein_counts_by_accession", {}).get(accession, 0))

        download_status = _download_status(download_row)
        normalize_status = _normalize_status(download_status, batch_info, accession, n_genomes, n_sequences)
        translate_status = _translate_status(normalize_status, batch_info, n_proteins)

        for method, repeat_residue in method_residue_pairs:
            detect_status = _downstream_stage_status(
                translate_status,
                n_proteins,
                detect_status_by_key.get((batch_id, method, repeat_residue), []),
            )
            n_method_repeat_calls = repeat_calls_by_key.get((accession, method, repeat_residue), 0)
            finalize_status = _finalize_stage_status(
                detect_status,
                n_method_repeat_calls,
                finalize_status_by_key.get((batch_id, method, repeat_residue), []),
            )
            count_rows.append(
                {
                    "assembly_accession": accession,
                    "batch_id": batch_id,
                    "method": method,
                    "repeat_residue": repeat_residue,
                    "detect_status": detect_status,
                    "finalize_status": finalize_status,
                    "n_repeat_calls": n_method_repeat_calls,
                }
            )
    return count_rows


def build_status_summary(status_rows: Sequence[dict[str, object]]) -> dict[str, object]:
    """Summarize one accession status table into a run-level payload."""

    terminal_counter = Counter(str(row.get("terminal_status", "")) for row in status_rows)
    overall_status = "success"
    if terminal_counter.get("failed", 0) or terminal_counter.get("skipped_upstream_failed", 0):
        overall_status = "partial"

    return {
        "status": overall_status,
        "counts": {
            "n_requested_accessions": len(status_rows),
            "n_completed": terminal_counter.get("completed", 0),
            "n_completed_no_calls": terminal_counter.get("completed_no_calls", 0),
            "n_failed": terminal_counter.get("failed", 0),
            "n_skipped_upstream_failed": terminal_counter.get("skipped_upstream_failed", 0),
        },
        "terminal_status_counts": dict(sorted(terminal_counter.items())),
    }


def _load_batch_info(batch_dirs: Sequence[Path]) -> dict[str, dict[str, object]]:
    payload: dict[str, dict[str, object]] = {}
    for batch_dir in batch_dirs:
        translate_status = _read_optional_stage_status(batch_dir / "translate_stage_status.json")
        batch_id = translate_status.get("batch_id", "") if translate_status else ""
        if not batch_id:
            continue

        download_rows = _read_optional_tsv(batch_dir / "download_manifest.tsv", DOWNLOAD_MANIFEST_REQUIRED)
        genomes_rows = _read_optional_tsv(batch_dir / "genomes.tsv", GENOMES_REQUIRED)
        sequences_rows = _read_optional_tsv(batch_dir / "sequences.tsv", SEQUENCES_REQUIRED)
        proteins_rows = _read_optional_tsv(batch_dir / "proteins.tsv", PROTEINS_REQUIRED)
        payload[batch_id] = {
            "download_stage_status": _read_optional_stage_status(batch_dir / "download_stage_status.json"),
            "normalize_stage_status": _read_optional_stage_status(batch_dir / "normalize_stage_status.json"),
            "translate_stage_status": translate_status,
            "download_rows_by_accession": {
                row.get("assembly_accession", ""): row for row in download_rows if row.get("assembly_accession", "")
            },
            "genome_counts_by_accession": Counter(row.get("accession", "") for row in genomes_rows if row.get("accession", "")),
            "sequence_counts_by_accession": Counter(
                row.get("assembly_accession", "") for row in sequences_rows if row.get("assembly_accession", "")
            ),
            "protein_counts_by_accession": Counter(
                row.get("assembly_accession", "") for row in proteins_rows if row.get("assembly_accession", "")
            ),
            "accession_by_genome_id": {
                row.get("genome_id", ""): row.get("accession", "")
                for row in genomes_rows
                if row.get("genome_id", "") and row.get("accession", "")
            },
        }
    return payload


def _group_stage_status_by_batch(paths: Sequence[Path]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for path in paths:
        row = read_stage_status(path)
        batch_id = row.get("batch_id", "")
        if batch_id:
            grouped[batch_id].append(row)
    return grouped


def _group_stage_status_by_batch_method_residue(paths: Sequence[Path]) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for path in paths:
        row = read_stage_status(path)
        batch_id = row.get("batch_id", "")
        method = row.get("method", "")
        repeat_residue = row.get("repeat_residue", "")
        if batch_id and method and repeat_residue:
            grouped[(batch_id, method, repeat_residue)].append(row)
    return grouped


def _accession_by_genome_id(batch_info_rows: Iterable[dict[str, object]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for batch_info in batch_info_rows:
        for genome_id, accession in batch_info.get("accession_by_genome_id", {}).items():
            if genome_id and accession:
                mapping[str(genome_id)] = str(accession)
    return mapping


def _count_repeat_calls(call_tsv_paths: Sequence[Path], accession_by_genome_id: dict[str, str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for path in call_tsv_paths:
        for row in _read_optional_tsv(path, CALLS_REQUIRED):
            accession = accession_by_genome_id.get(row.get("genome_id", ""))
            if accession:
                counts[accession] += 1
    return counts


def _count_repeat_calls_by_accession_method_residue(
    call_tsv_paths: Sequence[Path],
    accession_by_genome_id: dict[str, str],
) -> Counter[tuple[str, str, str]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    for path in call_tsv_paths:
        for row in _read_optional_tsv(path, CALLS_REQUIRED):
            accession = accession_by_genome_id.get(row.get("genome_id", ""))
            method = row.get("method", "")
            repeat_residue = row.get("repeat_residue", "")
            if accession and method and repeat_residue:
                counts[(accession, method, repeat_residue)] += 1
    return counts


def _observed_method_residue_pairs(
    *,
    detect_status_paths: Sequence[Path],
    finalize_status_paths: Sequence[Path],
    call_tsv_paths: Sequence[Path],
) -> list[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for path in [*detect_status_paths, *finalize_status_paths]:
        row = read_stage_status(path)
        method = row.get("method", "")
        repeat_residue = row.get("repeat_residue", "")
        if method and repeat_residue:
            pairs.add((method, repeat_residue))
    for path in call_tsv_paths:
        for row in _read_optional_tsv(path, CALLS_REQUIRED):
            method = row.get("method", "")
            repeat_residue = row.get("repeat_residue", "")
            if method and repeat_residue:
                pairs.add((method, repeat_residue))
    return sorted(pairs)


def _download_status(download_row: dict[str, str]) -> str:
    if download_row.get("download_status", "") in SUCCESSFUL_DOWNLOAD_STATUSES:
        return "success"
    return "failed"


def _normalize_status(
    download_status: str,
    batch_info: dict[str, object],
    accession: str,
    n_genomes: int,
    n_sequences: int,
) -> str:
    if download_status != "success":
        return "skipped_upstream_failed"
    stage_status = str(batch_info.get("normalize_stage_status", {}).get("status", ""))
    if stage_status == "failed":
        return "failed"
    return "success" if n_genomes > 0 and n_sequences > 0 else "failed"


def _translate_status(normalize_status: str, batch_info: dict[str, object], n_proteins: int) -> str:
    if normalize_status != "success":
        return "skipped_upstream_failed"
    stage_status = str(batch_info.get("translate_stage_status", {}).get("status", ""))
    if stage_status == "failed":
        return "failed"
    return "success" if n_proteins > 0 else "failed"


def _downstream_stage_status(
    translate_status: str,
    n_proteins: int,
    stage_rows: Sequence[dict[str, str]],
) -> str:
    if translate_status != "success":
        return "skipped_upstream_failed"
    if n_proteins == 0:
        return "skipped"
    if not stage_rows:
        return "failed"
    statuses = {row.get("status", "") for row in stage_rows}
    if "failed" in statuses:
        return "failed"
    if "success" in statuses:
        return "success"
    return "failed"


def _finalize_stage_status(
    detect_status: str,
    n_repeat_calls: int,
    stage_rows: Sequence[dict[str, str]],
) -> str:
    if detect_status == "failed":
        return "skipped_upstream_failed"
    if detect_status == "skipped_upstream_failed":
        return "skipped_upstream_failed"
    if detect_status == "skipped":
        return "skipped"
    if stage_rows:
        statuses = {row.get("status", "") for row in stage_rows}
        if "failed" in statuses:
            return "failed"
        if "success" in statuses:
            return "success"
        return "failed"
    if detect_status == "success" and n_repeat_calls == 0:
        return "skipped"
    return "failed"


def _failure_details(
    *,
    download_status: str,
    normalize_status: str,
    translate_status: str,
    detect_status: str,
    finalize_status: str,
    download_row: dict[str, str],
    batch_info: dict[str, object],
    detect_status_rows: Sequence[dict[str, str]],
    finalize_status_rows: Sequence[dict[str, str]],
) -> tuple[str, str]:
    if download_status == "failed":
        return ("download", str(download_row.get("notes", "")) or "download failed")
    if normalize_status == "failed":
        if not batch_info.get("sequence_counts_by_accession", {}).get(download_row.get("assembly_accession", ""), 0):
            return ("normalize", "no normalized CDS sequences produced for accession")
        return (
            "normalize",
            str(batch_info.get("normalize_stage_status", {}).get("message", "")) or "normalize failed",
        )
    if translate_status == "failed":
        if not batch_info.get("protein_counts_by_accession", {}).get(download_row.get("assembly_accession", ""), 0):
            return ("translate", "no retained proteins produced for accession")
        return (
            "translate",
            str(batch_info.get("translate_stage_status", {}).get("message", "")) or "translate failed",
        )
    if detect_status == "failed":
        return ("detect", _stage_failure_message(detect_status_rows) or "detect failed")
    if finalize_status == "failed":
        return ("finalize", _stage_failure_message(finalize_status_rows) or "finalize failed")
    return ("", "")


def _stage_failure_message(stage_rows: Sequence[dict[str, str]]) -> str:
    for row in stage_rows:
        if row.get("status", "") == "failed" and row.get("message", ""):
            return row["message"]
    return ""


def _terminal_status(
    *,
    download_status: str,
    normalize_status: str,
    translate_status: str,
    detect_status: str,
    finalize_status: str,
    n_repeat_calls: int,
) -> str:
    if "failed" in {download_status, normalize_status, translate_status, detect_status, finalize_status}:
        return "failed"
    if "skipped_upstream_failed" in {normalize_status, translate_status, detect_status, finalize_status}:
        return "skipped_upstream_failed"
    if n_repeat_calls > 0:
        return "completed"
    return "completed_no_calls"


def _read_optional_stage_status(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return read_stage_status(path)


def _read_optional_tsv(path: Path, required_columns: Sequence[str]) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        return read_tsv(path, required_columns=required_columns)
    except ContractError:
        return []
