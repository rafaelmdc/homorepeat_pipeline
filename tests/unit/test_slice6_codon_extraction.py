from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from homorepeat.detection.codon_extract import build_codon_usage_rows, extract_call_codons
from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, build_call_row, validate_call_row
from homorepeat.io.tsv_io import read_tsv, write_tsv


from tests.test_support import CLI_ENV, REPO_ROOT, cli_command


class SliceSixCodonExtractionTest(unittest.TestCase):
    def test_extract_call_codons_returns_expected_slice(self) -> None:
        result = extract_call_codons(
            "ATGGCTGCTGCTGCTGCTGCT",
            aa_start=2,
            aa_end=7,
            aa_sequence="AAAAAA",
            translation_table="1",
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.codon_sequence, "GCTGCTGCTGCTGCTGCT")

    def test_extract_call_codons_rejects_translation_mismatch(self) -> None:
        result = extract_call_codons(
            "ATGGCTGCTGCTGCTGCTGCT",
            aa_start=2,
            aa_end=7,
            aa_sequence="AAAAAQ",
            translation_table="1",
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.codon_sequence, "")
        self.assertEqual(result.warning_message, "codon slice translation does not match amino-acid tract")

    def test_build_codon_usage_rows_reports_per_amino_acid_fractions(self) -> None:
        call_row = build_call_row(
            method="seed_extend",
            genome_id="genome_001",
            taxon_id="9606",
            sequence_id="seq_001",
            protein_id="prot_001",
            repeat_residue="Q",
            start=2,
            end=7,
            aa_sequence="QAQAQQ",
        )
        call_row["codon_sequence"] = "CAAGCTCAGGCTCAACAG"

        usage_rows = build_codon_usage_rows(call_row, translation_table="1")

        self.assertEqual(
            [
                (row["amino_acid"], row["codon"], row["codon_count"], row["codon_fraction"])
                for row in usage_rows
            ],
            [
                ("A", "GCT", 2, "1.0000000000"),
                ("Q", "CAA", 2, "0.5000000000"),
                ("Q", "CAG", 2, "0.5000000000"),
            ],
        )

    def test_extract_call_codons_accepts_table_two_slice(self) -> None:
        result = extract_call_codons(
            "ATATGATAA",
            aa_start=1,
            aa_end=2,
            aa_sequence="MW",
            translation_table="2",
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.codon_sequence, "ATATGA")

    def test_build_codon_usage_rows_supports_table_two(self) -> None:
        call_row = build_call_row(
            method="pure",
            genome_id="genome_001",
            taxon_id="10090",
            sequence_id="seq_mt_001",
            protein_id="prot_mt_001",
            repeat_residue="W",
            start=1,
            end=2,
            aa_sequence="MW",
        )
        call_row["codon_sequence"] = "ATATGA"

        usage_rows = build_codon_usage_rows(call_row, translation_table="2")

        self.assertEqual(
            [
                (row["amino_acid"], row["codon"], row["codon_count"], row["codon_fraction"])
                for row in usage_rows
            ],
            [
                ("M", "ATA", 1, "1.0000000000"),
                ("W", "TGA", 1, "1.0000000000"),
            ],
        )

    def test_extract_repeat_codons_cli_enriches_successful_rows_and_warns_on_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            acquisition_dir = tmp / "merged" / "acquisition"
            calls_dir = tmp / "merged" / "calls"
            outdir = tmp / "merged" / "calls_with_codons"
            acquisition_dir.mkdir(parents=True, exist_ok=True)
            calls_dir.mkdir(parents=True, exist_ok=True)

            sequences_tsv = acquisition_dir / "sequences.tsv"
            cds_fasta = acquisition_dir / "cds.fna"
            calls_tsv = calls_dir / "pure_calls.tsv"

            write_tsv(
                sequences_tsv,
                [
                    {
                        "sequence_id": "seq_001",
                        "genome_id": "genome_001",
                        "sequence_name": "tx1",
                        "sequence_length": 21,
                        "sequence_path": str(cds_fasta.resolve()),
                        "gene_symbol": "GENE1",
                        "transcript_id": "tx1",
                        "isoform_id": "tx1",
                        "assembly_accession": "GCF_TEST_1.1",
                        "taxon_id": "9606",
                        "source_record_id": "cds-tx1",
                        "protein_external_id": "NP_TEST.1",
                        "translation_table": "1",
                        "gene_group": "GENE1",
                        "linkage_status": "gff_transcript",
                        "partial_status": "",
                    }
                ],
                fieldnames=[
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
                ],
            )
            cds_fasta.write_text(">seq_001\nATGGCTGCTGCTGCTGCTGCT\n", encoding="utf-8")

            success_row = build_call_row(
                method="pure",
                genome_id="genome_001",
                taxon_id="9606",
                sequence_id="seq_001",
                protein_id="prot_001",
                repeat_residue="A",
                start=2,
                end=7,
                aa_sequence="AAAAAA",
                source_file=str((acquisition_dir / "proteins.faa").resolve()),
                merge_rule="contiguous_run",
            )
            mismatch_row = build_call_row(
                method="threshold",
                genome_id="genome_001",
                taxon_id="9606",
                sequence_id="seq_001",
                protein_id="prot_001",
                repeat_residue="A",
                start=2,
                end=7,
                aa_sequence="AAAAAQ",
                source_file=str((acquisition_dir / "proteins.faa").resolve()),
                window_definition="A6/8",
                merge_rule="merge_adjacent_or_overlap",
            )
            write_tsv(calls_tsv, [success_row, mismatch_row], fieldnames=CALL_FIELDNAMES)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.extract_repeat_codons",
                    "--calls-tsv",
                    str(calls_tsv),
                    "--sequences-tsv",
                    str(sequences_tsv),
                    "--cds-fasta",
                    str(cds_fasta),
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
                    f"extract_repeat_codons.py failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            enriched_rows = read_tsv(outdir / "pure_calls.tsv")
            warning_rows = read_tsv(outdir / "pure_calls_codon_warnings.tsv")
            codon_usage_rows = read_tsv(outdir / "pure_calls_codon_usage.tsv")

            self.assertEqual(len(enriched_rows), 2)
            for row in enriched_rows:
                validate_call_row(row)
                self.assertEqual(row["codon_metric_name"], "")
                self.assertEqual(row["codon_metric_value"], "")

            self.assertEqual(enriched_rows[0]["codon_sequence"], "GCTGCTGCTGCTGCTGCT")
            self.assertEqual(len(enriched_rows[0]["codon_sequence"]), 18)
            self.assertEqual(enriched_rows[1]["codon_sequence"], "")

            self.assertEqual(len(codon_usage_rows), 1)
            self.assertEqual(codon_usage_rows[0]["call_id"], success_row["call_id"])
            self.assertEqual(codon_usage_rows[0]["amino_acid"], "A")
            self.assertEqual(codon_usage_rows[0]["codon"], "GCT")
            self.assertEqual(codon_usage_rows[0]["codon_count"], "6")
            self.assertEqual(codon_usage_rows[0]["codon_fraction"], "1.0000000000")

            self.assertEqual(len(warning_rows), 1)
            self.assertEqual(warning_rows[0]["warning_code"], "codon_slice_failed")
            self.assertEqual(warning_rows[0]["warning_scope"], "call")
            self.assertEqual(warning_rows[0]["sequence_id"], "seq_001")
            self.assertEqual(warning_rows[0]["protein_id"], "prot_001")
            self.assertEqual(
                warning_rows[0]["warning_message"],
                "codon slice translation does not match amino-acid tract",
            )

    def test_extract_repeat_codons_cli_failure_writes_stage_status_and_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            acquisition_dir = tmp / "merged" / "acquisition"
            calls_dir = tmp / "merged" / "calls"
            outdir = tmp / "merged" / "calls_with_codons"
            acquisition_dir.mkdir(parents=True, exist_ok=True)
            calls_dir.mkdir(parents=True, exist_ok=True)

            calls_tsv = calls_dir / "pure_calls.tsv"
            cds_fasta = acquisition_dir / "cds.fna"
            status_path = outdir / "finalize_status.json"

            build_row = build_call_row(
                method="pure",
                genome_id="genome_001",
                taxon_id="9606",
                sequence_id="seq_missing",
                protein_id="prot_001",
                repeat_residue="A",
                start=2,
                end=7,
                aa_sequence="AAAAAA",
            )
            write_tsv(calls_tsv, [build_row], fieldnames=CALL_FIELDNAMES)
            cds_fasta.write_text(">seq_missing\nATGGCTGCTGCTGCTGCTGCT\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.extract_repeat_codons",
                    "--calls-tsv",
                    str(calls_tsv),
                    "--sequences-tsv",
                    str(acquisition_dir / "missing_sequences.tsv"),
                    "--cds-fasta",
                    str(cds_fasta),
                    "--batch-id",
                    "batch_0001",
                    "--method",
                    "pure",
                    "--repeat-residue",
                    "A",
                    "--status-out",
                    str(status_path),
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
            stage_status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(stage_status["stage"], "finalize")
            self.assertEqual(stage_status["status"], "failed")
            self.assertEqual(stage_status["batch_id"], "batch_0001")
            self.assertEqual(stage_status["method"], "pure")
            self.assertEqual(stage_status["repeat_residue"], "A")
            self.assertTrue(stage_status["message"])
