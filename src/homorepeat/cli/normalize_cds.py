#!/usr/bin/env python3
"""Normalize one extracted NCBI package into canonical CDS acquisition outputs."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from homorepeat.io.fasta_io import (  # noqa: E402
    extract_ncbi_molecule_accession,
    parse_ncbi_fasta_header,
    read_fasta,
    write_fasta,
)
from homorepeat.acquisition.gff_norm import first_nonempty, build_gff_index, resolve_linkage  # noqa: E402
from homorepeat.core.ids import stable_id  # noqa: E402
from homorepeat.acquisition.package_layout import (  # noqa: E402
    build_allowed_primary_sequence_accessions,
    find_annotation_file,
    find_package_root,
    load_assembly_report,
    load_sequence_report,
)
from homorepeat.taxonomy.ncbi import build_taxonomy_rows, get_build_version, inspect_lineage  # noqa: E402
from homorepeat.io.tsv_io import ContractError, write_tsv  # noqa: E402
from homorepeat.contracts.warnings import WARNING_FIELDNAMES, build_warning_row  # noqa: E402


GENOMES_FIELDNAMES = [
    "genome_id",
    "source",
    "accession",
    "genome_name",
    "assembly_type",
    "taxon_id",
    "assembly_level",
    "species_name",
    "download_path",
    "notes",
]
TAXONOMY_FIELDNAMES = ["taxon_id", "taxon_name", "parent_taxon_id", "rank", "source"]
SEQUENCES_FIELDNAMES = [
    "sequence_id",
    "genome_id",
    "sequence_name",
    "sequence_length",
    "sequence_path",
    "gene_symbol",
    "transcript_id",
    "isoform_id",
    "assembly_accession",
    "taxon_id",
    "source_record_id",
    "protein_external_id",
    "translation_table",
    "gene_group",
    "linkage_status",
    "partial_status",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True, help="Extracted package directory")
    parser.add_argument("--taxonomy-db", required=True, help="Path to the taxon-weaver SQLite DB")
    parser.add_argument("--batch-id", required=True, help="Operational batch identifier")
    parser.add_argument("--outdir", required=True, help="Batch-local normalized output directory")
    parser.add_argument("--log-file", help="Reserved log file path")
    parser.add_argument("--warning-out", help="Optional explicit warning artifact path")
    parser.add_argument(
        "--taxon-weaver-bin",
        default="taxon-weaver",
        help="Path to the taxon-weaver executable",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package_root = find_package_root(args.package_dir)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    warning_path = Path(args.warning_out) if args.warning_out else outdir / "normalization_warnings.tsv"
    normalized_cds_path = outdir / "cds.fna"
    taxonomy_build_version = get_build_version(
        args.taxonomy_db,
        taxon_weaver_bin=args.taxon_weaver_bin,
    )

    genomes_rows: list[dict[str, object]] = []
    taxonomy_rows_by_id: dict[str, dict[str, object]] = {}
    sequences_rows: list[dict[str, object]] = []
    warnings_rows: list[dict[str, object]] = []
    normalized_cds_records: list[tuple[str, str]] = []
    lineage_cache: dict[str, list[dict[str, object]]] = {}
    seen_sequence_rows: dict[str, dict[str, object]] = {}
    seen_cds_sequences: dict[str, str] = {}
    seen_source_sequences: dict[str, str] = {}

    for record in load_assembly_report(package_root):
        assembly_info = record.get("assemblyInfo", {}) if isinstance(record.get("assemblyInfo"), dict) else {}
        organism = record.get("organism", {}) if isinstance(record.get("organism"), dict) else {}
        accession = str(record.get("accession", ""))
        taxon_id = str(organism.get("taxId", ""))
        genome_id = stable_id("genome", accession, taxon_id)
        genomes_rows.append(
            {
                "genome_id": genome_id,
                "source": "ncbi_datasets",
                "accession": accession,
                "genome_name": first_nonempty(str(organism.get("organismName", "")), accession),
                "assembly_type": str(assembly_info.get("assemblyType", "")),
                "taxon_id": taxon_id,
                "assembly_level": str(assembly_info.get("assemblyLevel", "")),
                "species_name": str(organism.get("organismName", "")),
                "download_path": str(package_root.resolve()),
                "notes": "",
            }
        )
        if taxon_id:
            lineage = lineage_cache.get(taxon_id)
            if lineage is None:
                lineage = inspect_lineage(
                    int(taxon_id),
                    args.taxonomy_db,
                    taxon_weaver_bin=args.taxon_weaver_bin,
                )
                lineage_cache[taxon_id] = lineage
            if not lineage:
                raise ContractError(
                    f"taxon-weaver returned an empty lineage for taxid {taxon_id} while normalizing {accession}"
                )
            for taxonomy_row in build_taxonomy_rows(
                lineage,
                taxonomy_build_version=taxonomy_build_version,
            ):
                row_taxon_id = str(taxonomy_row.get("taxon_id", ""))
                if row_taxon_id:
                    taxonomy_rows_by_id[row_taxon_id] = taxonomy_row

        gff_path = find_annotation_file(package_root, accession, kind="gff")
        cds_path = find_annotation_file(package_root, accession, kind="cds")
        if gff_path is None or cds_path is None:
            warnings_rows.append(
                build_warning_row(
                    "missing_annotation_component",
                    "genome",
                    "Required annotation files are missing for selected assembly",
                    batch_id=args.batch_id,
                    genome_id=genome_id,
                    assembly_accession=accession,
                    source_file=str((gff_path or cds_path or package_root).resolve()),
                )
            )
            continue

        sequence_report_rows = load_sequence_report(package_root, accession)
        allowed_sequence_accessions = build_allowed_primary_sequence_accessions(sequence_report_rows)
        gff_index = build_gff_index(
            gff_path,
            allowed_sequence_accessions=allowed_sequence_accessions or None,
        )
        for header, sequence in read_fasta(cds_path):
            metadata = parse_ncbi_fasta_header(header)
            molecule_accession = extract_ncbi_molecule_accession(metadata.get("record_id", ""))
            if (
                allowed_sequence_accessions
                and molecule_accession
                and molecule_accession not in allowed_sequence_accessions
            ):
                continue
            linkage = resolve_linkage(metadata, gff_index)
            if linkage is None:
                warnings_rows.append(
                    build_warning_row(
                        "unresolved_linkage",
                        "sequence",
                        "Falling back to CDS FASTA header linkage because GFF mapping was not found",
                        batch_id=args.batch_id,
                        genome_id=genome_id,
                        assembly_accession=accession,
                        source_file=str(cds_path.resolve()),
                        source_record_id=metadata.get("record_id", ""),
                    )
                )
                gene_symbol = metadata.get("gene", "")
                transcript_id = metadata.get("transcript_id", "")
                protein_external_id = metadata.get("protein_id", "")
                translation_table = metadata.get("transl_table", "") or "1"
                source_record_id = metadata.get("record_id", "")
                partial_status = "partial" if metadata.get("partial", "").lower() == "true" else ""
                linkage_status = "header_fallback"
            else:
                gene_symbol = linkage.gene_symbol
                transcript_id = linkage.transcript_id
                protein_external_id = linkage.protein_external_id
                translation_table = linkage.translation_table or "1"
                source_record_id = linkage.source_record_id or metadata.get("record_id", "")
                partial_status = linkage.partial_status
                linkage_status = linkage.match_source
                if metadata.get("transcript_id") and metadata.get("transcript_id") != transcript_id:
                    warnings_rows.append(
                        build_warning_row(
                            "gff_fasta_disagreement",
                            "sequence",
                            "GFF transcript linkage disagrees with CDS FASTA header metadata",
                            batch_id=args.batch_id,
                            genome_id=genome_id,
                            assembly_accession=accession,
                            source_file=str(cds_path.resolve()),
                            source_record_id=metadata.get("record_id", ""),
                        )
                    )

            stable_key = first_nonempty(transcript_id, source_record_id, metadata.get("record_id", ""), header)
            source_sequence_key = stable_id("source_seq", accession, stable_key)
            previous_source_sequence = seen_source_sequences.get(source_sequence_key)
            sequence_id = stable_id("seq", accession, stable_key, sequence)
            gene_group = first_nonempty(gene_symbol, transcript_id, sequence_id)
            sequence_name = first_nonempty(transcript_id, source_record_id, metadata.get("record_id", ""))
            candidate_row = {
                "sequence_id": sequence_id,
                "genome_id": genome_id,
                "sequence_name": sequence_name,
                "sequence_length": len(sequence),
                "sequence_path": str(normalized_cds_path.resolve()),
                "gene_symbol": gene_symbol,
                "transcript_id": transcript_id,
                "isoform_id": first_nonempty(protein_external_id, transcript_id),
                "assembly_accession": accession,
                "taxon_id": taxon_id,
                "source_record_id": source_record_id,
                "protein_external_id": protein_external_id,
                "translation_table": translation_table,
                "gene_group": gene_group,
                "linkage_status": linkage_status,
                "partial_status": partial_status,
            }
            if previous_source_sequence is None:
                seen_source_sequences[source_sequence_key] = sequence
            elif previous_source_sequence != sequence:
                warnings_rows.append(
                    build_warning_row(
                        "conflicting_duplicate_cds_key",
                        "sequence",
                        "The same CDS linkage key appeared multiple times with different nucleotide sequences",
                        batch_id=args.batch_id,
                        genome_id=genome_id,
                        sequence_id=sequence_id,
                        assembly_accession=accession,
                        source_file=str(cds_path.resolve()),
                        source_record_id=source_record_id or metadata.get("record_id", ""),
                    )
                )

            existing_row = seen_sequence_rows.get(sequence_id)
            if existing_row is not None:
                existing_sequence = seen_cds_sequences.get(sequence_id, "")
                if existing_row != candidate_row or existing_sequence != sequence:
                    raise ContractError(
                        f"Conflicting normalized sequence rows produced the same sequence_id {sequence_id}"
                    )
                continue

            seen_sequence_rows[sequence_id] = candidate_row
            seen_cds_sequences[sequence_id] = sequence
            sequences_rows.append(candidate_row)
            normalized_cds_records.append((sequence_id, sequence))

    write_tsv(outdir / "genomes.tsv", genomes_rows, fieldnames=GENOMES_FIELDNAMES)
    write_tsv(
        outdir / "taxonomy.tsv",
        [taxonomy_rows_by_id[key] for key in sorted(taxonomy_rows_by_id)],
        fieldnames=TAXONOMY_FIELDNAMES,
    )
    write_tsv(outdir / "sequences.tsv", sequences_rows, fieldnames=SEQUENCES_FIELDNAMES)
    write_fasta(normalized_cds_path, normalized_cds_records)
    write_tsv(warning_path, warnings_rows, fieldnames=WARNING_FIELDNAMES)
    _copy_download_manifest(package_root, outdir)
    return 0


def _copy_download_manifest(package_root: Path, outdir: Path) -> None:
    candidate_paths = [
        package_root / "download_manifest.tsv",
        package_root.parent / "download_manifest.tsv",
    ]
    for candidate in candidate_paths:
        if candidate.is_file():
            shutil.copyfile(candidate, outdir / "download_manifest.tsv")
            return


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
