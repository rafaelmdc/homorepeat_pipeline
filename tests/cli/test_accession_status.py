from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, build_call_row
from homorepeat.io.tsv_io import read_tsv, write_tsv
from homorepeat.runtime.stage_status import build_stage_status, write_stage_status

from tests.test_support import CLI_ENV, REPO_ROOT


class AccessionStatusCliTest(unittest.TestCase):
    def test_build_accession_status_covers_completed_no_calls_and_failed_accessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            planning = tmp / "planning"
            batch_one = tmp / "batches" / "batch_0001"
            batch_two = tmp / "batches" / "batch_0002"
            batch_three = tmp / "batches" / "batch_0003"
            batch_four = tmp / "batches" / "batch_0004"
            detect_dir = tmp / "detect"
            outdir = tmp / "publish" / "status"
            planning.mkdir(parents=True, exist_ok=True)
            batch_one.mkdir(parents=True, exist_ok=True)
            batch_two.mkdir(parents=True, exist_ok=True)
            batch_three.mkdir(parents=True, exist_ok=True)
            batch_four.mkdir(parents=True, exist_ok=True)
            detect_dir.mkdir(parents=True, exist_ok=True)

            batch_table = planning / "accession_batches.tsv"
            write_tsv(
                batch_table,
                [
                    {"batch_id": "batch_0001", "assembly_accession": "GCF_COMPLETE.1"},
                    {"batch_id": "batch_0002", "assembly_accession": "GCF_NO_CALLS.1"},
                    {"batch_id": "batch_0003", "assembly_accession": "GCF_FAILED.1"},
                    {"batch_id": "batch_0004", "assembly_accession": "GCF_DETECT_NO_CALLS.1"},
                ],
                fieldnames=["batch_id", "assembly_accession"],
            )

            self._write_batch_dir(
                batch_one,
                batch_id="batch_0001",
                accession="GCF_COMPLETE.1",
                n_genomes=1,
                n_proteins=1,
                download_status="downloaded",
            )
            self._write_batch_dir(
                batch_two,
                batch_id="batch_0002",
                accession="GCF_NO_CALLS.1",
                n_genomes=1,
                n_proteins=0,
                download_status="downloaded",
            )
            self._write_failed_batch_dir(
                batch_three,
                batch_id="batch_0003",
                accession="GCF_FAILED.1",
                message="datasets failed",
            )
            self._write_batch_dir(
                batch_four,
                batch_id="batch_0004",
                accession="GCF_DETECT_NO_CALLS.1",
                n_genomes=1,
                n_proteins=1,
                download_status="downloaded",
            )

            detect_success = detect_dir / "detect_success.json"
            detect_success_no_calls = detect_dir / "detect_success_no_calls.json"
            finalize_success = detect_dir / "finalize_success.json"
            write_stage_status(
                detect_success,
                build_stage_status(
                    stage="detect",
                    status="success",
                    batch_id="batch_0001",
                    method="pure",
                    repeat_residue="Q",
                ),
            )
            write_stage_status(
                detect_success_no_calls,
                build_stage_status(
                    stage="detect",
                    status="success",
                    batch_id="batch_0004",
                    method="pure",
                    repeat_residue="Q",
                ),
            )
            write_stage_status(
                finalize_success,
                build_stage_status(
                    stage="finalize",
                    status="success",
                    batch_id="batch_0001",
                    method="pure",
                    repeat_residue="Q",
                ),
            )

            call_tsv = detect_dir / "final_pure_Q_batch_0001_calls.tsv"
            write_tsv(
                call_tsv,
                [
                    build_call_row(
                        method="pure",
                        genome_id="genome_GCF_COMPLETE.1",
                        taxon_id="9606",
                        sequence_id="seq_GCF_COMPLETE.1_0",
                        protein_id="prot_GCF_COMPLETE.1_0",
                        repeat_residue="Q",
                        start=1,
                        end=6,
                        aa_sequence="QQQQQQ",
                    )
                ],
                fieldnames=CALL_FIELDNAMES,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homorepeat.cli.build_accession_status",
                    "--batch-table",
                    str(batch_table),
                    "--batch-dir",
                    str(batch_one),
                    "--batch-dir",
                    str(batch_two),
                    "--batch-dir",
                    str(batch_three),
                    "--batch-dir",
                    str(batch_four),
                    "--detect-status-json",
                    str(detect_success),
                    "--detect-status-json",
                    str(detect_success_no_calls),
                    "--finalize-status-json",
                    str(finalize_success),
                    "--call-tsv",
                    str(call_tsv),
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
                    f"build_accession_status failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            status_rows = read_tsv(outdir / "accession_status.tsv")
            count_rows = read_tsv(outdir / "accession_call_counts.tsv")
            summary = json.loads((outdir / "status_summary.json").read_text(encoding="utf-8"))

            by_accession = {row["assembly_accession"]: row for row in status_rows}
            by_count_key = {
                (row["assembly_accession"], row["method"], row["repeat_residue"]): row
                for row in count_rows
            }
            self.assertEqual(by_accession["GCF_COMPLETE.1"]["terminal_status"], "completed")
            self.assertEqual(by_accession["GCF_COMPLETE.1"]["n_repeat_calls"], "1")
            self.assertEqual(by_accession["GCF_NO_CALLS.1"]["terminal_status"], "failed")
            self.assertEqual(by_accession["GCF_NO_CALLS.1"]["translate_status"], "failed")
            self.assertEqual(by_accession["GCF_NO_CALLS.1"]["failure_stage"], "translate")
            self.assertEqual(by_accession["GCF_DETECT_NO_CALLS.1"]["terminal_status"], "completed_no_calls")
            self.assertEqual(by_accession["GCF_DETECT_NO_CALLS.1"]["detect_status"], "success")
            self.assertEqual(by_accession["GCF_DETECT_NO_CALLS.1"]["finalize_status"], "skipped")
            self.assertEqual(by_accession["GCF_FAILED.1"]["terminal_status"], "failed")
            self.assertEqual(by_accession["GCF_FAILED.1"]["failure_stage"], "download")
            self.assertEqual(len(count_rows), 4)
            self.assertEqual(by_count_key[("GCF_COMPLETE.1", "pure", "Q")]["n_repeat_calls"], "1")
            self.assertEqual(by_count_key[("GCF_COMPLETE.1", "pure", "Q")]["finalize_status"], "success")
            self.assertEqual(by_count_key[("GCF_NO_CALLS.1", "pure", "Q")]["detect_status"], "skipped_upstream_failed")
            self.assertEqual(by_count_key[("GCF_DETECT_NO_CALLS.1", "pure", "Q")]["detect_status"], "success")
            self.assertEqual(by_count_key[("GCF_DETECT_NO_CALLS.1", "pure", "Q")]["finalize_status"], "skipped")
            self.assertEqual(by_count_key[("GCF_FAILED.1", "pure", "Q")]["finalize_status"], "skipped_upstream_failed")
            self.assertEqual(summary["status"], "partial")
            self.assertEqual(summary["counts"]["n_requested_accessions"], 4)
            self.assertEqual(summary["counts"]["n_completed"], 1)
            self.assertEqual(summary["counts"]["n_completed_no_calls"], 1)
            self.assertEqual(summary["counts"]["n_failed"], 2)

    def _write_batch_dir(
        self,
        batch_dir: Path,
        *,
        batch_id: str,
        accession: str,
        n_genomes: int,
        n_proteins: int,
        download_status: str,
    ) -> None:
        write_stage_status(
            batch_dir / "download_stage_status.json",
            build_stage_status(stage="download", status="success", batch_id=batch_id),
        )
        write_stage_status(
            batch_dir / "normalize_stage_status.json",
            build_stage_status(stage="normalize", status="success", batch_id=batch_id),
        )
        write_stage_status(
            batch_dir / "translate_stage_status.json",
            build_stage_status(stage="translate", status="success", batch_id=batch_id),
        )
        write_tsv(
            batch_dir / "download_manifest.tsv",
            [
                {
                    "batch_id": batch_id,
                    "assembly_accession": accession,
                    "download_status": download_status,
                    "package_mode": "direct_zip",
                    "download_path": "",
                    "rehydrated_path": "",
                    "checksum": "",
                    "file_size_bytes": "",
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
        write_tsv(
            batch_dir / "genomes.tsv",
            [
                {
                    "genome_id": f"genome_{accession}",
                    "source": "ncbi_datasets",
                    "accession": accession,
                    "genome_name": accession,
                    "assembly_type": "haploid",
                    "taxon_id": "9606",
                    "assembly_level": "Chromosome",
                    "species_name": "Homo sapiens",
                    "download_path": str(batch_dir.resolve()),
                    "notes": "",
                }
                for index in range(n_genomes)
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
                "download_path",
                "notes",
            ],
        )
        write_tsv(
            batch_dir / "sequences.tsv",
            [
                {
                    "sequence_id": f"seq_{accession}_{index}",
                    "genome_id": f"genome_{accession}",
                    "sequence_name": f"SEQ_{index}",
                    "sequence_length": "300",
                    "gene_symbol": "",
                    "transcript_id": "",
                    "isoform_id": "",
                    "assembly_accession": accession,
                    "taxon_id": "9606",
                    "source_record_id": "",
                    "protein_external_id": "",
                    "translation_table": "1",
                    "gene_group": f"gene_{index}",
                    "linkage_status": "gff",
                    "partial_status": "",
                }
                for index in range(n_genomes)
            ],
            fieldnames=[
                "sequence_id",
                "genome_id",
                "sequence_name",
                "sequence_length",
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
            ],
        )
        write_tsv(
            batch_dir / "proteins.tsv",
            [
                {
                    "protein_id": f"prot_{accession}_{index}",
                    "sequence_id": f"seq_{accession}_{index}",
                    "genome_id": f"genome_{accession}",
                    "protein_name": f"PROT_{index}",
                    "protein_length": 100,
                    "protein_path": str((batch_dir / "proteins.faa").resolve()),
                    "gene_symbol": "",
                    "translation_method": "local_cds_translation",
                    "translation_status": "translated",
                    "assembly_accession": accession,
                    "taxon_id": "9606",
                    "gene_group": f"gene_{index}",
                    "protein_external_id": "",
                }
                for index in range(n_proteins)
            ],
            fieldnames=[
                "protein_id",
                "sequence_id",
                "genome_id",
                "protein_name",
                "protein_length",
                "protein_path",
                "gene_symbol",
                "translation_method",
                "translation_status",
                "assembly_accession",
                "taxon_id",
                "gene_group",
                "protein_external_id",
            ],
        )

    def _write_failed_batch_dir(self, batch_dir: Path, *, batch_id: str, accession: str, message: str) -> None:
        write_stage_status(
            batch_dir / "translate_stage_status.json",
            build_stage_status(stage="translate", status="success", batch_id=batch_id),
        )
        write_stage_status(
            batch_dir / "normalize_stage_status.json",
            build_stage_status(stage="normalize", status="success", batch_id=batch_id),
        )
        write_stage_status(
            batch_dir / "download_stage_status.json",
            build_stage_status(stage="download", status="failed", batch_id=batch_id, message=message),
        )
        write_tsv(
            batch_dir / "download_manifest.tsv",
            [
                {
                    "batch_id": batch_id,
                    "assembly_accession": accession,
                    "download_status": "failed",
                    "package_mode": "direct_zip",
                    "download_path": "",
                    "rehydrated_path": "",
                    "checksum": "",
                    "file_size_bytes": "",
                    "download_started_at": "",
                    "download_finished_at": "",
                    "notes": message,
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
        write_tsv(batch_dir / "genomes.tsv", [], fieldnames=[
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
        ])
        write_tsv(batch_dir / "sequences.tsv", [], fieldnames=[
            "sequence_id",
            "genome_id",
            "sequence_name",
            "sequence_length",
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
        ])
        write_tsv(batch_dir / "proteins.tsv", [], fieldnames=[
            "protein_id",
            "sequence_id",
            "genome_id",
            "protein_name",
            "protein_length",
            "protein_path",
            "gene_symbol",
            "translation_method",
            "translation_status",
            "assembly_accession",
            "taxon_id",
            "gene_group",
            "protein_external_id",
        ])
