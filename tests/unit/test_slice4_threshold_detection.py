from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from homorepeat.detection.detect_threshold import find_threshold_tracts
from homorepeat.contracts.repeat_features import validate_call_row
from homorepeat.io.tsv_io import read_tsv, write_tsv


from tests.test_support import CLI_ENV, REPO_ROOT, cli_command


class SliceFourThresholdDetectionTest(unittest.TestCase):
    def test_find_threshold_tracts_reproduces_phase2_worked_example(self) -> None:
        tracts = find_threshold_tracts("MQAATVAAAAAK", "A")
        self.assertEqual(len(tracts), 1)
        tract = tracts[0]
        self.assertEqual((tract.start, tract.end, tract.aa_sequence), (3, 11, "AATVAAAAA"))

    def test_find_threshold_tracts_misses_similarity_only_example(self) -> None:
        tracts = find_threshold_tracts("MQAASTAAQAAVAP", "A")
        self.assertEqual(tracts, [])

    def test_find_threshold_tracts_counts_short_repeat_when_full_window_qualifies(self) -> None:
        tracts = find_threshold_tracts("MQQQQQQA", "Q")
        self.assertEqual(len(tracts), 1)
        self.assertEqual((tracts[0].start, tracts[0].end, tracts[0].aa_sequence), (2, 7, "QQQQQQ"))

    def test_find_threshold_tracts_merges_overlapping_seed_windows(self) -> None:
        tracts = find_threshold_tracts("MRAAAAAATAAAAAK", "A")
        self.assertEqual(len(tracts), 1)
        self.assertEqual((tracts[0].start, tracts[0].end, tracts[0].aa_sequence), (3, 14, "AAAAAATAAAAA"))

    def test_find_threshold_tracts_can_reach_sequence_edges_from_qualifying_windows(self) -> None:
        tracts = find_threshold_tracts("AAAAAATAAAAA", "A")
        self.assertEqual(len(tracts), 1)
        self.assertEqual((tracts[0].start, tracts[0].end, tracts[0].aa_sequence), (1, 12, "AAAAAATAAAAA"))

    def test_find_threshold_tracts_uses_merged_qualifying_windows_without_purity_extension(self) -> None:
        tracts = find_threshold_tracts("QQAATVAAAAAKQQ", "A")
        self.assertEqual(len(tracts), 1)
        self.assertEqual((tracts[0].start, tracts[0].end, tracts[0].aa_sequence), (3, 11, "AATVAAAAA"))

    def test_detect_threshold_cli_rows_satisfy_contract_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            inputs_dir = tmp / "merged" / "acquisition"
            outdir = tmp / "merged" / "detection" / "threshold"
            inputs_dir.mkdir(parents=True, exist_ok=True)

            proteins_tsv = inputs_dir / "proteins.tsv"
            proteins_faa = inputs_dir / "proteins.faa"
            write_tsv(
                proteins_tsv,
                [
                    {
                        "protein_id": "prot_contract_1",
                        "sequence_id": "seq_contract_1",
                        "genome_id": "genome_001",
                        "protein_name": "contract_one",
                        "protein_length": 15,
                        "protein_path": str(proteins_faa.resolve()),
                        "gene_symbol": "GENE1",
                        "translation_method": "local_cds_translation",
                        "translation_status": "translated",
                        "assembly_accession": "GCF_TEST_1.1",
                        "taxon_id": "9606",
                        "gene_group": "GENE1",
                        "protein_external_id": "NP_TEST_1.1",
                    }
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
            proteins_faa.write_text(">prot_contract_1\nMRAAAAAATAAAAAK\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.detect_threshold",
                    "--proteins-tsv",
                    str(proteins_tsv),
                    "--proteins-fasta",
                    str(proteins_faa),
                    "--repeat-residue",
                    "A",
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
                    f"detect_threshold.py failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            call_rows = read_tsv(outdir / "threshold_calls.tsv")
            protein_sequence = "MRAAAAAATAAAAAK"
            self.assertEqual(len(call_rows), 1)
            for row in call_rows:
                validate_call_row(row)
                start = int(row["start"])
                end = int(row["end"])
                aa_sequence = row["aa_sequence"]
                self.assertEqual(aa_sequence, protein_sequence[start - 1 : end])
                self.assertEqual(aa_sequence[0], "A")
                self.assertEqual(aa_sequence[-1], "A")
                self.assertEqual(int(row["repeat_count"]) + int(row["non_repeat_count"]), int(row["length"]))

    def test_detect_threshold_cli_writes_calls_and_run_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            inputs_dir = tmp / "merged" / "acquisition"
            outdir = tmp / "merged" / "detection" / "threshold"
            inputs_dir.mkdir(parents=True, exist_ok=True)

            proteins_tsv = inputs_dir / "proteins.tsv"
            proteins_faa = inputs_dir / "proteins.faa"
            write_tsv(
                proteins_tsv,
                [
                    {
                        "protein_id": "prot_threshold_1",
                        "sequence_id": "seq_threshold_1",
                        "genome_id": "genome_001",
                        "protein_name": "threshold_example",
                        "protein_length": 12,
                        "protein_path": str(proteins_faa.resolve()),
                        "gene_symbol": "GENE1",
                        "translation_method": "local_cds_translation",
                        "translation_status": "translated",
                        "assembly_accession": "GCF_TEST_1.1",
                        "taxon_id": "9606",
                        "gene_group": "GENE1",
                        "protein_external_id": "NP_TEST_THRESHOLD.1",
                    },
                    {
                        "protein_id": "prot_threshold_2",
                        "sequence_id": "seq_threshold_2",
                        "genome_id": "genome_001",
                        "protein_name": "similarity_only_example",
                        "protein_length": 14,
                        "protein_path": str(proteins_faa.resolve()),
                        "gene_symbol": "GENE2",
                        "translation_method": "local_cds_translation",
                        "translation_status": "translated",
                        "assembly_accession": "GCF_TEST_1.1",
                        "taxon_id": "9606",
                        "gene_group": "GENE2",
                        "protein_external_id": "NP_TEST_SIMILARITY.1",
                    },
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
            proteins_faa.write_text(
                ">prot_threshold_1\nMQAATVAAAAAK\n"
                ">prot_threshold_2\nMQAASTAAQAAVAP\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.detect_threshold",
                    "--proteins-tsv",
                    str(proteins_tsv),
                    "--proteins-fasta",
                    str(proteins_faa),
                    "--repeat-residue",
                    "A",
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
                    f"detect_threshold.py failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            call_rows = read_tsv(outdir / "threshold_calls.tsv")
            param_rows = read_tsv(outdir / "run_params.tsv")

            self.assertEqual(len(call_rows), 1)
            row = call_rows[0]
            self.assertEqual(row["method"], "threshold")
            self.assertEqual(row["protein_id"], "prot_threshold_1")
            self.assertEqual(row["start"], "3")
            self.assertEqual(row["end"], "11")
            self.assertEqual(row["aa_sequence"], "AATVAAAAA")
            self.assertEqual(row["repeat_residue"], "A")
            self.assertEqual(row["repeat_count"], "7")
            self.assertEqual(row["non_repeat_count"], "2")
            self.assertEqual(row["length"], "9")
            self.assertEqual(row["purity"], "0.7777777778")
            self.assertEqual(row["window_definition"], "A6/8")
            self.assertEqual(row["merge_rule"], "merge_adjacent_or_overlap")

            self.assertEqual(
                {(item["param_name"], item["param_value"]) for item in param_rows},
                {
                    ("repeat_residue", "A"),
                    ("window_size", "8"),
                    ("min_target_count", "6"),
                },
            )
