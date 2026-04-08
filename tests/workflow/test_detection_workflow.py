from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from collections import Counter
from pathlib import Path

from homorepeat.io.fasta_io import write_fasta
from homorepeat.io.tsv_io import write_tsv

from tests.test_support import CLI_ENV, REPO_ROOT


class DetectionWorkflowTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_detection_workflow_keeps_multi_residue_outputs_per_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            batch_dir = tmp / "batch_0001"
            publish_dir = tmp / "publish"
            work_dir = tmp / "work"
            workflow_path = tmp / "test_detection_workflow.nf"

            batch_dir.mkdir(parents=True, exist_ok=True)
            publish_dir.mkdir(parents=True, exist_ok=True)
            work_dir.mkdir(parents=True, exist_ok=True)

            self._write_translated_batch_fixture(batch_dir)
            workflow_path.write_text(
                textwrap.dedent(
                    f"""
                    nextflow.enable.dsl = 2

                    include {{ DETECTION_FROM_ACQUISITION }} from '{(REPO_ROOT / "workflows" / "detection_from_acquisition").as_posix()}'
                    include {{ MERGE_CALL_TABLES }} from '{(REPO_ROOT / "modules" / "local" / "reporting" / "merge_call_tables").as_posix()}'

                    workflow {{
                      translated = Channel.value([ tuple('batch_0001', file(params.batch_dir)) ])
                      detection = DETECTION_FROM_ACQUISITION(translated)
                      MERGE_CALL_TABLES(detection.call_tsvs, detection.run_params_tsvs)
                    }}
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            env = {
                **CLI_ENV,
                "NXF_HOME": os.environ.get("NXF_HOME", str(REPO_ROOT / "runtime" / "cache" / "nextflow")),
            }
            result = subprocess.run(
                [
                    "nextflow",
                    "run",
                    str(workflow_path),
                    "-profile",
                    "local",
                    "-work-dir",
                    str(work_dir),
                    "--batch_dir",
                    str(batch_dir),
                    "--output_dir",
                    str(publish_dir),
                    "--python_bin",
                    sys.executable,
                    "--repeat_residues",
                    "Q,N",
                    "--run_pure",
                    "true",
                    "--run_threshold",
                    "true",
                    "--run_seed_extend",
                    "false",
                ],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.fail(
                    f"nextflow detection workflow failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            repeat_calls_path = publish_dir / "calls" / "repeat_calls.tsv"
            run_params_path = publish_dir / "calls" / "run_params.tsv"
            self.assertTrue(repeat_calls_path.is_file(), repeat_calls_path)
            self.assertTrue(run_params_path.is_file(), run_params_path)

            call_counts: Counter[tuple[str, str]] = Counter()
            with repeat_calls_path.open(encoding="utf-8") as handle:
                for row in csv.DictReader(handle, delimiter="\t"):
                    call_counts[(row["method"], row["repeat_residue"])] += 1

            self.assertEqual(
                dict(sorted(call_counts.items())),
                {
                    ("pure", "N"): 1,
                    ("pure", "Q"): 1,
                    ("threshold", "N"): 1,
                    ("threshold", "Q"): 1,
                },
            )

            run_param_pairs: set[tuple[str, str]] = set()
            with run_params_path.open(encoding="utf-8") as handle:
                for row in csv.DictReader(handle, delimiter="\t"):
                    run_param_pairs.add((row["method"], row["repeat_residue"]))

            self.assertEqual(
                run_param_pairs,
                {
                    ("pure", "N"),
                    ("pure", "Q"),
                    ("threshold", "N"),
                    ("threshold", "Q"),
                },
            )

    def _write_translated_batch_fixture(self, batch_dir: Path) -> None:
        proteins_faa = batch_dir / "proteins.faa"
        cds_fna = batch_dir / "cds.fna"

        write_tsv(
            batch_dir / "proteins.tsv",
            [
                {
                    "protein_id": "prot_q",
                    "sequence_id": "seq_q",
                    "genome_id": "genome_fixture",
                    "protein_name": "PROT_Q",
                    "protein_length": "9",
                    "protein_path": str(proteins_faa.resolve()),
                    "taxon_id": "9606",
                },
                {
                    "protein_id": "prot_n",
                    "sequence_id": "seq_n",
                    "genome_id": "genome_fixture",
                    "protein_name": "PROT_N",
                    "protein_length": "9",
                    "protein_path": str(proteins_faa.resolve()),
                    "taxon_id": "9606",
                },
            ],
            fieldnames=[
                "protein_id",
                "sequence_id",
                "genome_id",
                "protein_name",
                "protein_length",
                "protein_path",
                "taxon_id",
            ],
        )
        write_fasta(
            proteins_faa,
            [
                ("prot_q", "MQQQQQQAK"),
                ("prot_n", "MNNNNNNAK"),
            ],
        )

        write_tsv(
            batch_dir / "sequences.tsv",
            [
                {
                    "sequence_id": "seq_q",
                    "genome_id": "genome_fixture",
                    "sequence_name": "SEQ_Q",
                    "sequence_length": "27",
                    "sequence_path": str(cds_fna.resolve()),
                    "translation_table": "1",
                },
                {
                    "sequence_id": "seq_n",
                    "genome_id": "genome_fixture",
                    "sequence_name": "SEQ_N",
                    "sequence_length": "27",
                    "sequence_path": str(cds_fna.resolve()),
                    "translation_table": "1",
                },
            ],
            fieldnames=[
                "sequence_id",
                "genome_id",
                "sequence_name",
                "sequence_length",
                "sequence_path",
                "translation_table",
            ],
        )
        write_fasta(
            cds_fna,
            [
                ("seq_q", "ATG" + "CAA" * 6 + "GCT" + "AAA"),
                ("seq_n", "ATG" + "AAT" * 6 + "GCT" + "AAA"),
            ],
        )
