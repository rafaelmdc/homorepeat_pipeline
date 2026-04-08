#!/usr/bin/env python3
"""Translate normalized CDS rows into retained canonical protein inputs."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from homorepeat.acquisition.acquisition_validation import (  # noqa: E402
    build_acquisition_validation,
    build_acquisition_validation_from_summary,
    write_validation_json,
)
from homorepeat.io.fasta_io import iter_fasta, write_fasta  # noqa: E402
from homorepeat.core.ids import text_id  # noqa: E402
from homorepeat.acquisition.translation import translate_cds as translate_sequence  # noqa: E402
from homorepeat.io.tsv_io import ContractError, iter_tsv, read_tsv, write_tsv  # noqa: E402
from homorepeat.contracts.warnings import WARNING_FIELDNAMES, build_warning_row  # noqa: E402
from homorepeat.runtime.stage_status import build_stage_status, write_stage_status  # noqa: E402


SEQUENCES_REQUIRED = ["sequence_id", "genome_id", "sequence_name", "sequence_length"]
PROTEINS_FIELDNAMES = [
    "protein_id",
    "sequence_id",
    "genome_id",
    "protein_name",
    "protein_length",
    "gene_symbol",
    "translation_method",
    "translation_status",
    "assembly_accession",
    "taxon_id",
    "gene_group",
    "protein_external_id",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences-tsv", required=True, help="Path to normalized sequences.tsv")
    parser.add_argument("--cds-fasta", required=True, help="Path to normalized cds.fna")
    parser.add_argument("--batch-id", required=True, help="Operational batch identifier")
    parser.add_argument("--outdir", required=True, help="Batch-local normalized output directory")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument("--warning-out", help="Optional explicit warning artifact path")
    parser.add_argument("--stage-status-out", help="Optional stage-status JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        _run(args)
    except Exception as exc:
        _write_failure_artifacts(args, str(exc))
        raise
    _write_stage_status_file(args, status="success")
    return 0


def _write_failure_artifacts(args: argparse.Namespace, message: str) -> None:
    try:
        _write_failed_outputs(args, message)
    except Exception:
        pass
    try:
        _write_stage_status_file(args, status="failed", message=message)
    except Exception:
        pass


def _run(args: argparse.Namespace) -> None:
    outdir = Path(args.outdir)
    warning_path = Path(args.warning_out) if args.warning_out else outdir / "normalization_warnings.tsv"
    protein_fasta_path = outdir / "proteins.faa"
    proteins_tsv_path = outdir / "proteins.tsv"

    sequences_by_id: dict[str, dict[str, str]] = {}
    sequence_ids: set[str] = set()
    sequence_accessions: set[str] = set()
    n_sequences = 0
    for row in iter_tsv(args.sequences_tsv, required_columns=SEQUENCES_REQUIRED):
        sequence_id = row.get("sequence_id", "")
        sequences_by_id[sequence_id] = row
        sequence_ids.add(sequence_id)
        assembly_accession = row.get("assembly_accession", "")
        if assembly_accession:
            sequence_accessions.add(assembly_accession)
        n_sequences += 1

    existing_warning_rows = read_tsv(warning_path) if warning_path.is_file() else []
    warning_rows = list(existing_warning_rows)
    translation_warning_rows: list[dict[str, object]] = []
    retained_by_gene: dict[tuple[str, str], dict[str, object]] = {}
    seen_cds_sequence_ids: set[str] = set()

    for sequence_id, cds_sequence in iter_fasta(args.cds_fasta):
        row = sequences_by_id.get(sequence_id)
        if row is None:
            continue
        seen_cds_sequence_ids.add(sequence_id)
        if row.get("partial_status", "") == "partial":
            warning_row = build_warning_row(
                "partial_cds",
                "sequence",
                "CDS is marked partial and is rejected before translation",
                batch_id=args.batch_id,
                genome_id=row.get("genome_id", ""),
                sequence_id=sequence_id,
                assembly_accession=row.get("assembly_accession", ""),
                source_record_id=row.get("source_record_id", ""),
            )
            warning_rows.append(warning_row)
            translation_warning_rows.append(warning_row)
            continue

        result = translate_sequence(cds_sequence, row.get("translation_table", "1"))
        if not result.accepted:
            warning_row = build_warning_row(
                result.warning_code,
                "sequence",
                result.warning_message,
                batch_id=args.batch_id,
                genome_id=row.get("genome_id", ""),
                sequence_id=sequence_id,
                assembly_accession=row.get("assembly_accession", ""),
                source_record_id=row.get("source_record_id", ""),
            )
            warning_rows.append(warning_row)
            translation_warning_rows.append(warning_row)
            continue

        protein_id = text_id(sequence_id, "protein")
        candidate = {
            "protein_id": protein_id,
            "sequence_id": sequence_id,
            "genome_id": row.get("genome_id", ""),
            "protein_name": row.get("protein_external_id", "") or row.get("sequence_name", ""),
            "protein_length": len(result.protein_sequence),
            "gene_symbol": row.get("gene_symbol", ""),
            "translation_method": "local_cds_translation",
            "translation_status": "translated",
            "assembly_accession": row.get("assembly_accession", ""),
            "taxon_id": row.get("taxon_id", ""),
            "gene_group": row.get("gene_group", "") or row.get("gene_symbol", "") or sequence_id,
            "protein_external_id": row.get("protein_external_id", ""),
            "_protein_sequence": result.protein_sequence,
        }
        gene_key = (str(candidate.get("genome_id", "")), str(candidate.get("gene_group", "")))
        winner = retained_by_gene.get(gene_key)
        if winner is None or _candidate_sort_key(candidate) < _candidate_sort_key(winner):
            retained_by_gene[gene_key] = candidate

    missing_sequence_ids = sorted(sequence_ids - seen_cds_sequence_ids)
    if missing_sequence_ids:
        raise ContractError(f"Normalized CDS FASTA is missing sequence_id {missing_sequence_ids[0]}")

    retained_rows = sorted(retained_by_gene.values(), key=lambda row: str(row.get("protein_id", "")))
    missing_accessions = _missing_translated_accessions(
        outdir / "download_manifest.tsv",
        sequence_accessions,
        retained_rows,
    )
    warning_rows.extend(_build_missing_accession_warning_rows(translation_warning_rows, missing_accessions, args.batch_id))
    write_tsv(
        proteins_tsv_path,
        [{field: row.get(field, "") for field in PROTEINS_FIELDNAMES} for row in retained_rows],
        fieldnames=PROTEINS_FIELDNAMES,
    )
    write_fasta(protein_fasta_path, [(row["protein_id"], row["_protein_sequence"]) for row in retained_rows])
    write_tsv(warning_path, warning_rows, fieldnames=WARNING_FIELDNAMES)

    genomes_rows = read_tsv(outdir / "genomes.tsv") if (outdir / "genomes.tsv").is_file() else []
    download_manifest_rows = (
        read_tsv(outdir / "download_manifest.tsv") if (outdir / "download_manifest.tsv").is_file() else []
    )
    genome_ids = {row.get("genome_id", "") for row in genomes_rows}
    failed_accessions = [
        row.get("assembly_accession", "")
        for row in download_manifest_rows
        if row.get("download_status") == "failed" and row.get("assembly_accession", "")
    ]
    failed_accessions.extend(missing_accessions)
    warning_summary = Counter(row.get("warning_code", "") for row in warning_rows if row.get("warning_code", ""))
    validation_payload = build_acquisition_validation_from_summary(
        scope="batch",
        batch_id=args.batch_id,
        n_selected_assemblies=len({row.get("assembly_accession", "") for row in download_manifest_rows}),
        n_downloaded_packages=sum(
            1 for row in download_manifest_rows if row.get("download_status") in {"downloaded", "rehydrated"}
        ),
        n_genomes=len(genomes_rows),
        n_sequences=n_sequences,
        n_proteins=len(retained_rows),
        n_warning_rows=len(warning_rows),
        checks={
            "all_selected_accessions_accounted_for": bool(download_manifest_rows)
            and all(row.get("assembly_accession", "") for row in download_manifest_rows),
            "all_genomes_have_taxids": all(row.get("taxon_id", "") for row in genomes_rows),
            "all_proteins_belong_to_genomes": all(row.get("genome_id", "") in genome_ids for row in retained_rows),
            "all_retained_proteins_trace_to_cds": all(row.get("sequence_id", "") in sequence_ids for row in retained_rows),
        },
        failed_accessions=failed_accessions,
        warning_summary=warning_summary,
    )
    if missing_accessions:
        validation_payload.setdefault("notes", []).append(
            "translate stage retained no proteins for accessions: " + ", ".join(sorted(missing_accessions))
        )
    write_validation_json(outdir / "acquisition_validation.json", validation_payload)
    if retained_rows:
        return
    raise ContractError(
        f"Batch {args.batch_id} produced no retained proteins for normalized accessions: {', '.join(sorted(missing_accessions))}"
    )


def _write_failed_outputs(args: argparse.Namespace, message: str) -> None:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    warning_path = Path(args.warning_out) if args.warning_out else outdir / "normalization_warnings.tsv"
    existing_warning_rows = read_tsv(warning_path) if warning_path.is_file() else []
    sequences_rows = (
        read_tsv(args.sequences_tsv, required_columns=SEQUENCES_REQUIRED)
        if Path(args.sequences_tsv).is_file()
        else []
    )
    genomes_rows = read_tsv(outdir / "genomes.tsv") if (outdir / "genomes.tsv").is_file() else []
    download_manifest_rows = (
        read_tsv(outdir / "download_manifest.tsv") if (outdir / "download_manifest.tsv").is_file() else []
    )

    write_tsv(outdir / "proteins.tsv", [], fieldnames=PROTEINS_FIELDNAMES)
    write_fasta(outdir / "proteins.faa", [])
    write_tsv(warning_path, existing_warning_rows, fieldnames=WARNING_FIELDNAMES)

    validation_payload = build_acquisition_validation(
        scope="batch",
        batch_id=args.batch_id,
        genomes_rows=genomes_rows,
        sequences_rows=sequences_rows,
        proteins_rows=[],
        warning_rows=existing_warning_rows,
        download_manifest_rows=download_manifest_rows,
    )
    accession_failures = sorted(
        {
            row.get("assembly_accession", "")
            for row in existing_warning_rows
            if row.get("warning_scope", "") == "accession" and row.get("assembly_accession", "")
        }
    )
    if accession_failures:
        validation_payload["failed_accessions"] = sorted(
            set(validation_payload.get("failed_accessions", [])) | set(accession_failures)
        )
    validation_payload["status"] = "fail"
    validation_payload.setdefault("notes", []).append(f"translate stage failed: {message}")
    write_validation_json(outdir / "acquisition_validation.json", validation_payload)


def _write_stage_status_file(args: argparse.Namespace, *, status: str, message: str = "") -> None:
    if not args.stage_status_out:
        return
    write_stage_status(
        args.stage_status_out,
        build_stage_status(
            stage="translate",
            status=status,
            batch_id=args.batch_id,
            message=message,
        ),
    )


def _candidate_sort_key(row: dict[str, object]) -> tuple[int, str]:
    return (-int(row.get("protein_length", 0)), str(row.get("protein_id", "")))


def _missing_translated_accessions(
    download_manifest_path: Path,
    sequence_accessions: set[str],
    retained_rows: list[dict[str, object]],
) -> list[str]:
    if download_manifest_path.is_file():
        expected_accessions = {
            row.get("assembly_accession", "")
            for row in read_tsv(
                download_manifest_path,
                required_columns=["assembly_accession", "download_status"],
            )
            if row.get("download_status", "") in {"downloaded", "rehydrated"} and row.get("assembly_accession", "")
        }
    else:
        expected_accessions = set(sequence_accessions)
    translated_accessions = {
        str(row.get("assembly_accession", ""))
        for row in retained_rows
        if str(row.get("assembly_accession", ""))
    }
    return sorted(expected_accessions - translated_accessions)


def _build_missing_accession_warning_rows(
    warning_rows: list[dict[str, object]],
    missing_accessions: list[str],
    batch_id: str,
) -> list[dict[str, object]]:
    warning_codes_by_accession: dict[str, Counter[str]] = {}
    for row in warning_rows:
        assembly_accession = row.get("assembly_accession", "")
        warning_code = row.get("warning_code", "")
        if not assembly_accession or not warning_code:
            continue
        warning_codes_by_accession.setdefault(assembly_accession, Counter())[warning_code] += 1

    payload: list[dict[str, object]] = []
    for accession in missing_accessions:
        warning_code = "accession_no_retained_proteins"
        warning_message = "No retained proteins were produced for this accession during translation"
        accession_warning_codes = warning_codes_by_accession.get(accession, Counter())
        if accession_warning_codes:
            if set(accession_warning_codes) == {"unsupported_translation_table"}:
                warning_code = "accession_unsupported_translation_table"
            elif "likely_translation_table_mismatch" in accession_warning_codes:
                warning_code = "accession_likely_translation_table_mismatch"
            detail = ", ".join(
                f"{code} x{count}"
                for code, count in sorted(accession_warning_codes.items())
            )
            warning_message = f"{warning_message} ({detail})"
        payload.append(
            build_warning_row(
                warning_code,
                "accession",
                warning_message,
                batch_id=batch_id,
                assembly_accession=accession,
            )
        )
    return payload


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
