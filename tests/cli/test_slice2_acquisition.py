from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path

from homorepeat.io.tsv_io import read_tsv, write_tsv


from tests.test_support import CLI_ENV, REPO_ROOT, cli_command
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "packages"


class SliceTwoAcquisitionTest(unittest.TestCase):
    def test_download_normalize_translate_and_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            planning_dir = tmp / "planning"
            batch_one_raw = tmp / "batches" / "batch_0001" / "raw"
            batch_one_norm = tmp / "batches" / "batch_0001" / "normalized"
            batch_two_raw = tmp / "batches" / "batch_0002" / "raw"
            batch_two_norm = tmp / "batches" / "batch_0002" / "normalized"
            merged_dir = tmp / "merged" / "acquisition"
            fake_bin_dir = tmp / "fake_bin"
            taxonomy_db = tmp / "taxonomy.sqlite"
            planning_dir.mkdir(parents=True, exist_ok=True)
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            taxonomy_db.write_text("", encoding="utf-8")

            selected_batches_path = planning_dir / "selected_batches.tsv"
            write_tsv(
                selected_batches_path,
                [
                    {
                        "batch_id": "batch_0001",
                        "request_id": "req_001",
                        "assembly_accession": "GCF_000001405.40",
                        "taxon_id": "9606",
                        "batch_reason": "split_large_taxon_fixed_size",
                        "resolved_name": "Homo sapiens",
                        "refseq_category": "reference genome",
                        "assembly_level": "Chromosome",
                        "annotation_status": "annotated:Updated annotation",
                    },
                    {
                        "batch_id": "batch_0002",
                        "request_id": "req_004",
                        "assembly_accession": "GCF_000001635.27",
                        "taxon_id": "10090",
                        "batch_reason": "single_small_taxon_batch",
                        "resolved_name": "Mus musculus",
                        "refseq_category": "reference genome",
                        "assembly_level": "Chromosome",
                        "annotation_status": "annotated:Updated annotation",
                    },
                ],
                fieldnames=[
                    "batch_id",
                    "request_id",
                    "assembly_accession",
                    "taxon_id",
                    "batch_reason",
                    "resolved_name",
                    "refseq_category",
                    "assembly_level",
                    "annotation_status",
                ],
            )

            self._write_fake_datasets(fake_bin_dir / "datasets")
            self._write_fake_taxon_weaver(fake_bin_dir / "taxon-weaver")
            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"
            env["HOMOREPEAT_FIXTURES_ROOT"] = str(FIXTURES_ROOT)

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.download_ncbi_packages",
                    "--batch-manifest",
                    str(selected_batches_path),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(batch_one_raw),
                ],
                env=env,
            )
            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.normalize_cds",
                    "--package-dir",
                    str(batch_one_raw / "ncbi_package"),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(batch_one_norm),
                ],
                env=env,
            )
            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.translate_cds",
                    "--sequences-tsv",
                    str(batch_one_norm / "sequences.tsv"),
                    "--cds-fasta",
                    str(batch_one_norm / "cds.fna"),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(batch_one_norm),
                ],
                env=env,
            )

            batch_one_manifest = read_tsv(batch_one_raw / "download_manifest.tsv")
            self.assertEqual(len(batch_one_manifest), 1)
            self.assertEqual({row["download_status"] for row in batch_one_manifest}, {"downloaded"})

            batch_one_genomes = read_tsv(batch_one_norm / "genomes.tsv")
            batch_one_taxonomy = read_tsv(batch_one_norm / "taxonomy.tsv")
            batch_one_sequences = read_tsv(batch_one_norm / "sequences.tsv")
            batch_one_proteins = read_tsv(batch_one_norm / "proteins.tsv")
            batch_one_warnings = read_tsv(batch_one_norm / "normalization_warnings.tsv")
            batch_one_validation = json.loads((batch_one_norm / "acquisition_validation.json").read_text(encoding="utf-8"))

            self.assertEqual(len(batch_one_genomes), 1)
            self.assertEqual(len(batch_one_taxonomy), 3)
            taxonomy_by_id = {row["taxon_id"]: row for row in batch_one_taxonomy}
            self.assertEqual(taxonomy_by_id["1"]["taxon_name"], "root")
            self.assertEqual(taxonomy_by_id["1"]["parent_taxon_id"], "")
            self.assertEqual(taxonomy_by_id["9605"]["taxon_name"], "Homo")
            self.assertEqual(taxonomy_by_id["9605"]["parent_taxon_id"], "1")
            self.assertEqual(taxonomy_by_id["9606"]["taxon_name"], "Homo sapiens")
            self.assertEqual(taxonomy_by_id["9606"]["parent_taxon_id"], "9605")
            self.assertEqual(taxonomy_by_id["9606"]["rank"], "species")
            self.assertEqual(taxonomy_by_id["9606"]["source"], "taxon_weaver:2026-04-05")
            self.assertEqual(len(batch_one_sequences), 3)
            self.assertEqual(len(batch_one_proteins), 2)
            self.assertNotIn("download_path", batch_one_genomes[0])
            self.assertNotIn("sequence_path", batch_one_sequences[0])
            self.assertNotIn("protein_path", batch_one_proteins[0])
            self.assertEqual(batch_one_genomes[0]["genome_id"], "GCF_000001405.40")
            self.assertTrue(all(row["sequence_id"].startswith("GCF_000001405.40::") for row in batch_one_sequences))
            self.assertTrue(all(row["protein_id"].endswith("::protein") for row in batch_one_proteins))
            self.assertEqual(sorted(row["gene_symbol"] for row in batch_one_proteins), ["ABC1", "XYZ1"])
            self.assertEqual(batch_one_warnings, [])
            self.assertEqual(batch_one_validation["status"], "pass")

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.download_ncbi_packages",
                    "--batch-manifest",
                    str(selected_batches_path),
                    "--batch-id",
                    "batch_0002",
                    "--outdir",
                    str(batch_two_raw),
                ],
                env=env,
            )
            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.normalize_cds",
                    "--package-dir",
                    str(batch_two_raw / "ncbi_package"),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--batch-id",
                    "batch_0002",
                    "--outdir",
                    str(batch_two_norm),
                ],
                env=env,
            )
            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.translate_cds",
                    "--sequences-tsv",
                    str(batch_two_norm / "sequences.tsv"),
                    "--cds-fasta",
                    str(batch_two_norm / "cds.fna"),
                    "--batch-id",
                    "batch_0002",
                    "--outdir",
                    str(batch_two_norm),
                ],
                env=env,
            )

            batch_two_proteins = read_tsv(batch_two_norm / "proteins.tsv")
            self.assertEqual(len(batch_two_proteins), 1)
            self.assertEqual(batch_two_proteins[0]["gene_symbol"], "MOUSE1")

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.merge_acquisition_batches",
                    "--batch-inputs",
                    str(batch_one_norm),
                    "--batch-inputs",
                    str(batch_two_norm),
                    "--outdir",
                    str(merged_dir),
                ],
                env=env,
            )

            merged_genomes = read_tsv(merged_dir / "genomes.tsv")
            merged_taxonomy = read_tsv(merged_dir / "taxonomy.tsv")
            merged_sequences = read_tsv(merged_dir / "sequences.tsv")
            merged_proteins = read_tsv(merged_dir / "proteins.tsv")
            merged_warnings = read_tsv(merged_dir / "normalization_warnings.tsv")
            merged_manifest = read_tsv(merged_dir / "download_manifest.tsv")
            merged_validation = json.loads((merged_dir / "acquisition_validation.json").read_text(encoding="utf-8"))

            self.assertEqual(len(merged_genomes), 2)
            self.assertEqual(len(merged_taxonomy), 5)
            self.assertEqual(len(merged_sequences), 4)
            self.assertEqual(len(merged_proteins), 3)
            self.assertEqual(len(merged_manifest), 2)
            self.assertEqual(merged_warnings, [])
            self.assertEqual(merged_validation["scope"], "merged")
            self.assertEqual(merged_validation["status"], "pass")

    def test_download_ncbi_packages_retries_transient_datasets_gateway_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            planning_dir = tmp / "planning"
            outdir = tmp / "batches" / "batch_0001" / "raw"
            fake_bin_dir = tmp / "fake_bin"
            planning_dir.mkdir(parents=True, exist_ok=True)
            fake_bin_dir.mkdir(parents=True, exist_ok=True)

            selected_batches_path = planning_dir / "selected_batches.tsv"
            write_tsv(
                selected_batches_path,
                [
                    {
                        "batch_id": "batch_0001",
                        "request_id": "req_001",
                        "assembly_accession": "GCF_000001405.40",
                        "taxon_id": "9606",
                        "batch_reason": "single_small_taxon_batch",
                        "resolved_name": "Homo sapiens",
                        "refseq_category": "reference genome",
                        "assembly_level": "Chromosome",
                        "annotation_status": "annotated:Updated annotation",
                    },
                    {
                        "batch_id": "batch_0001",
                        "request_id": "req_001",
                        "assembly_accession": "GCF_222222222.1",
                        "taxon_id": "9606",
                        "batch_reason": "single_small_taxon_batch",
                        "resolved_name": "Homo sapiens",
                        "refseq_category": "representative genome",
                        "assembly_level": "Scaffold",
                        "annotation_status": "annotated:Full annotation",
                    }
                ],
                fieldnames=[
                    "batch_id",
                    "request_id",
                    "assembly_accession",
                    "taxon_id",
                    "batch_reason",
                    "resolved_name",
                    "refseq_category",
                    "assembly_level",
                    "annotation_status",
                ],
            )

            self._write_fake_datasets(fake_bin_dir / "datasets")
            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"
            env["HOMOREPEAT_FIXTURES_ROOT"] = str(FIXTURES_ROOT)
            env["HOMOREPEAT_FAKE_DATASETS_FAIL_DOWNLOADS"] = "1"
            env["HOMOREPEAT_FAKE_DATASETS_STATE_DIR"] = str(tmp / "fake_state")

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.download_ncbi_packages",
                    "--batch-manifest",
                    str(selected_batches_path),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(outdir),
                    "--datasets-max-attempts",
                    "3",
                    "--datasets-retry-delay-seconds",
                    "0",
                ],
                env=env,
            )

            manifest_rows = read_tsv(outdir / "download_manifest.tsv")
            self.assertEqual(len(manifest_rows), 2)
            self.assertEqual({row["download_status"] for row in manifest_rows}, {"downloaded"})
            self.assertTrue((outdir / "ncbi_package").exists())
            self.assertFalse((outdir / "batch_0001_ncbi_dataset.zip").exists())
            self.assertEqual({row["download_path"] for row in manifest_rows}, {""})

    def test_download_ncbi_packages_cleans_stale_zip_before_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            planning_dir = tmp / "planning"
            outdir = tmp / "batches" / "batch_0001" / "raw"
            fake_bin_dir = tmp / "fake_bin"
            planning_dir.mkdir(parents=True, exist_ok=True)
            fake_bin_dir.mkdir(parents=True, exist_ok=True)

            selected_batches_path = planning_dir / "selected_batches.tsv"
            write_tsv(
                selected_batches_path,
                [
                    {
                        "batch_id": "batch_0001",
                        "request_id": "req_001",
                        "assembly_accession": "GCF_000001405.40",
                        "taxon_id": "9606",
                        "batch_reason": "single_small_taxon_batch",
                        "resolved_name": "Homo sapiens",
                        "refseq_category": "reference genome",
                        "assembly_level": "Chromosome",
                        "annotation_status": "annotated:Updated annotation",
                    }
                ],
                fieldnames=[
                    "batch_id",
                    "request_id",
                    "assembly_accession",
                    "taxon_id",
                    "batch_reason",
                    "resolved_name",
                    "refseq_category",
                    "assembly_level",
                    "annotation_status",
                ],
            )

            self._write_fake_datasets(fake_bin_dir / "datasets")
            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"
            env["HOMOREPEAT_FIXTURES_ROOT"] = str(FIXTURES_ROOT)
            env["HOMOREPEAT_FAKE_DATASETS_FAIL_INVALID_ZIP_DOWNLOADS"] = "1"
            env["HOMOREPEAT_FAKE_DATASETS_REQUIRE_CLEAN_FILENAME_AFTER_FAILURE"] = "1"
            env["HOMOREPEAT_FAKE_DATASETS_STATE_DIR"] = str(tmp / "fake_state")

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.download_ncbi_packages",
                    "--batch-manifest",
                    str(selected_batches_path),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(outdir),
                    "--datasets-max-attempts",
                    "3",
                    "--datasets-retry-delay-seconds",
                    "0",
                ],
                env=env,
            )

            manifest_rows = read_tsv(outdir / "download_manifest.tsv")
            self.assertEqual(len(manifest_rows), 1)
            self.assertEqual({row["download_status"] for row in manifest_rows}, {"downloaded"})
            self.assertTrue((outdir / "ncbi_package").exists())
            self.assertFalse((outdir / "batch_0001_ncbi_dataset.zip").exists())
            self.assertEqual({row["download_path"] for row in manifest_rows}, {""})

    def test_download_ncbi_packages_keeps_zip_when_cache_dir_is_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            planning_dir = tmp / "planning"
            outdir = tmp / "batches" / "batch_0001" / "raw"
            cache_dir = tmp / "cache"
            fake_bin_dir = tmp / "fake_bin"
            planning_dir.mkdir(parents=True, exist_ok=True)
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            cache_dir.mkdir(parents=True, exist_ok=True)

            selected_batches_path = planning_dir / "selected_batches.tsv"
            write_tsv(
                selected_batches_path,
                [
                    {
                        "batch_id": "batch_0001",
                        "request_id": "req_001",
                        "assembly_accession": "GCF_000001405.40",
                        "taxon_id": "9606",
                        "batch_reason": "single_small_taxon_batch",
                        "resolved_name": "Homo sapiens",
                        "refseq_category": "reference genome",
                        "assembly_level": "Chromosome",
                        "annotation_status": "annotated:Updated annotation",
                    }
                ],
                fieldnames=[
                    "batch_id",
                    "request_id",
                    "assembly_accession",
                    "taxon_id",
                    "batch_reason",
                    "resolved_name",
                    "refseq_category",
                    "assembly_level",
                    "annotation_status",
                ],
            )

            self._write_fake_datasets(fake_bin_dir / "datasets")
            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"
            env["HOMOREPEAT_FIXTURES_ROOT"] = str(FIXTURES_ROOT)

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.download_ncbi_packages",
                    "--batch-manifest",
                    str(selected_batches_path),
                    "--batch-id",
                    "batch_0001",
                    "--cache-dir",
                    str(cache_dir),
                    "--outdir",
                    str(outdir),
                ],
                env=env,
            )

            manifest_rows = read_tsv(outdir / "download_manifest.tsv")
            archive_path = cache_dir / "batch_0001_ncbi_dataset.zip"

            self.assertEqual(len(manifest_rows), 1)
            self.assertTrue((outdir / "ncbi_package").exists())
            self.assertTrue(archive_path.is_file())
            self.assertEqual({row["download_path"] for row in manifest_rows}, {str(archive_path.resolve())})

    def test_download_ncbi_packages_failure_writes_failed_manifest_and_stage_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            planning_dir = tmp / "planning"
            outdir = tmp / "batches" / "batch_0001" / "raw"
            fake_bin_dir = tmp / "fake_bin"
            planning_dir.mkdir(parents=True, exist_ok=True)
            fake_bin_dir.mkdir(parents=True, exist_ok=True)

            selected_batches_path = planning_dir / "selected_batches.tsv"
            write_tsv(
                selected_batches_path,
                [
                    {
                        "batch_id": "batch_0001",
                        "request_id": "req_001",
                        "assembly_accession": "GCF_000001405.40",
                        "taxon_id": "9606",
                        "batch_reason": "single_small_taxon_batch",
                        "resolved_name": "Homo sapiens",
                        "refseq_category": "reference genome",
                        "assembly_level": "Chromosome",
                        "annotation_status": "annotated:Updated annotation",
                    },
                    {
                        "batch_id": "batch_0001",
                        "request_id": "req_001",
                        "assembly_accession": "GCF_222222222.1",
                        "taxon_id": "9606",
                        "batch_reason": "single_small_taxon_batch",
                        "resolved_name": "Homo sapiens",
                        "refseq_category": "representative genome",
                        "assembly_level": "Scaffold",
                        "annotation_status": "annotated:Full annotation",
                    },
                ],
                fieldnames=[
                    "batch_id",
                    "request_id",
                    "assembly_accession",
                    "taxon_id",
                    "batch_reason",
                    "resolved_name",
                    "refseq_category",
                    "assembly_level",
                    "annotation_status",
                ],
            )

            self._write_fake_datasets(fake_bin_dir / "datasets")
            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"
            env["HOMOREPEAT_FIXTURES_ROOT"] = str(FIXTURES_ROOT)
            env["HOMOREPEAT_FAKE_DATASETS_FAIL_DOWNLOADS"] = "5"
            env["HOMOREPEAT_FAKE_DATASETS_STATE_DIR"] = str(tmp / "fake_state")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.download_ncbi_packages",
                    "--batch-manifest",
                    str(selected_batches_path),
                    "--batch-id",
                    "batch_0001",
                    "--stage-status-out",
                    str(outdir / "download_stage_status.json"),
                    "--outdir",
                    str(outdir),
                    "--datasets-max-attempts",
                    "2",
                    "--datasets-retry-delay-seconds",
                    "0",
                ],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

            manifest_rows = read_tsv(outdir / "download_manifest.tsv")
            self.assertEqual(len(manifest_rows), 2)
            self.assertEqual({row["download_status"] for row in manifest_rows}, {"failed"})
            self.assertTrue(all(row["notes"] for row in manifest_rows))

            stage_status = json.loads((outdir / "download_stage_status.json").read_text(encoding="utf-8"))
            self.assertEqual(stage_status["stage"], "download")
            self.assertEqual(stage_status["status"], "failed")
            self.assertEqual(stage_status["batch_id"], "batch_0001")
            self.assertTrue(stage_status["message"])

    def test_normalize_fails_when_downloaded_accession_has_no_normalized_sequences(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            package_root = tmp / "package"
            fake_bin_dir = tmp / "fake_bin"
            outdir = tmp / "normalized"
            taxonomy_db = tmp / "taxonomy.sqlite"
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            taxonomy_db.write_text("", encoding="utf-8")
            self._write_fake_taxon_weaver(fake_bin_dir / "taxon-weaver")

            accession_good = "GCF_GOOD.1"
            accession_missing = "GCF_MISSING_ANNOT.1"
            good_dir = package_root / "ncbi_dataset" / "data" / accession_good
            missing_dir = package_root / "ncbi_dataset" / "data" / accession_missing
            good_dir.mkdir(parents=True, exist_ok=True)
            missing_dir.mkdir(parents=True, exist_ok=True)

            (package_root / "download_manifest.tsv").write_text(
                "\n".join(
                    [
                        "batch_id\tassembly_accession\tdownload_status\tpackage_mode\tdownload_path\trehydrated_path\tchecksum\tfile_size_bytes\tdownload_started_at\tdownload_finished_at\tnotes",
                        f"batch_0001\t{accession_good}\tdownloaded\tdirect_zip\t\t\t\t\t\t\t",
                        f"batch_0001\t{accession_missing}\tdownloaded\tdirect_zip\t\t\t\t\t\t\t",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (package_root / "ncbi_dataset" / "data" / "assembly_data_report.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "accession": accession_good,
                                "assemblyInfo": {"assemblyLevel": "Chromosome", "assemblyType": "haploid"},
                                "organism": {"taxId": 9606, "organismName": "Homo sapiens"},
                            }
                        ),
                        json.dumps(
                            {
                                "accession": accession_missing,
                                "assemblyInfo": {"assemblyLevel": "Chromosome", "assemblyType": "haploid"},
                                "organism": {"taxId": 9606, "organismName": "Homo sapiens"},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (good_dir / f"{accession_good}_genomic.gff").write_text(
                "\n".join(
                    [
                        "chr1\tRefSeq\tgene\t1\t9\t.\t+\t.\tID=gene1;gene=GENE1",
                        "chr1\tRefSeq\tmRNA\t1\t9\t.\t+\t.\tID=rna1;Parent=gene1;transcript_id=NM_TEST.1;gene=GENE1",
                        "chr1\tRefSeq\tCDS\t1\t9\t.\t+\t0\tID=cds-NP_TEST.1-1;Parent=rna1;protein_id=NP_TEST.1;transcript_id=NM_TEST.1;transl_table=1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (good_dir / f"{accession_good}_cds_from_genomic.fna").write_text(
                "\n".join(
                    [
                        ">lcl|cds1 [gene=GENE1] [protein_id=NP_TEST.1] [transcript_id=NM_TEST.1] [transl_table=1]",
                        "ATGGCCGCC",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.normalize_cds",
                    "--package-dir",
                    str(package_root),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--batch-id",
                    "batch_0001",
                    "--stage-status-out",
                    str(outdir / "normalize_stage_status.json"),
                    "--outdir",
                    str(outdir),
                ],
                cwd=REPO_ROOT,
                env={**CLI_ENV, **env},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("produced no normalized CDS sequences", result.stderr)

            stage_status = json.loads((outdir / "normalize_stage_status.json").read_text(encoding="utf-8"))
            self.assertEqual(stage_status["status"], "failed")
            self.assertIn(accession_missing, stage_status["message"])

    def test_translate_warns_but_succeeds_when_one_accession_has_no_retained_proteins(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            outdir = tmp / "translated"
            outdir.mkdir(parents=True, exist_ok=True)

            sequences_tsv = tmp / "sequences.tsv"
            cds_fasta = tmp / "cds.fna"

            write_tsv(
                tmp / "download_manifest.tsv",
                [
                    {
                        "batch_id": "batch_0001",
                        "assembly_accession": "GCF_KEEP.1",
                        "download_status": "downloaded",
                        "package_mode": "direct_zip",
                        "download_path": "",
                        "rehydrated_path": "",
                        "checksum": "",
                        "file_size_bytes": "",
                        "download_started_at": "",
                        "download_finished_at": "",
                        "notes": "",
                    },
                    {
                        "batch_id": "batch_0001",
                        "assembly_accession": "GCF_DROP.1",
                        "download_status": "downloaded",
                        "package_mode": "direct_zip",
                        "download_path": "",
                        "rehydrated_path": "",
                        "checksum": "",
                        "file_size_bytes": "",
                        "download_started_at": "",
                        "download_finished_at": "",
                        "notes": "",
                    },
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
                tmp / "genomes.tsv",
                [
                    {
                        "genome_id": "genome_keep",
                        "source": "ncbi_datasets",
                        "accession": "GCF_KEEP.1",
                        "genome_name": "keep",
                        "assembly_type": "haploid",
                        "taxon_id": "9606",
                        "assembly_level": "Chromosome",
                        "species_name": "Homo sapiens",
                        "notes": "",
                    },
                    {
                        "genome_id": "genome_drop",
                        "source": "ncbi_datasets",
                        "accession": "GCF_DROP.1",
                        "genome_name": "drop",
                        "assembly_type": "haploid",
                        "taxon_id": "9606",
                        "assembly_level": "Chromosome",
                        "species_name": "Homo sapiens",
                        "notes": "",
                    },
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
                sequences_tsv,
                [
                    {
                        "sequence_id": "seq_keep",
                        "genome_id": "genome_keep",
                        "sequence_name": "SEQ_KEEP",
                        "sequence_length": "9",
                        "gene_symbol": "GENE1",
                        "transcript_id": "NM_KEEP.1",
                        "isoform_id": "NP_KEEP.1",
                        "assembly_accession": "GCF_KEEP.1",
                        "taxon_id": "9606",
                        "source_record_id": "rec_keep",
                        "protein_external_id": "NP_KEEP.1",
                        "translation_table": "1",
                        "gene_group": "GENE1",
                        "linkage_status": "gff",
                        "partial_status": "",
                    },
                    {
                        "sequence_id": "seq_drop",
                        "genome_id": "genome_drop",
                        "sequence_name": "SEQ_DROP",
                        "sequence_length": "9",
                        "gene_symbol": "GENE2",
                        "transcript_id": "NM_DROP.1",
                        "isoform_id": "NP_DROP.1",
                        "assembly_accession": "GCF_DROP.1",
                        "taxon_id": "9606",
                        "source_record_id": "rec_drop",
                        "protein_external_id": "NP_DROP.1",
                        "translation_table": "1",
                        "gene_group": "GENE2",
                        "linkage_status": "gff",
                        "partial_status": "partial",
                    },
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
            cds_fasta.write_text(
                "\n".join(
                    [
                        ">seq_keep",
                        "ATGGCCGCC",
                        ">seq_drop",
                        "ATGGCCGCC",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            shutil.copyfile(tmp / "download_manifest.tsv", outdir / "download_manifest.tsv")
            shutil.copyfile(tmp / "genomes.tsv", outdir / "genomes.tsv")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.translate_cds",
                    "--sequences-tsv",
                    str(sequences_tsv),
                    "--cds-fasta",
                    str(cds_fasta),
                    "--batch-id",
                    "batch_0001",
                    "--stage-status-out",
                    str(outdir / "translate_stage_status.json"),
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
                    f"translate_cds failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            stage_status = json.loads((outdir / "translate_stage_status.json").read_text(encoding="utf-8"))
            proteins_rows = read_tsv(outdir / "proteins.tsv")
            warning_rows = read_tsv(outdir / "normalization_warnings.tsv")
            validation = json.loads((outdir / "acquisition_validation.json").read_text(encoding="utf-8"))

            self.assertEqual(stage_status["status"], "success")
            self.assertEqual(len(proteins_rows), 1)
            self.assertEqual(proteins_rows[0]["assembly_accession"], "GCF_KEEP.1")
            self.assertIn("GCF_DROP.1", validation["failed_accessions"])
            self.assertEqual(validation["status"], "warn")
            self.assertIn(
                "translate stage retained no proteins for accessions: GCF_DROP.1",
                validation["notes"],
            )
            self.assertEqual(
                [row["warning_code"] for row in warning_rows],
                ["partial_cds", "accession_no_retained_proteins"],
            )

    def test_translate_accepts_vertebrate_mitochondrial_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            outdir = tmp / "translated"
            outdir.mkdir(parents=True, exist_ok=True)

            sequences_tsv = tmp / "sequences.tsv"
            cds_fasta = tmp / "cds.fna"

            write_tsv(
                outdir / "download_manifest.tsv",
                [
                    {
                        "batch_id": "batch_0001",
                        "assembly_accession": "GCF_MT.1",
                        "download_status": "downloaded",
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
                outdir / "genomes.tsv",
                [
                    {
                        "genome_id": "genome_mt",
                        "source": "ncbi_datasets",
                        "accession": "GCF_MT.1",
                        "genome_name": "mt",
                        "assembly_type": "haploid",
                        "taxon_id": "10090",
                        "assembly_level": "Chromosome",
                        "species_name": "Mus musculus",
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
                sequences_tsv,
                [
                    {
                        "sequence_id": "seq_mt",
                        "genome_id": "genome_mt",
                        "sequence_name": "rna-ND1",
                        "sequence_length": "9",
                        "gene_symbol": "ND1",
                        "transcript_id": "rna-ND1",
                        "isoform_id": "NP_MT.1",
                        "assembly_accession": "GCF_MT.1",
                        "taxon_id": "10090",
                        "source_record_id": "cds-NP_MT.1",
                        "protein_external_id": "NP_MT.1",
                        "translation_table": "2",
                        "gene_group": "ND1",
                        "linkage_status": "gff",
                        "partial_status": "",
                    }
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
            cds_fasta.write_text(">seq_mt\nATATGATAA\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.translate_cds",
                    "--sequences-tsv",
                    str(sequences_tsv),
                    "--cds-fasta",
                    str(cds_fasta),
                    "--batch-id",
                    "batch_0001",
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
                    f"translate_cds failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            proteins_rows = read_tsv(outdir / "proteins.tsv")
            self.assertEqual(len(proteins_rows), 1)
            self.assertEqual(proteins_rows[0]["gene_symbol"], "ND1")
            self.assertEqual(proteins_rows[0]["protein_length"], "2")
            self.assertIn(f">{proteins_rows[0]['protein_id']}", (outdir / "proteins.faa").read_text(encoding="utf-8"))
            self.assertIn("\nMW\n", (outdir / "proteins.faa").read_text(encoding="utf-8"))

    def test_translate_fails_when_no_accession_yields_retained_proteins(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            outdir = tmp / "translated"
            outdir.mkdir(parents=True, exist_ok=True)

            sequences_tsv = tmp / "sequences.tsv"
            cds_fasta = tmp / "cds.fna"

            write_tsv(
                outdir / "download_manifest.tsv",
                [
                    {
                        "batch_id": "batch_0001",
                        "assembly_accession": "GCF_UNSUPPORTED.1",
                        "download_status": "downloaded",
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
                outdir / "genomes.tsv",
                [
                    {
                        "genome_id": "genome_unsupported",
                        "source": "ncbi_datasets",
                        "accession": "GCF_UNSUPPORTED.1",
                        "genome_name": "unsupported",
                        "assembly_type": "haploid",
                        "taxon_id": "9606",
                        "assembly_level": "Chromosome",
                        "species_name": "Homo sapiens",
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
                sequences_tsv,
                [
                    {
                        "sequence_id": "seq_unsupported",
                        "genome_id": "genome_unsupported",
                        "sequence_name": "SEQ_UNSUPPORTED",
                        "sequence_length": "9",
                        "gene_symbol": "GENE_BAD",
                        "transcript_id": "NM_BAD.1",
                        "isoform_id": "NP_BAD.1",
                        "assembly_accession": "GCF_UNSUPPORTED.1",
                        "taxon_id": "9606",
                        "source_record_id": "rec_bad",
                        "protein_external_id": "NP_BAD.1",
                        "translation_table": "99",
                        "gene_group": "GENE_BAD",
                        "linkage_status": "gff",
                        "partial_status": "",
                    }
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
            cds_fasta.write_text(">seq_unsupported\nATGGCCTAA\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.translate_cds",
                    "--sequences-tsv",
                    str(sequences_tsv),
                    "--cds-fasta",
                    str(cds_fasta),
                    "--batch-id",
                    "batch_0001",
                    "--stage-status-out",
                    str(outdir / "translate_stage_status.json"),
                    "--outdir",
                    str(outdir),
                ],
                cwd=REPO_ROOT,
                env=CLI_ENV,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("produced no retained proteins", result.stderr)

            stage_status = json.loads((outdir / "translate_stage_status.json").read_text(encoding="utf-8"))
            validation = json.loads((outdir / "acquisition_validation.json").read_text(encoding="utf-8"))
            warning_rows = read_tsv(outdir / "normalization_warnings.tsv")

            self.assertEqual(stage_status["status"], "failed")
            self.assertIn("GCF_UNSUPPORTED.1", stage_status["message"])
            self.assertEqual(validation["status"], "fail")
            self.assertIn("GCF_UNSUPPORTED.1", validation["failed_accessions"])
            self.assertIn(
                "translate stage failed: Batch batch_0001 produced no retained proteins for normalized accessions: GCF_UNSUPPORTED.1",
                validation["notes"],
            )
            self.assertEqual(
                [row["warning_code"] for row in warning_rows],
                ["unsupported_translation_table", "accession_unsupported_translation_table"],
            )

    def test_normalize_deduplicates_identical_cds_records_and_keeps_distinct_variants(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            package_root = tmp / "package"
            accession = "GCF_TEST_DUP.1"
            accession_dir = package_root / "ncbi_dataset" / "data" / accession
            fake_bin_dir = tmp / "fake_bin"
            outdir = tmp / "normalized"
            taxonomy_db = tmp / "taxonomy.sqlite"
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            accession_dir.mkdir(parents=True, exist_ok=True)
            taxonomy_db.write_text("", encoding="utf-8")
            self._write_fake_taxon_weaver(fake_bin_dir / "taxon-weaver")

            (package_root / "ncbi_dataset" / "data" / "assembly_data_report.jsonl").write_text(
                json.dumps(
                    {
                        "accession": accession,
                        "assemblyInfo": {
                            "assemblyLevel": "Chromosome",
                            "assemblyType": "haploid",
                        },
                        "organism": {"taxId": 9606, "organismName": "Homo sapiens"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_genomic.gff").write_text(
                "\n".join(
                    [
                        "chr1\tRefSeq\tgene\t1\t9\t.\t+\t.\tID=gene1;gene=GENE1",
                        "chr1\tRefSeq\tmRNA\t1\t9\t.\t+\t.\tID=rna1;Parent=gene1;transcript_id=NM_TEST.1;gene=GENE1",
                        "chr1\tRefSeq\tCDS\t1\t9\t.\t+\t0\tID=cds-NP_TEST.1-1;Parent=rna1;protein_id=NP_TEST.1;transcript_id=NM_TEST.1;transl_table=1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_cds_from_genomic.fna").write_text(
                "\n".join(
                    [
                        ">lcl|cds1 [gene=GENE1] [protein_id=NP_TEST.1] [transcript_id=NM_TEST.1] [transl_table=1]",
                        "ATGGCCGCC",
                        ">lcl|cds2 [gene=GENE1] [protein_id=NP_TEST.1] [transcript_id=NM_TEST.1] [transl_table=1]",
                        "ATGGCCGCC",
                        ">lcl|cds3 [gene=GENE1] [protein_id=NP_TEST.1] [transcript_id=NM_TEST.1] [transl_table=1]",
                        "ATGGCCGCT",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.normalize_cds",
                    "--package-dir",
                    str(package_root),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(outdir),
                ],
                env=env,
            )

            sequences = read_tsv(outdir / "sequences.tsv")
            warnings_rows = read_tsv(outdir / "normalization_warnings.tsv")
            cds_records = read_tsv(outdir / "genomes.tsv")

            self.assertEqual(len(cds_records), 1)
            self.assertEqual(len(sequences), 2)
            self.assertEqual(len({row["sequence_id"] for row in sequences}), 2)
            self.assertEqual(
                [row["warning_code"] for row in warnings_rows],
                ["conflicting_duplicate_cds_key", "ambiguous_sequence_identity_resolved"],
            )
            self.assertEqual((outdir / "cds.fna").read_text(encoding="utf-8").count(">"), 2)

    def test_normalize_disambiguates_ambiguous_transcript_level_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            package_root = tmp / "package"
            accession = "GCF_TEST_AMBIG.1"
            accession_dir = package_root / "ncbi_dataset" / "data" / accession
            fake_bin_dir = tmp / "fake_bin"
            outdir = tmp / "normalized"
            taxonomy_db = tmp / "taxonomy.sqlite"
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            accession_dir.mkdir(parents=True, exist_ok=True)
            taxonomy_db.write_text("", encoding="utf-8")
            self._write_fake_taxon_weaver(fake_bin_dir / "taxon-weaver")

            (package_root / "ncbi_dataset" / "data" / "assembly_data_report.jsonl").write_text(
                json.dumps(
                    {
                        "accession": accession,
                        "assemblyInfo": {
                            "assemblyLevel": "Chromosome",
                            "assemblyType": "haploid",
                        },
                        "organism": {"taxId": 9606, "organismName": "Homo sapiens"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_genomic.gff").write_text(
                "\n".join(
                    [
                        "chr1\tRefSeq\tgene\t1\t9\t.\t+\t.\tID=gene1;gene=LOC1",
                        "chr1\tRefSeq\tmRNA\t1\t9\t.\t+\t.\tID=rna1;Parent=gene1;transcript_id=XM_SHARED.1;gene=LOC1",
                        "chr1\tRefSeq\tCDS\t1\t9\t.\t+\t0\tID=cds-LOC1;Parent=rna1;protein_id=XP_ONE.1;transcript_id=XM_SHARED.1;transl_table=1",
                        "chr1\tRefSeq\tgene\t20\t28\t.\t+\t.\tID=gene2;gene=LOC2",
                        "chr1\tRefSeq\tmRNA\t20\t28\t.\t+\t.\tID=rna2;Parent=gene2;transcript_id=XM_SHARED.1;gene=LOC2",
                        "chr1\tRefSeq\tCDS\t20\t28\t.\t+\t0\tID=cds-LOC2;Parent=rna2;protein_id=XP_TWO.1;transcript_id=XM_SHARED.1;transl_table=1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_cds_from_genomic.fna").write_text(
                "\n".join(
                    [
                        ">lcl|chr1_cds_XP_ONE.1_1 [gene=LOC1] [protein_id=XP_ONE.1] [transl_table=1]",
                        "ATGGCCGCC",
                        ">lcl|chr1_cds_XP_TWO.1_2 [gene=LOC2] [protein_id=XP_TWO.1] [transl_table=1]",
                        "ATGGCCGCC",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.normalize_cds",
                    "--package-dir",
                    str(package_root),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(outdir),
                ],
                env=env,
            )

            sequences = read_tsv(outdir / "sequences.tsv")
            warnings_rows = read_tsv(outdir / "normalization_warnings.tsv")

            self.assertEqual(len(sequences), 2)
            self.assertEqual(len({row["sequence_id"] for row in sequences}), 2)
            self.assertIn(f"{accession}::XM_SHARED.1", {row["sequence_id"] for row in sequences})
            self.assertEqual({row["gene_symbol"] for row in sequences}, {"LOC1", "LOC2"})
            self.assertEqual(
                [row["warning_code"] for row in warnings_rows],
                ["ambiguous_sequence_identity_resolved"],
            )

    def test_normalize_uses_source_backed_keys_for_shared_gene_segment_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            package_root = tmp / "package"
            accession = "GCF_TEST_SEGMENTS.1"
            accession_dir = package_root / "ncbi_dataset" / "data" / accession
            fake_bin_dir = tmp / "fake_bin"
            outdir = tmp / "normalized"
            taxonomy_db = tmp / "taxonomy.sqlite"
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            accession_dir.mkdir(parents=True, exist_ok=True)
            taxonomy_db.write_text("", encoding="utf-8")
            self._write_fake_taxon_weaver(fake_bin_dir / "taxon-weaver")

            (package_root / "ncbi_dataset" / "data" / "assembly_data_report.jsonl").write_text(
                json.dumps(
                    {
                        "accession": accession,
                        "assemblyInfo": {
                            "assemblyLevel": "Chromosome",
                            "assemblyType": "haploid",
                        },
                        "organism": {"taxId": 9606, "organismName": "Homo sapiens"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_genomic.gff").write_text(
                "\n".join(
                    [
                        "chr1\tRefSeq\tgene\t1\t9\t.\t+\t.\tID=gene1;gene=LOC_SEG1",
                        "chr1\tRefSeq\tC_gene_segment\t1\t9\t.\t+\t.\tID=id-LOC_SEG1;Parent=gene1;gene=LOC_SEG1;standard_name=Shared segment",
                        "chr1\tRefSeq\tCDS\t1\t9\t.\t+\t0\tID=cds-LOC_SEG1;Parent=id-LOC_SEG1;gene=LOC_SEG1;partial=true",
                        "chr1\tRefSeq\tgene\t20\t28\t.\t+\t.\tID=gene2;gene=LOC_SEG2",
                        "chr1\tRefSeq\tC_gene_segment\t20\t28\t.\t+\t.\tID=id-LOC_SEG2;Parent=gene2;gene=LOC_SEG2;standard_name=Shared segment",
                        "chr1\tRefSeq\tCDS\t20\t28\t.\t+\t0\tID=cds-LOC_SEG2;Parent=id-LOC_SEG2;gene=LOC_SEG2;partial=true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_cds_from_genomic.fna").write_text(
                "\n".join(
                    [
                        ">lcl|chr1_cds_1 [gene=LOC_SEG1] [exception=rearrangement required for product] [gbkey=CDS]",
                        "ATGGCCGCC",
                        ">lcl|chr1_cds_2 [gene=LOC_SEG2] [exception=rearrangement required for product] [gbkey=CDS]",
                        "ATGAAAGCC",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.normalize_cds",
                    "--package-dir",
                    str(package_root),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(outdir),
                ],
                env=env,
            )

            sequences = read_tsv(outdir / "sequences.tsv")
            warnings_rows = read_tsv(outdir / "normalization_warnings.tsv")

            self.assertEqual(len(sequences), 2)
            self.assertEqual(len({row["sequence_id"] for row in sequences}), 2)
            self.assertEqual({row["source_record_id"] for row in sequences}, {"cds-LOC_SEG1", "cds-LOC_SEG2"})
            self.assertEqual({row["linkage_status"] for row in sequences}, {"gff_gene_segment_alias"})
            self.assertEqual({row["transcript_id"] for row in sequences}, {"Shared segment"})
            self.assertEqual(warnings_rows, [])

    def test_normalize_filters_alt_loci_using_sequence_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            package_root = tmp / "package"
            accession = "GCF_TEST_PRIMARY.1"
            accession_dir = package_root / "ncbi_dataset" / "data" / accession
            fake_bin_dir = tmp / "fake_bin"
            outdir = tmp / "normalized"
            taxonomy_db = tmp / "taxonomy.sqlite"
            fake_bin_dir.mkdir(parents=True, exist_ok=True)
            accession_dir.mkdir(parents=True, exist_ok=True)
            taxonomy_db.write_text("", encoding="utf-8")
            self._write_fake_taxon_weaver(fake_bin_dir / "taxon-weaver")

            (package_root / "ncbi_dataset" / "data" / "assembly_data_report.jsonl").write_text(
                json.dumps(
                    {
                        "accession": accession,
                        "assemblyInfo": {
                            "assemblyLevel": "Chromosome",
                            "assemblyType": "haploid",
                        },
                        "organism": {"taxId": 9606, "organismName": "Homo sapiens"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / "sequence_report.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "assemblyAccession": accession,
                                "assemblyUnit": "Primary Assembly",
                                "refseqAccession": "NC_000001.11",
                                "role": "assembled-molecule",
                            }
                        ),
                        json.dumps(
                            {
                                "assemblyAccession": accession,
                                "assemblyUnit": "ALT_REF_LOCI_1",
                                "refseqAccession": "NT_187515.1",
                                "role": "alt-scaffold",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_genomic.gff").write_text(
                "\n".join(
                    [
                        "NC_000001.11\tRefSeq\tgene\t1\t9\t.\t+\t.\tID=gene1;gene=GENE1",
                        "NC_000001.11\tRefSeq\tmRNA\t1\t9\t.\t+\t.\tID=rna-NM_MAIN.1;Parent=gene1;transcript_id=NM_MAIN.1;gene=GENE1",
                        "NC_000001.11\tRefSeq\tCDS\t1\t9\t.\t+\t0\tID=cds-NP_MAIN.1;Parent=rna-NM_MAIN.1;protein_id=NP_MAIN.1;gene=GENE1;gbkey=CDS",
                        "NT_187515.1\tRefSeq\tgene\t1\t9\t.\t+\t.\tID=gene2;gene=GENE2",
                        "NT_187515.1\tRefSeq\tmRNA\t1\t9\t.\t+\t.\tID=rna-NM_ALT.1;Parent=gene2;transcript_id=NM_ALT.1;gene=GENE2",
                        "NT_187515.1\tRefSeq\tCDS\t1\t9\t.\t+\t0\tID=cds-NP_ALT.1;Parent=rna-NM_ALT.1;protein_id=NP_ALT.1;gene=GENE2;gbkey=CDS",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (accession_dir / f"{accession}_cds_from_genomic.fna").write_text(
                "\n".join(
                    [
                        ">lcl|NC_000001.11_cds_NP_MAIN.1_1 [gene=GENE1] [protein=main protein [primary]] [protein_id=NP_MAIN.1] [gbkey=CDS]",
                        "ATGGCCGCC",
                        ">lcl|NT_187515.1_cds_NP_ALT.1_2 [gene=GENE2] [protein=alt protein [alt]] [protein_id=NP_ALT.1] [gbkey=CDS]",
                        "ATGAAAGCC",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            env = dict(os.environ)
            env["PATH"] = f"{fake_bin_dir}:{env.get('PATH', '')}"

            self._run_cli(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.normalize_cds",
                    "--package-dir",
                    str(package_root),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--batch-id",
                    "batch_0001",
                    "--outdir",
                    str(outdir),
                ],
                env=env,
            )

            sequences = read_tsv(outdir / "sequences.tsv")
            warnings_rows = read_tsv(outdir / "normalization_warnings.tsv")

            self.assertEqual(len(sequences), 1)
            self.assertEqual(sequences[0]["gene_symbol"], "GENE1")
            self.assertEqual(sequences[0]["protein_external_id"], "NP_MAIN.1")
            self.assertEqual(sequences[0]["linkage_status"], "gff")
            self.assertEqual(warnings_rows, [])
            self.assertEqual((outdir / "cds.fna").read_text(encoding="utf-8").count(">"), 1)

    def _run_cli(self, command: list[str], *, env: dict[str, str]) -> None:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env={**CLI_ENV, **env},
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                f"Command failed with exit code {result.returncode}: {' '.join(command)}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

    def _write_fake_datasets(self, path: Path) -> None:
        script = textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import os
            import pathlib
            import shutil
            import sys
            import zipfile

            def zip_tree(source_root: pathlib.Path, destination_zip: pathlib.Path) -> None:
                destination_zip.parent.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(destination_zip, "w") as archive:
                    for file_path in sorted(source_root.rglob("*")):
                        if file_path.is_file():
                            archive.write(file_path, file_path.relative_to(source_root))

            args = sys.argv[1:]
            fixtures_root = pathlib.Path(os.environ["HOMOREPEAT_FIXTURES_ROOT"])
            state_dir = pathlib.Path(os.environ.get("HOMOREPEAT_FAKE_DATASETS_STATE_DIR", "."))
            state_dir.mkdir(parents=True, exist_ok=True)

            if args[:3] == ["download", "genome", "accession"]:
                inputfile = pathlib.Path(args[args.index("--inputfile") + 1])
                filename = pathlib.Path(args[args.index("--filename") + 1])
                fail_downloads = int(os.environ.get("HOMOREPEAT_FAKE_DATASETS_FAIL_DOWNLOADS", "0"))
                fail_invalid_zip_downloads = int(
                    os.environ.get("HOMOREPEAT_FAKE_DATASETS_FAIL_INVALID_ZIP_DOWNLOADS", "0")
                )
                require_clean_filename = os.environ.get(
                    "HOMOREPEAT_FAKE_DATASETS_REQUIRE_CLEAN_FILENAME_AFTER_FAILURE", ""
                ) == "1"
                counter_path = state_dir / "download_attempts.txt"
                attempt_count = int(counter_path.read_text(encoding="utf-8")) if counter_path.exists() else 0
                attempt_count += 1
                counter_path.write_text(str(attempt_count), encoding="utf-8")
                if attempt_count <= fail_downloads:
                    print(
                        'Error: [gateway] Post "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/dataset_report": '
                        "POST https://api.ncbi.nlm.nih.gov/datasets/v2/genome/dataset_report giving up after 11 attempt(s)",
                        file=sys.stderr,
                    )
                    raise SystemExit(1)
                if attempt_count <= fail_invalid_zip_downloads:
                    filename.parent.mkdir(parents=True, exist_ok=True)
                    filename.write_bytes(b"broken zip payload")
                    print("Error: Internal error (invalid zip archive). Please try again", file=sys.stderr)
                    raise SystemExit(1)
                if require_clean_filename and filename.exists():
                    print("stale output zip remains before retry", file=sys.stderr)
                    raise SystemExit(1)
                accessions = {line.strip() for line in inputfile.read_text(encoding="utf-8").splitlines() if line.strip()}
                if accessions == {"GCF_000001405.40", "GCF_222222222.1"}:
                    zip_tree(fixtures_root / "batch_a", filename)
                    raise SystemExit(0)
                if accessions == {"GCF_000001405.40"}:
                    zip_tree(fixtures_root / "batch_a", filename)
                    raise SystemExit(0)
                if accessions == {"GCF_000001635.27"}:
                    zip_tree(fixtures_root / "batch_b", filename)
                    raise SystemExit(0)
                raise SystemExit(1)

            if args[:1] == ["rehydrate"]:
                raise SystemExit(0)

            raise SystemExit(1)
            """
        )
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def _write_fake_taxon_weaver(self, path: Path) -> None:
        script = textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import sys

            args = sys.argv[1:]
            if args[:1] == ["build-info"]:
                print(json.dumps({"taxonomy_build_version": "2026-04-05"}))
                raise SystemExit(0)

            if args[:1] == ["inspect-lineage"]:
                taxid = args[args.index("--taxid") + 1]
                if taxid == "9606":
                    print(json.dumps({
                        "taxid": 9606,
                        "lineage": [
                            {"taxid": 1, "rank": "no rank", "name": "root"},
                            {"taxid": 9605, "rank": "genus", "name": "Homo"},
                            {"taxid": 9606, "rank": "species", "name": "Homo sapiens"},
                        ],
                    }))
                    raise SystemExit(0)
                if taxid == "10090":
                    print(json.dumps({
                        "taxid": 10090,
                        "lineage": [
                            {"taxid": 1, "rank": "no rank", "name": "root"},
                            {"taxid": 10088, "rank": "genus", "name": "Mus"},
                            {"taxid": 10090, "rank": "species", "name": "Mus musculus"},
                        ],
                    }))
                    raise SystemExit(0)
                raise SystemExit(1)

            raise SystemExit(1)
            """
        )
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


if __name__ == "__main__":
    unittest.main()
