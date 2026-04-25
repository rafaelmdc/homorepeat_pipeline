"""Reducers for the additive publish-contract v2 table exports."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Sequence

from homorepeat.acquisition.acquisition_validation import build_acquisition_validation_from_summary, write_validation_json
from homorepeat.contracts.publish_contract_v2 import (
    ACCESSION_CALL_COUNTS_FIELDNAMES,
    ACCESSION_STATUS_FIELDNAMES,
    DOWNLOAD_MANIFEST_FIELDNAMES,
    GENOMES_FIELDNAMES,
    NORMALIZATION_WARNINGS_FIELDNAMES,
    TAXONOMY_FIELDNAMES,
    validate_accession_call_count_row,
    validate_accession_status_row,
    validate_download_manifest_row,
    validate_genome_row,
    validate_normalization_warning_row,
    validate_taxonomy_row,
)
from homorepeat.io.tsv_io import ContractError, iter_tsv, open_tsv_writer, read_tsv, write_tsv
from homorepeat.runtime.accession_status import BATCH_TABLE_REQUIRED


ACQUISITION_VALIDATION_COUNT_KEYS = (
    "n_selected_assemblies",
    "n_downloaded_packages",
    "n_genomes",
    "n_sequences",
    "n_proteins",
    "n_warning_rows",
)


def export_publish_tables(
    *,
    batch_table_rows: Sequence[dict[str, str]],
    batch_dirs: Sequence[Path],
    accession_status_tsv: Path,
    accession_call_counts_tsv: Path,
    status_summary_json: Path,
    outdir: Path,
    strict_taxonomy_merge: bool = True,
) -> None:
    """Export the additive v2 flat tables and summaries."""

    ordered_batch_ids = _ordered_batch_ids(batch_table_rows)
    batch_dir_by_id = _batch_dir_by_id(batch_dirs)
    missing_batch_ids = [batch_id for batch_id in ordered_batch_ids if batch_id not in batch_dir_by_id]
    if missing_batch_ids:
        raise ContractError(f"Missing batch export inputs for: {', '.join(missing_batch_ids)}")

    extra_batch_ids = sorted(set(batch_dir_by_id) - set(ordered_batch_ids))
    if extra_batch_ids:
        raise ContractError(f"Batch export inputs include unknown batch IDs: {', '.join(extra_batch_ids)}")

    tables_dir = outdir / "tables"
    summaries_dir = outdir / "summaries"
    taxonomy_by_id: dict[str, dict[str, str]] = {}
    acquisition_validation_payloads: list[dict[str, object]] = []

    with (
        open_tsv_writer(tables_dir / "genomes.tsv", fieldnames=GENOMES_FIELDNAMES) as genomes_writer,
        open_tsv_writer(tables_dir / "download_manifest.tsv", fieldnames=DOWNLOAD_MANIFEST_FIELDNAMES) as manifest_writer,
        open_tsv_writer(
            tables_dir / "normalization_warnings.tsv",
            fieldnames=NORMALIZATION_WARNINGS_FIELDNAMES,
        ) as warnings_writer,
    ):
        for batch_id in ordered_batch_ids:
            batch_dir = batch_dir_by_id[batch_id]

            for genome_row in iter_tsv(batch_dir / "genomes.tsv"):
                export_row = {
                    "batch_id": batch_id,
                    "genome_id": genome_row.get("genome_id", ""),
                    "source": genome_row.get("source", ""),
                    "accession": genome_row.get("accession", ""),
                    "genome_name": genome_row.get("genome_name", ""),
                    "assembly_type": genome_row.get("assembly_type", ""),
                    "taxon_id": genome_row.get("taxon_id", ""),
                    "assembly_level": genome_row.get("assembly_level", ""),
                    "species_name": genome_row.get("species_name", ""),
                    "notes": genome_row.get("notes", ""),
                }
                validate_genome_row(export_row)
                genomes_writer.write_row(export_row)

            for taxonomy_row in iter_tsv(batch_dir / "taxonomy.tsv"):
                validate_taxonomy_row(taxonomy_row)
                taxon_id = taxonomy_row.get("taxon_id", "")
                if not taxon_id:
                    continue
                existing = taxonomy_by_id.get(taxon_id)
                if existing is None:
                    taxonomy_by_id[taxon_id] = dict(taxonomy_row)
                    continue
                if strict_taxonomy_merge and _taxonomy_rows_materially_differ(existing, taxonomy_row):
                    raise ContractError(f"Conflicting taxonomy rows found for taxon_id {taxon_id}")

            for manifest_row in iter_tsv(batch_dir / "download_manifest.tsv"):
                validate_download_manifest_row(manifest_row)
                manifest_writer.write_row(manifest_row)

            for warning_row in iter_tsv(batch_dir / "normalization_warnings.tsv"):
                validate_normalization_warning_row(warning_row)
                warnings_writer.write_row(warning_row)

            validation_path = batch_dir / "acquisition_validation.json"
            if validation_path.is_file():
                acquisition_validation_payloads.append(_read_json_payload(validation_path))

    write_tsv(
        tables_dir / "taxonomy.tsv",
        [taxonomy_by_id[taxon_id] for taxon_id in sorted(taxonomy_by_id)],
        fieldnames=TAXONOMY_FIELDNAMES,
    )

    _stream_validated_table(
        accession_status_tsv,
        tables_dir / "accession_status.tsv",
        fieldnames=ACCESSION_STATUS_FIELDNAMES,
        validate_row=validate_accession_status_row,
    )
    _stream_validated_table(
        accession_call_counts_tsv,
        tables_dir / "accession_call_counts.tsv",
        fieldnames=ACCESSION_CALL_COUNTS_FIELDNAMES,
        validate_row=validate_accession_call_count_row,
    )

    status_summary_payload = _read_json_payload(status_summary_json)
    summaries_dir.mkdir(parents=True, exist_ok=True)
    (summaries_dir / "status_summary.json").write_text(
        json.dumps(status_summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if acquisition_validation_payloads:
        write_validation_json(
            summaries_dir / "acquisition_validation.json",
            merge_acquisition_validation_payloads(acquisition_validation_payloads),
        )


def merge_acquisition_validation_payloads(payloads: Sequence[dict[str, object]]) -> dict[str, object]:
    """Merge batch-scoped acquisition validations into one run-scoped payload."""

    if not payloads:
        raise ContractError("No acquisition validation payloads were provided")

    counts = Counter()
    warning_summary = Counter()
    failed_accessions: set[str] = set()
    check_names = sorted(
        {
            str(check_name)
            for payload in payloads
            for check_name in dict(payload.get("checks", {})).keys()
            if str(check_name)
        }
    )

    for payload in payloads:
        payload_counts = dict(payload.get("counts", {}))
        for key in ACQUISITION_VALIDATION_COUNT_KEYS:
            counts[key] += _coerce_int(payload_counts.get(key, 0), label=f"acquisition_validation.{key}")

        payload_warning_summary = dict(payload.get("warning_summary", {}))
        for warning_code, count in payload_warning_summary.items():
            warning_key = str(warning_code).strip()
            if warning_key:
                warning_summary[warning_key] += _coerce_int(count, label=f"warning_summary.{warning_key}")

        for accession in payload.get("failed_accessions", []) or []:
            accession_text = str(accession).strip()
            if accession_text:
                failed_accessions.add(accession_text)

    checks = {
        check_name: all(bool(dict(payload.get("checks", {})).get(check_name, False)) for payload in payloads)
        for check_name in check_names
    }

    return build_acquisition_validation_from_summary(
        scope="merged",
        batch_id=None,
        n_selected_assemblies=counts["n_selected_assemblies"],
        n_downloaded_packages=counts["n_downloaded_packages"],
        n_genomes=counts["n_genomes"],
        n_sequences=counts["n_sequences"],
        n_proteins=counts["n_proteins"],
        n_warning_rows=counts["n_warning_rows"],
        checks=checks,
        failed_accessions=sorted(failed_accessions),
        warning_summary=dict(sorted(warning_summary.items())),
    )


def read_batch_table(path: Path | str) -> list[dict[str, str]]:
    """Read the canonical batch table used to order export inputs."""

    return read_tsv(path, required_columns=BATCH_TABLE_REQUIRED)


def _stream_validated_table(path: Path, outpath: Path, *, fieldnames: Sequence[str], validate_row) -> None:
    with open_tsv_writer(outpath, fieldnames=fieldnames) as writer:
        for row in iter_tsv(path, required_columns=fieldnames):
            validate_row(row)
            writer.write_row(row)


def _ordered_batch_ids(batch_table_rows: Sequence[dict[str, str]]) -> list[str]:
    ordered_batch_ids: list[str] = []
    seen: set[str] = set()
    for row in batch_table_rows:
        batch_id = str(row.get("batch_id", "")).strip()
        if not batch_id:
            raise ContractError("batch_table contains an empty batch_id")
        if batch_id in seen:
            continue
        ordered_batch_ids.append(batch_id)
        seen.add(batch_id)
    return ordered_batch_ids


def _batch_dir_by_id(batch_dirs: Sequence[Path]) -> dict[str, Path]:
    payload: dict[str, Path] = {}
    for batch_dir in batch_dirs:
        batch_id = batch_dir.name.strip()
        if not batch_id:
            raise ContractError(f"Cannot infer batch_id from batch export directory: {batch_dir}")
        if batch_id in payload:
            raise ContractError(f"Duplicate batch export directory for batch_id {batch_id}")
        payload[batch_id] = batch_dir
    return payload


def _taxonomy_rows_materially_differ(left: dict[str, str], right: dict[str, str]) -> bool:
    keys = {"taxon_name", "parent_taxon_id", "rank", "source"}
    return any((left.get(key, "") or "") != (right.get(key, "") or "") for key in keys)


def _read_json_payload(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"Invalid JSON payload: {path}") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"Expected a JSON object in {path}")
    return payload


def _coerce_int(value: object, *, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"Invalid integer value for {label}: {value!r}") from exc
