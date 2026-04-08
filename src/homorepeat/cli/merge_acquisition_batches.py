#!/usr/bin/env python3
"""Merge validated batch-local acquisition outputs into canonical merged artifacts."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from homorepeat.acquisition.acquisition_validation import build_acquisition_validation_from_summary, write_validation_json  # noqa: E402
from homorepeat.io.fasta_io import iter_fasta, open_fasta_writer  # noqa: E402
from homorepeat.io.tsv_io import ContractError, iter_tsv, open_tsv_writer, read_tsv_fieldnames, write_tsv  # noqa: E402
from homorepeat.contracts.warnings import WARNING_FIELDNAMES  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-inputs",
        required=True,
        action="append",
        help="Batch-local normalized directory. Repeat for multiple batches.",
    )
    parser.add_argument("--outdir", required=True, help="Merged acquisition output directory")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument(
        "--strict-taxonomy-merge",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Hard-fail if two taxonomy rows with the same taxon_id disagree materially",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    batch_dirs = sorted({Path(path).resolve() for path in args.batch_inputs}, key=str)
    if not batch_dirs:
        raise ContractError("No batch inputs were provided")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    first_batch_dir = batch_dirs[0]
    genomes_fieldnames = read_tsv_fieldnames(first_batch_dir / "genomes.tsv")
    taxonomy_fieldnames = read_tsv_fieldnames(first_batch_dir / "taxonomy.tsv")
    sequences_fieldnames = read_tsv_fieldnames(first_batch_dir / "sequences.tsv")
    proteins_fieldnames = read_tsv_fieldnames(first_batch_dir / "proteins.tsv")
    download_manifest_fieldnames = read_tsv_fieldnames(first_batch_dir / "download_manifest.tsv")

    taxonomy_by_id: dict[str, dict[str, str]] = {}
    warning_summary: Counter[str] = Counter()
    seen_genome_ids: set[str] = set()
    seen_sequence_ids: set[str] = set()
    seen_protein_ids: set[str] = set()
    selected_accessions: set[str] = set()
    failed_accessions: list[str] = []
    n_downloaded_packages = 0
    n_genomes = 0
    n_sequences = 0
    n_proteins = 0
    n_warning_rows = 0
    manifest_rows_seen = False
    all_selected_accessions_accounted_for = True
    all_genomes_have_taxids = True
    all_proteins_belong_to_genomes = True
    all_retained_proteins_trace_to_cds = True

    with (
        open_tsv_writer(outdir / "genomes.tsv", fieldnames=genomes_fieldnames) as genomes_writer,
        open_tsv_writer(outdir / "sequences.tsv", fieldnames=sequences_fieldnames) as sequences_writer,
        open_tsv_writer(outdir / "proteins.tsv", fieldnames=proteins_fieldnames) as proteins_writer,
        open_tsv_writer(outdir / "download_manifest.tsv", fieldnames=download_manifest_fieldnames) as manifest_writer,
        open_tsv_writer(outdir / "normalization_warnings.tsv", fieldnames=WARNING_FIELDNAMES) as warnings_writer,
        open_fasta_writer(outdir / "cds.fna") as cds_writer,
        open_fasta_writer(outdir / "proteins.faa") as proteins_fasta_writer,
    ):
        for batch_dir in batch_dirs:
            for genome_row in iter_tsv(batch_dir / "genomes.tsv"):
                genome_id = genome_row.get("genome_id", "")
                _assert_new_key(genome_id, seen_genome_ids, "genomes.tsv", "genome_id")
                if not genome_row.get("taxon_id", ""):
                    all_genomes_have_taxids = False
                genomes_writer.write_row(genome_row)
                n_genomes += 1

            for sequence_row in iter_tsv(batch_dir / "sequences.tsv"):
                sequence_id = sequence_row.get("sequence_id", "")
                _assert_new_key(sequence_id, seen_sequence_ids, "sequences.tsv", "sequence_id")
                sequences_writer.write_row(sequence_row)
                n_sequences += 1

            for protein_row in iter_tsv(batch_dir / "proteins.tsv"):
                protein_id = protein_row.get("protein_id", "")
                _assert_new_key(protein_id, seen_protein_ids, "proteins.tsv", "protein_id")
                if protein_row.get("genome_id", "") not in seen_genome_ids:
                    all_proteins_belong_to_genomes = False
                if protein_row.get("sequence_id", "") not in seen_sequence_ids:
                    all_retained_proteins_trace_to_cds = False
                proteins_writer.write_row(protein_row)
                n_proteins += 1

            warnings_path = batch_dir / "normalization_warnings.tsv"
            if warnings_path.is_file():
                for warning_row in iter_tsv(warnings_path):
                    warning_code = warning_row.get("warning_code", "")
                    if (
                        warning_row.get("warning_scope", "") == "accession"
                        and warning_code in {
                            "accession_no_retained_proteins",
                            "accession_likely_translation_table_mismatch",
                            "accession_unsupported_translation_table",
                        }
                        and warning_row.get("assembly_accession", "")
                    ):
                        failed_accessions.append(warning_row["assembly_accession"])
                    if warning_code:
                        warning_summary[warning_code] += 1
                    warnings_writer.write_row(warning_row)
                    n_warning_rows += 1

            download_manifest_path = batch_dir / "download_manifest.tsv"
            if download_manifest_path.is_file():
                for manifest_row in iter_tsv(download_manifest_path):
                    manifest_rows_seen = True
                    assembly_accession = manifest_row.get("assembly_accession", "")
                    if assembly_accession:
                        selected_accessions.add(assembly_accession)
                    else:
                        all_selected_accessions_accounted_for = False
                    if manifest_row.get("download_status", "") in {"downloaded", "rehydrated"}:
                        n_downloaded_packages += 1
                    if manifest_row.get("download_status", "") == "failed" and assembly_accession:
                        failed_accessions.append(assembly_accession)
                    manifest_writer.write_row(manifest_row)

            cds_path = batch_dir / "cds.fna"
            if cds_path.is_file():
                for header, sequence in iter_fasta(cds_path):
                    cds_writer.write_record(header, sequence)

            proteins_faa_path = batch_dir / "proteins.faa"
            if proteins_faa_path.is_file():
                for header, sequence in iter_fasta(proteins_faa_path):
                    proteins_fasta_writer.write_record(header, sequence)

            for taxonomy_row in iter_tsv(batch_dir / "taxonomy.tsv"):
                taxon_id = taxonomy_row.get("taxon_id", "")
                if not taxon_id:
                    continue
                existing = taxonomy_by_id.get(taxon_id)
                if existing is None:
                    taxonomy_by_id[taxon_id] = taxonomy_row
                    continue
                if args.strict_taxonomy_merge and materially_differs(existing, taxonomy_row):
                    raise ContractError(f"Conflicting taxonomy rows found for taxon_id {taxon_id}")

    write_tsv(
        outdir / "taxonomy.tsv",
        [taxonomy_by_id[key] for key in sorted(taxonomy_by_id)],
        fieldnames=taxonomy_fieldnames,
    )

    validation_payload = build_acquisition_validation_from_summary(
        scope="merged",
        batch_id=None,
        n_selected_assemblies=len(selected_accessions),
        n_downloaded_packages=n_downloaded_packages,
        n_genomes=n_genomes,
        n_sequences=n_sequences,
        n_proteins=n_proteins,
        n_warning_rows=n_warning_rows,
        checks={
            "all_selected_accessions_accounted_for": manifest_rows_seen and all_selected_accessions_accounted_for,
            "all_genomes_have_taxids": all_genomes_have_taxids,
            "all_proteins_belong_to_genomes": all_proteins_belong_to_genomes,
            "all_retained_proteins_trace_to_cds": all_retained_proteins_trace_to_cds,
        },
        failed_accessions=failed_accessions,
        warning_summary=warning_summary,
    )
    write_validation_json(outdir / "acquisition_validation.json", validation_payload)
    return 0


def materially_differs(left: dict[str, str], right: dict[str, str]) -> bool:
    """Return whether two taxonomy rows disagree on stable values."""

    keys = {"taxon_name", "parent_taxon_id", "rank", "source"}
    return any((left.get(key, "") or "") != (right.get(key, "") or "") for key in keys)


def _assert_new_key(key: str, seen: set[str], label: str, key_name: str) -> None:
    if not key:
        return
    if key in seen:
        raise ContractError(f"{label} contains duplicate {key_name} values: {key}")
    seen.add(key)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
