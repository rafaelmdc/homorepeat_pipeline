from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from homorepeat.contracts.publish_contract_v2 import MATCHED_PROTEINS_FIELDNAMES, MATCHED_SEQUENCES_FIELDNAMES
from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, build_call_row
from homorepeat.contracts.warnings import WARNING_FIELDNAMES
from homorepeat.io.fasta_io import write_fasta
from homorepeat.io.tsv_io import read_tsv, write_tsv

from tests.test_support import CLI_ENV, REPO_ROOT, cli_command


SOURCE_SEQUENCE_FIELDNAMES = [
    fieldname
    for fieldname in MATCHED_SEQUENCES_FIELDNAMES[1:]
    if fieldname != "nucleotide_sequence"
]
SOURCE_PROTEIN_FIELDNAMES = [
    fieldname
    for fieldname in MATCHED_PROTEINS_FIELDNAMES[1:]
    if fieldname != "amino_acid_sequence"
]


class ExportPublishTablesCliTest(unittest.TestCase):
    def test_export_publish_tables_cli_merges_flat_tables_and_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            planning_dir = tmp / "planning"
            status_dir = tmp / "status"
            outdir = tmp / "publish"
            batch_one = tmp / "batch_views" / "batch_0001"
            batch_two = tmp / "batch_views" / "batch_0002"
            planning_dir.mkdir(parents=True, exist_ok=True)
            status_dir.mkdir(parents=True, exist_ok=True)
            batch_one.mkdir(parents=True, exist_ok=True)
            batch_two.mkdir(parents=True, exist_ok=True)

            batch_table = planning_dir / "accession_batches.tsv"
            write_tsv(
                batch_table,
                [
                    {"batch_id": "batch_0001", "assembly_accession": "GCF_A.1"},
                    {"batch_id": "batch_0002", "assembly_accession": "GCF_B.1"},
                ],
                fieldnames=["batch_id", "assembly_accession"],
            )

            self._write_batch_view(
                batch_one,
                accession="GCF_A.1",
                taxon_id="9606",
                species_name="Homo sapiens",
                warning_rows=[
                    {
                        "warning_code": "partial_cds",
                        "warning_scope": "sequence",
                        "warning_message": "CDS is partial",
                        "batch_id": "batch_0001",
                        "genome_id": "genome_GCF_A.1",
                        "sequence_id": "seq_GCF_A.1_1",
                        "protein_id": "",
                        "assembly_accession": "GCF_A.1",
                        "source_file": "",
                        "source_record_id": "cds-1",
                    }
                ],
                validation_payload={
                    "status": "warn",
                    "scope": "batch",
                    "batch_id": "batch_0001",
                    "counts": {
                        "n_selected_assemblies": 1,
                        "n_downloaded_packages": 1,
                        "n_genomes": 1,
                        "n_sequences": 2,
                        "n_proteins": 1,
                        "n_warning_rows": 1,
                    },
                    "checks": {
                        "all_selected_accessions_accounted_for": True,
                        "all_genomes_have_taxids": True,
                        "all_proteins_belong_to_genomes": True,
                        "all_retained_proteins_trace_to_cds": True,
                    },
                    "failed_accessions": [],
                    "warning_summary": {"partial_cds": 1},
                    "notes": [],
                },
            )
            self._write_batch_view(
                batch_two,
                accession="GCF_B.1",
                taxon_id="10090",
                species_name="Mus musculus",
                warning_rows=[],
                validation_payload={
                    "status": "pass",
                    "scope": "batch",
                    "batch_id": "batch_0002",
                    "counts": {
                        "n_selected_assemblies": 1,
                        "n_downloaded_packages": 1,
                        "n_genomes": 1,
                        "n_sequences": 1,
                        "n_proteins": 0,
                        "n_warning_rows": 0,
                    },
                    "checks": {
                        "all_selected_accessions_accounted_for": True,
                        "all_genomes_have_taxids": True,
                        "all_proteins_belong_to_genomes": True,
                        "all_retained_proteins_trace_to_cds": True,
                    },
                    "failed_accessions": [],
                    "warning_summary": {},
                    "notes": [],
                },
                taxonomy_rows=[
                    {
                        "taxon_id": "9606",
                        "taxon_name": "Homo sapiens",
                        "parent_taxon_id": "9605",
                        "rank": "species",
                        "source": "ncbi_taxonomy",
                    },
                    {
                        "taxon_id": "10090",
                        "taxon_name": "Mus musculus",
                        "parent_taxon_id": "10088",
                        "rank": "species",
                        "source": "ncbi_taxonomy",
                    },
                ],
            )

            accession_status_tsv = status_dir / "accession_status.tsv"
            accession_call_counts_tsv = status_dir / "accession_call_counts.tsv"
            repeat_calls_tsv = status_dir / "repeat_calls.tsv"
            status_summary_json = status_dir / "status_summary.json"
            write_tsv(
                repeat_calls_tsv,
                [
                    build_call_row(
                        method="pure",
                        genome_id="genome_GCF_A.1",
                        taxon_id="9606",
                        sequence_id="seq_GCF_A.1_1",
                        protein_id="protein_GCF_A.1_1",
                        repeat_residue="Q",
                        start=1,
                        end=3,
                        aa_sequence="QQQ",
                    ),
                    build_call_row(
                        method="threshold",
                        genome_id="genome_GCF_A.1",
                        taxon_id="9606",
                        sequence_id="seq_GCF_A.1_1",
                        protein_id="protein_GCF_A.1_1",
                        repeat_residue="Q",
                        start=5,
                        end=7,
                        aa_sequence="QQQ",
                    ),
                ],
                fieldnames=CALL_FIELDNAMES,
            )
            write_tsv(
                accession_status_tsv,
                [
                    {
                        "assembly_accession": "GCF_A.1",
                        "batch_id": "batch_0001",
                        "download_status": "downloaded",
                        "normalize_status": "success",
                        "translate_status": "success",
                        "detect_status": "success",
                        "finalize_status": "success",
                        "terminal_status": "completed",
                        "failure_stage": "",
                        "failure_reason": "",
                        "n_genomes": 1,
                        "n_proteins": 1,
                        "n_repeat_calls": 2,
                        "notes": "",
                    },
                    {
                        "assembly_accession": "GCF_B.1",
                        "batch_id": "batch_0002",
                        "download_status": "downloaded",
                        "normalize_status": "success",
                        "translate_status": "success",
                        "detect_status": "success",
                        "finalize_status": "skipped",
                        "terminal_status": "completed_no_calls",
                        "failure_stage": "",
                        "failure_reason": "",
                        "n_genomes": 1,
                        "n_proteins": 0,
                        "n_repeat_calls": 0,
                        "notes": "",
                    },
                ],
                fieldnames=[
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
                ],
            )
            write_tsv(
                accession_call_counts_tsv,
                [
                    {
                        "assembly_accession": "GCF_A.1",
                        "batch_id": "batch_0001",
                        "method": "pure",
                        "repeat_residue": "Q",
                        "detect_status": "success",
                        "finalize_status": "success",
                        "n_repeat_calls": 2,
                    },
                    {
                        "assembly_accession": "GCF_B.1",
                        "batch_id": "batch_0002",
                        "method": "pure",
                        "repeat_residue": "Q",
                        "detect_status": "success",
                        "finalize_status": "skipped",
                        "n_repeat_calls": 0,
                    },
                ],
                fieldnames=[
                    "assembly_accession",
                    "batch_id",
                    "method",
                    "repeat_residue",
                    "detect_status",
                    "finalize_status",
                    "n_repeat_calls",
                ],
            )
            summary_payload = {
                "status": "success",
                "counts": {
                    "n_requested_accessions": 2,
                    "n_completed": 1,
                    "n_completed_no_calls": 1,
                    "n_failed": 0,
                    "n_skipped_upstream_failed": 0,
                },
                "terminal_status_counts": {
                    "completed": 1,
                    "completed_no_calls": 1,
                },
            }
            status_summary_json.write_text(json.dumps(summary_payload) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    *cli_command("export_publish_tables"),
                    "--batch-table",
                    str(batch_table),
                    "--batch-dir",
                    str(batch_one),
                    "--batch-dir",
                    str(batch_two),
                    "--repeat-calls-tsv",
                    str(repeat_calls_tsv),
                    "--accession-status-tsv",
                    str(accession_status_tsv),
                    "--accession-call-counts-tsv",
                    str(accession_call_counts_tsv),
                    "--status-summary-json",
                    str(status_summary_json),
                    "--outdir",
                    str(outdir),
                ],
                cwd=REPO_ROOT,
                env=CLI_ENV,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.fail(
                    f"export_publish_tables failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            genomes_rows = read_tsv(outdir / "tables" / "genomes.tsv")
            matched_sequence_rows = read_tsv(outdir / "tables" / "matched_sequences.tsv")
            matched_protein_rows = read_tsv(outdir / "tables" / "matched_proteins.tsv")
            taxonomy_rows = read_tsv(outdir / "tables" / "taxonomy.tsv")
            manifest_rows = read_tsv(outdir / "tables" / "download_manifest.tsv")
            warning_rows = read_tsv(outdir / "tables" / "normalization_warnings.tsv")
            status_rows = read_tsv(outdir / "tables" / "accession_status.tsv")
            call_count_rows = read_tsv(outdir / "tables" / "accession_call_counts.tsv")
            acquisition_validation = json.loads(
                (outdir / "summaries" / "acquisition_validation.json").read_text(encoding="utf-8")
            )
            exported_status_summary = json.loads((outdir / "summaries" / "status_summary.json").read_text(encoding="utf-8"))

            self.assertEqual(
                [(row["batch_id"], row["accession"], row["taxon_id"]) for row in genomes_rows],
                [
                    ("batch_0001", "GCF_A.1", "9606"),
                    ("batch_0002", "GCF_B.1", "10090"),
                ],
            )
            self.assertEqual(
                [(row["batch_id"], row["sequence_id"]) for row in matched_sequence_rows],
                [("batch_0001", "seq_GCF_A.1_1")],
            )
            self.assertEqual(matched_sequence_rows[0]["nucleotide_sequence"], "ATGCAACAACAATAG")
            self.assertEqual(
                [(row["batch_id"], row["protein_id"], row["sequence_id"]) for row in matched_protein_rows],
                [("batch_0001", "protein_GCF_A.1_1", "seq_GCF_A.1_1")],
            )
            self.assertEqual(matched_protein_rows[0]["amino_acid_sequence"], "MQQQ")
            self.assertEqual([row["taxon_id"] for row in taxonomy_rows], ["10090", "9606"])
            self.assertEqual([row["assembly_accession"] for row in manifest_rows], ["GCF_A.1", "GCF_B.1"])
            self.assertEqual(len(warning_rows), 1)
            self.assertEqual(warning_rows[0]["warning_code"], "partial_cds")
            self.assertEqual([row["assembly_accession"] for row in status_rows], ["GCF_A.1", "GCF_B.1"])
            self.assertEqual([row["n_repeat_calls"] for row in call_count_rows], ["2", "0"])
            self.assertEqual(exported_status_summary, summary_payload)
            self.assertEqual(acquisition_validation["scope"], "merged")
            self.assertEqual(acquisition_validation["status"], "warn")
            self.assertEqual(acquisition_validation["counts"]["n_selected_assemblies"], 2)
            self.assertEqual(acquisition_validation["counts"]["n_warning_rows"], 1)
            self.assertEqual(acquisition_validation["warning_summary"], {"partial_cds": 1})

    def _write_batch_view(
        self,
        batch_dir: Path,
        *,
        accession: str,
        taxon_id: str,
        species_name: str,
        warning_rows: list[dict[str, object]],
        validation_payload: dict[str, object],
        taxonomy_rows: list[dict[str, object]] | None = None,
    ) -> None:
        write_tsv(
            batch_dir / "genomes.tsv",
            [
                {
                    "genome_id": f"genome_{accession}",
                    "source": "ncbi_datasets",
                    "accession": accession,
                    "genome_name": species_name,
                    "assembly_type": "reference",
                    "taxon_id": taxon_id,
                    "assembly_level": "Chromosome",
                    "species_name": species_name,
                    "notes": "",
                }
            ],
            fieldnames=[
                "genome_id",
                "source",
                "accession",
                "genome_name",
                "assembly_type",
                "taxon_id",
                "assembly_level",
                "species_name",
                "notes",
            ],
        )
        write_tsv(
            batch_dir / "taxonomy.tsv",
            taxonomy_rows
            or [
                {
                    "taxon_id": taxon_id,
                    "taxon_name": species_name,
                    "parent_taxon_id": "9605" if taxon_id == "9606" else "10088" if taxon_id == "10090" else "",
                    "rank": "species",
                    "source": "ncbi_taxonomy",
                }
            ],
            fieldnames=["taxon_id", "taxon_name", "parent_taxon_id", "rank", "source"],
        )
        sequence_rows = [
            {
                "sequence_id": f"seq_{accession}_1",
                "genome_id": f"genome_{accession}",
                "sequence_name": "tx1",
                "sequence_length": "99",
                "gene_symbol": "GENE1",
                "transcript_id": "tx1",
                "isoform_id": "protein1",
                "assembly_accession": accession,
                "taxon_id": taxon_id,
                "source_record_id": "cds-1",
                "protein_external_id": "protein1",
                "translation_table": "1",
                "gene_group": "GENE1",
                "linkage_status": "protein_id_linked",
                "partial_status": "",
            },
            {
                "sequence_id": f"seq_{accession}_unmatched",
                "genome_id": f"genome_{accession}",
                "sequence_name": "tx-unmatched",
                "sequence_length": "42",
                "gene_symbol": "GENE2",
                "transcript_id": "tx-unmatched",
                "isoform_id": "protein-unmatched",
                "assembly_accession": accession,
                "taxon_id": taxon_id,
                "source_record_id": "cds-unmatched",
                "protein_external_id": "protein-unmatched",
                "translation_table": "1",
                "gene_group": "GENE2",
                "linkage_status": "protein_id_linked",
                "partial_status": "",
            },
        ]
        write_tsv(batch_dir / "sequences.tsv", sequence_rows, fieldnames=SOURCE_SEQUENCE_FIELDNAMES)
        write_fasta(
            batch_dir / "cds.fna",
            [
                (f"seq_{accession}_1", "ATGCAACAACAATAG"),
                (f"seq_{accession}_unmatched", "ATGCAATAG"),
            ],
        )
        protein_rows = [
            {
                "protein_id": f"protein_{accession}_1",
                "sequence_id": f"seq_{accession}_1",
                "genome_id": f"genome_{accession}",
                "protein_name": "protein1",
                "protein_length": "33",
                "gene_symbol": "GENE1",
                "translation_method": "local_cds_translation",
                "translation_status": "translated",
                "assembly_accession": accession,
                "taxon_id": taxon_id,
                "gene_group": "GENE1",
                "protein_external_id": "protein1",
            },
            {
                "protein_id": f"protein_{accession}_unmatched",
                "sequence_id": f"seq_{accession}_unmatched",
                "genome_id": f"genome_{accession}",
                "protein_name": "protein-unmatched",
                "protein_length": "14",
                "gene_symbol": "GENE2",
                "translation_method": "local_cds_translation",
                "translation_status": "translated",
                "assembly_accession": accession,
                "taxon_id": taxon_id,
                "gene_group": "GENE2",
                "protein_external_id": "protein-unmatched",
            },
        ]
        write_tsv(batch_dir / "proteins.tsv", protein_rows, fieldnames=SOURCE_PROTEIN_FIELDNAMES)
        write_fasta(
            batch_dir / "proteins.faa",
            [
                (f"protein_{accession}_1", "MQQQ"),
                (f"protein_{accession}_unmatched", "MQ"),
            ],
        )
        write_tsv(
            batch_dir / "download_manifest.tsv",
            [
                {
                    "batch_id": batch_dir.name,
                    "assembly_accession": accession,
                    "download_status": "downloaded",
                    "package_mode": "direct_zip",
                    "download_path": "",
                    "rehydrated_path": "",
                    "checksum": "",
                    "file_size_bytes": "1024",
                    "download_started_at": "",
                    "download_finished_at": "",
                    "notes": "",
                }
            ],
            fieldnames=[
                "batch_id",
                "assembly_accession",
                "download_status",
                "package_mode",
                "download_path",
                "rehydrated_path",
                "checksum",
                "file_size_bytes",
                "download_started_at",
                "download_finished_at",
                "notes",
            ],
        )
        write_tsv(batch_dir / "normalization_warnings.tsv", warning_rows, fieldnames=WARNING_FIELDNAMES)
        (batch_dir / "acquisition_validation.json").write_text(
            json.dumps(validation_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
