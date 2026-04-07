from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from homorepeat.detection.detect_pure import find_pure_tracts
from homorepeat.contracts.repeat_features import validate_call_row
from homorepeat.io.tsv_io import read_tsv, write_tsv


from tests.test_support import CLI_ENV, REPO_ROOT, cli_command


class SliceThreePureDetectionTest(unittest.TestCase):
    def test_find_pure_tracts_reproduces_phase2_worked_example(self) -> None:
        tracts = find_pure_tracts("MCAAAAAAGP", "A", min_repeat_count=6)
        self.assertEqual(len(tracts), 1)
        tract = tracts[0]
        self.assertEqual((tract.start, tract.end, tract.aa_sequence), (3, 8, "AAAAAA"))

    def test_find_pure_tracts_rejects_threshold_only_example(self) -> None:
        tracts = find_pure_tracts("MQAATVAAAAAK", "A", min_repeat_count=6)
        self.assertEqual(tracts, [])

    def test_find_pure_tracts_handles_multiple_contiguous_tracts(self) -> None:
        tracts = find_pure_tracts("AAAAAAXYAAAAAA", "A", min_repeat_count=6)
        self.assertEqual(
            [(tract.start, tract.end, tract.aa_sequence) for tract in tracts],
            [
                (1, 6, "AAAAAA"),
                (9, 14, "AAAAAA"),
            ],
        )

    def test_find_pure_tracts_rejects_interrupted_runs(self) -> None:
        tracts = find_pure_tracts("MAAATAAAGAAAAP", "A", min_repeat_count=6)
        self.assertEqual(tracts, [])

    def test_find_pure_tracts_breaks_at_non_target_block_and_keeps_later_qualifying_tract(self) -> None:
        tracts = find_pure_tracts("MAAASTAAAAAAP", "A", min_repeat_count=6)
        self.assertEqual(len(tracts), 1)
        self.assertEqual((tracts[0].start, tracts[0].end, tracts[0].aa_sequence), (7, 12, "AAAAAA"))

    def test_detect_pure_cli_rows_satisfy_contract_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            inputs_dir = tmp / "merged" / "acquisition"
            outdir = tmp / "merged" / "detection" / "pure"
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
                        "protein_length": 19,
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
            proteins_faa.write_text(">prot_contract_1\nAAAAAAXYAAAAAA\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.detect_pure",
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
                    f"detect_pure.py failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            call_rows = read_tsv(outdir / "pure_calls.tsv")
            protein_sequence = "AAAAAAXYAAAAAA"
            self.assertEqual(len(call_rows), 2)
            for row in call_rows:
                validate_call_row(row)
                start = int(row["start"])
                end = int(row["end"])
                self.assertEqual(row["aa_sequence"], protein_sequence[start - 1 : end])
                self.assertTrue(set(row["aa_sequence"]) <= {"A"})
                self.assertEqual(int(row["non_repeat_count"]), 0)
                self.assertEqual(int(row["repeat_count"]) + int(row["non_repeat_count"]), int(row["length"]))

    def test_detect_pure_cli_writes_calls_and_run_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            inputs_dir = tmp / "merged" / "acquisition"
            outdir = tmp / "merged" / "detection" / "pure"
            inputs_dir.mkdir(parents=True, exist_ok=True)

            proteins_tsv = inputs_dir / "proteins.tsv"
            proteins_faa = inputs_dir / "proteins.faa"
            write_tsv(
                proteins_tsv,
                [
                    {
                        "protein_id": "prot_example_1",
                        "sequence_id": "seq_example_1",
                        "genome_id": "genome_001",
                        "protein_name": "example_one",
                        "protein_length": 11,
                        "protein_path": str(proteins_faa.resolve()),
                        "gene_symbol": "GENE1",
                        "translation_method": "local_cds_translation",
                        "translation_status": "translated",
                        "assembly_accession": "GCF_TEST_1.1",
                        "taxon_id": "9606",
                        "gene_group": "GENE1",
                        "protein_external_id": "NP_TEST_1.1",
                    },
                    {
                        "protein_id": "prot_example_2",
                        "sequence_id": "seq_example_2",
                        "genome_id": "genome_001",
                        "protein_name": "example_two",
                        "protein_length": 12,
                        "protein_path": str(proteins_faa.resolve()),
                        "gene_symbol": "GENE2",
                        "translation_method": "local_cds_translation",
                        "translation_status": "translated",
                        "assembly_accession": "GCF_TEST_1.1",
                        "taxon_id": "9606",
                        "gene_group": "GENE2",
                        "protein_external_id": "NP_TEST_2.1",
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
                ">prot_example_1\nMCAAAAAAGP\n"
                ">prot_example_2\nMQAATVAAAAAK\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m", "homorepeat.cli.detect_pure",
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
                    f"detect_pure.py failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            call_rows = read_tsv(outdir / "pure_calls.tsv")
            param_rows = read_tsv(outdir / "run_params.tsv")

            self.assertEqual(len(call_rows), 1)
            row = call_rows[0]
            self.assertEqual(row["method"], "pure")
            self.assertEqual(row["protein_id"], "prot_example_1")
            self.assertEqual(row["start"], "3")
            self.assertEqual(row["end"], "8")
            self.assertEqual(row["aa_sequence"], "AAAAAA")
            self.assertEqual(row["repeat_residue"], "A")
            self.assertEqual(row["repeat_count"], "6")
            self.assertEqual(row["non_repeat_count"], "0")
            self.assertEqual(row["length"], "6")
            self.assertEqual(row["purity"], "1.0000000000")
            self.assertEqual(row["merge_rule"], "contiguous_run")

            self.assertEqual(
                {(item["param_name"], item["param_value"]) for item in param_rows},
                {
                    ("repeat_residue", "A"),
                    ("min_repeat_count", "6"),
                },
            )
