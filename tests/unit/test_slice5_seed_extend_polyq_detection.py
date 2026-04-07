from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from homorepeat.detection.detect_seed_extend_polyq import find_seed_extend_polyq_tracts
from homorepeat.contracts.repeat_features import validate_call_row
from homorepeat.io.tsv_io import read_tsv, write_tsv

from tests.test_support import CLI_ENV, REPO_ROOT


class SliceFiveSeedExtendPolyQDetectionTest(unittest.TestCase):
    def test_find_seed_extend_polyq_tracts_reports_long_interrupted_polyq(self) -> None:
        tracts = find_seed_extend_polyq_tracts("MQQQQQQAQQQQQQM")
        self.assertEqual(len(tracts), 1)
        tract = tracts[0]
        self.assertEqual((tract.start, tract.end, tract.aa_sequence), (2, 14, "QQQQQQAQQQQQQ"))

    def test_find_seed_extend_polyq_tracts_merges_overlapping_seed_windows(self) -> None:
        tracts = find_seed_extend_polyq_tracts("MQQQQQQQQQQQQP")
        self.assertEqual(len(tracts), 1)
        self.assertEqual((tracts[0].start, tracts[0].end, tracts[0].aa_sequence), (2, 13, "QQQQQQQQQQQQ"))

    def test_find_seed_extend_polyq_tracts_can_reach_sequence_edges(self) -> None:
        tracts = find_seed_extend_polyq_tracts("QQQQQQAQQQQQQ")
        self.assertEqual(len(tracts), 1)
        self.assertEqual((tracts[0].start, tracts[0].end, tracts[0].aa_sequence), (1, 13, "QQQQQQAQQQQQQ"))

    def test_find_seed_extend_polyq_tracts_rejects_weak_q_rich_noise_without_seed(self) -> None:
        tracts = find_seed_extend_polyq_tracts("MQQAQAQAQQAQQP")
        self.assertEqual(tracts, [])

    def test_find_seed_extend_polyq_tracts_trims_non_q_flanks_from_qualifying_windows(self) -> None:
        tracts = find_seed_extend_polyq_tracts("MQQQQQQAQQQQQQM")
        self.assertEqual(tracts[0].aa_sequence[0], "Q")
        self.assertEqual(tracts[0].aa_sequence[-1], "Q")

    def test_find_seed_extend_polyq_tracts_rejects_seed_only_candidates_below_min_total_length(self) -> None:
        tracts = find_seed_extend_polyq_tracts("QQQQQQQQ")
        self.assertEqual(tracts, [])

    def test_find_seed_extend_polyq_tracts_validates_parameters(self) -> None:
        with self.assertRaisesRegex(ValueError, "seed_min_q_count"):
            find_seed_extend_polyq_tracts("QQQQQQQQQQ", seed_window_size=8, seed_min_q_count=9)

    def test_detect_seed_extend_polyq_cli_writes_calls_and_run_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            inputs_dir = tmp / "merged" / "acquisition"
            outdir = tmp / "merged" / "detection" / "seed_extend_polyq"
            inputs_dir.mkdir(parents=True, exist_ok=True)

            proteins_tsv = inputs_dir / "proteins.tsv"
            proteins_faa = inputs_dir / "proteins.faa"
            write_tsv(
                proteins_tsv,
                [
                    {
                        "protein_id": "prot_seed_extend_1",
                        "sequence_id": "seq_seed_extend_1",
                        "genome_id": "genome_001",
                        "protein_name": "seed_extend_example",
                        "protein_length": 15,
                        "protein_path": str(proteins_faa.resolve()),
                        "gene_symbol": "GENE1",
                        "translation_method": "local_cds_translation",
                        "translation_status": "translated",
                        "assembly_accession": "GCF_TEST_1.1",
                        "taxon_id": "9606",
                        "gene_group": "GENE1",
                        "protein_external_id": "NP_TEST_SEED_EXTEND.1",
                    },
                    {
                        "protein_id": "prot_seed_extend_2",
                        "sequence_id": "seq_seed_extend_2",
                        "genome_id": "genome_001",
                        "protein_name": "seed_extend_negative",
                        "protein_length": 14,
                        "protein_path": str(proteins_faa.resolve()),
                        "gene_symbol": "GENE2",
                        "translation_method": "local_cds_translation",
                        "translation_status": "translated",
                        "assembly_accession": "GCF_TEST_1.1",
                        "taxon_id": "9606",
                        "gene_group": "GENE2",
                        "protein_external_id": "NP_TEST_SEED_EXTEND_NEG.1",
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
                ">prot_seed_extend_1\nMQQQQQQAQQQQQQM\n"
                ">prot_seed_extend_2\nMQQAQAQAQQAQQP\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.detect_seed_extend_polyq",
                    "--proteins-tsv",
                    str(proteins_tsv),
                    "--proteins-fasta",
                    str(proteins_faa),
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
                    f"detect_seed_extend_polyq.py failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            call_rows = read_tsv(outdir / "seed_extend_polyq_calls.tsv")
            param_rows = read_tsv(outdir / "run_params.tsv")

            self.assertEqual(len(call_rows), 1)
            row = call_rows[0]
            validate_call_row(row)
            self.assertEqual(row["method"], "seed_extend_polyq")
            self.assertEqual(row["protein_id"], "prot_seed_extend_1")
            self.assertEqual(row["start"], "2")
            self.assertEqual(row["end"], "14")
            self.assertEqual(row["aa_sequence"], "QQQQQQAQQQQQQ")
            self.assertEqual(row["repeat_residue"], "Q")
            self.assertEqual(row["repeat_count"], "12")
            self.assertEqual(row["non_repeat_count"], "1")
            self.assertEqual(row["length"], "13")
            self.assertEqual(row["window_definition"], "seed:Q6/8|extend:Q8/12")
            self.assertEqual(row["merge_rule"], "seed_extend_connected_windows")

            self.assertEqual(
                {(item["param_name"], item["param_value"]) for item in param_rows},
                {
                    ("repeat_residue", "Q"),
                    ("seed_window_size", "8"),
                    ("seed_min_q_count", "6"),
                    ("extend_window_size", "12"),
                    ("extend_min_q_count", "8"),
                    ("min_total_length", "10"),
                },
            )

    def test_detect_seed_extend_polyq_cli_rejects_non_q_repeat_residue(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            inputs_dir = tmp / "merged" / "acquisition"
            outdir = tmp / "merged" / "detection" / "seed_extend_polyq"
            inputs_dir.mkdir(parents=True, exist_ok=True)

            proteins_tsv = inputs_dir / "proteins.tsv"
            proteins_faa = inputs_dir / "proteins.faa"
            write_tsv(
                proteins_tsv,
                [
                    {
                        "protein_id": "prot_seed_extend_1",
                        "sequence_id": "seq_seed_extend_1",
                        "genome_id": "genome_001",
                        "protein_name": "seed_extend_example",
                        "protein_length": 15,
                        "protein_path": str(proteins_faa.resolve()),
                        "taxon_id": "9606",
                    }
                ],
                fieldnames=PROTEIN_TEST_FIELDNAMES,
            )
            proteins_faa.write_text(">prot_seed_extend_1\nMQQQQQQAQQQQQQM\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.detect_seed_extend_polyq",
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

            self.assertEqual(result.returncode, 3)
            self.assertIn("--repeat-residue must be 'Q'", result.stderr)


PROTEIN_TEST_FIELDNAMES = [
    "protein_id",
    "sequence_id",
    "genome_id",
    "protein_name",
    "protein_length",
    "protein_path",
    "taxon_id",
]


if __name__ == "__main__":
    unittest.main()
