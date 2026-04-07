from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, build_call_row
from homorepeat.contracts.run_params import RUN_PARAM_FIELDNAMES, build_run_param_rows
from homorepeat.io.tsv_io import read_tsv, write_tsv

from tests.test_support import CLI_ENV, REPO_ROOT


class RuntimeArtifactsTest(unittest.TestCase):
    def test_merge_call_tables_cli_publishes_canonical_repeat_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            pure_calls = tmp / "pure_calls.tsv"
            seed_extend_calls = tmp / "seed_extend_calls.tsv"
            threshold_calls = tmp / "threshold_calls.tsv"
            pure_params = tmp / "pure_run_params.tsv"
            seed_extend_params = tmp / "seed_extend_run_params.tsv"
            threshold_params = tmp / "threshold_run_params.tsv"
            outdir = tmp / "publish" / "calls"

            write_tsv(
                pure_calls,
                [
                    build_call_row(
                        method="pure",
                        genome_id="genome_001",
                        taxon_id="9606",
                        sequence_id="seq_001",
                        protein_id="prot_001",
                        repeat_residue="Q",
                        start=3,
                        end=8,
                        aa_sequence="QQQQQQ",
                    )
                ],
                fieldnames=CALL_FIELDNAMES,
            )
            write_tsv(
                seed_extend_calls,
                [
                    build_call_row(
                        method="seed_extend",
                        genome_id="genome_001",
                        taxon_id="9606",
                        sequence_id="seq_001",
                        protein_id="prot_001",
                        repeat_residue="Q",
                        start=20,
                        end=32,
                        aa_sequence="QQQQQQAQQQQQQ",
                        window_definition="seed:Q6/8|extend:Q8/12",
                    )
                ],
                fieldnames=CALL_FIELDNAMES,
            )
            write_tsv(
                threshold_calls,
                [
                    build_call_row(
                        method="threshold",
                        genome_id="genome_001",
                        taxon_id="9606",
                        sequence_id="seq_001",
                        protein_id="prot_001",
                        repeat_residue="Q",
                        start=10,
                        end=17,
                        aa_sequence="QQQAQAQQ",
                        window_definition="Q6/8",
                    )
                ],
                fieldnames=CALL_FIELDNAMES,
            )
            write_tsv(
                pure_params,
                build_run_param_rows("pure", {"repeat_residue": "Q", "min_repeat_count": 6}),
                fieldnames=RUN_PARAM_FIELDNAMES,
            )
            write_tsv(
                seed_extend_params,
                build_run_param_rows(
                    "seed_extend",
                    {
                        "repeat_residue": "Q",
                        "seed_window_size": 8,
                        "seed_min_target_count": 6,
                        "extend_window_size": 12,
                        "extend_min_target_count": 8,
                        "min_total_length": 10,
                    },
                ),
                fieldnames=RUN_PARAM_FIELDNAMES,
            )
            write_tsv(
                threshold_params,
                build_run_param_rows("threshold", {"repeat_residue": "Q", "window_size": 8, "min_target_count": 6}),
                fieldnames=RUN_PARAM_FIELDNAMES,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homorepeat.cli.merge_call_tables",
                    "--call-tsv",
                    str(pure_calls),
                    "--call-tsv",
                    str(seed_extend_calls),
                    "--call-tsv",
                    str(threshold_calls),
                    "--run-params-tsv",
                    str(pure_params),
                    "--run-params-tsv",
                    str(seed_extend_params),
                    "--run-params-tsv",
                    str(threshold_params),
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
                    f"merge_call_tables failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            merged_calls = read_tsv(outdir / "repeat_calls.tsv")
            merged_params = read_tsv(outdir / "run_params.tsv")

            self.assertEqual([row["method"] for row in merged_calls], ["pure", "seed_extend", "threshold"])
            self.assertEqual(
                [(row["method"], row["param_name"]) for row in merged_params],
                [
                    ("pure", "min_repeat_count"),
                    ("pure", "repeat_residue"),
                    ("seed_extend", "extend_min_target_count"),
                    ("seed_extend", "extend_window_size"),
                    ("seed_extend", "min_total_length"),
                    ("seed_extend", "repeat_residue"),
                    ("seed_extend", "seed_min_target_count"),
                    ("seed_extend", "seed_window_size"),
                    ("threshold", "min_target_count"),
                    ("threshold", "repeat_residue"),
                    ("threshold", "window_size"),
                ],
            )

    def test_write_run_manifest_cli_records_published_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_root = tmp / "runs" / "run_001"
            publish_root = run_root / "publish"
            (publish_root / "acquisition").mkdir(parents=True, exist_ok=True)
            (publish_root / "calls").mkdir(parents=True, exist_ok=True)
            (publish_root / "database" / "sqlite").mkdir(parents=True, exist_ok=True)
            (publish_root / "reports").mkdir(parents=True, exist_ok=True)
            (run_root / "internal" / "nextflow").mkdir(parents=True, exist_ok=True)

            for path in [
                publish_root / "acquisition" / "genomes.tsv",
                publish_root / "calls" / "repeat_calls.tsv",
                publish_root / "calls" / "run_params.tsv",
                publish_root / "database" / "sqlite" / "homorepeat.sqlite",
                publish_root / "reports" / "summary_by_taxon.tsv",
                run_root / "internal" / "nextflow" / "trace.txt",
            ]:
                if path.name == "run_params.tsv":
                    path.write_text(
                        "method\tparam_name\tparam_value\n"
                        "pure\trepeat_residue\tQ\n"
                        "pure\tmin_repeat_count\t6\n",
                        encoding="utf-8",
                    )
                else:
                    path.write_text("stub\n", encoding="utf-8")

            accessions_file = tmp / "accessions.txt"
            taxonomy_db = tmp / "taxonomy.sqlite"
            nextflow_command = run_root / "internal" / "nextflow" / "nextflow_command.sh"
            manifest_path = publish_root / "manifest" / "run_manifest.json"
            accessions_file.write_text("GCF_000001405.40\n", encoding="utf-8")
            taxonomy_db.write_text("", encoding="utf-8")
            nextflow_command.write_text("nextflow run .\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homorepeat.cli.write_run_manifest",
                    "--pipeline-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "run_001",
                    "--run-root",
                    str(run_root),
                    "--publish-root",
                    str(publish_root),
                    "--profile",
                    "local",
                    "--accessions-file",
                    str(accessions_file),
                    "--taxonomy-db",
                    str(taxonomy_db),
                    "--nextflow-command",
                    str(nextflow_command),
                    "--started-at-utc",
                    "2026-04-06T00:00:00Z",
                    "--finished-at-utc",
                    "2026-04-06T00:05:00Z",
                    "--status",
                    "success",
                    "--outpath",
                    str(manifest_path),
                ],
                cwd=REPO_ROOT,
                env=CLI_ENV,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                self.fail(
                    f"write_run_manifest failed with exit code {result.returncode}\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                )

            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["run_id"], "run_001")
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["enabled_methods"], ["pure"])
            self.assertEqual(payload["repeat_residues"], ["Q"])
            self.assertEqual(payload["params"]["detection"]["pure"]["min_repeat_count"], "6")
            self.assertEqual(payload["artifacts"]["acquisition"]["genomes_tsv"], "publish/acquisition/genomes.tsv")
            self.assertEqual(payload["artifacts"]["calls"]["repeat_calls_tsv"], "publish/calls/repeat_calls.tsv")
            self.assertEqual(payload["artifacts"]["calls"]["run_params_tsv"], "publish/calls/run_params.tsv")
            self.assertEqual(payload["artifacts"]["database"]["sqlite"], "publish/database/sqlite/homorepeat.sqlite")
            self.assertEqual(payload["artifacts"]["internal"]["trace_txt"], "internal/nextflow/trace.txt")


if __name__ == "__main__":
    unittest.main()
