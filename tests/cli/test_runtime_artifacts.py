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
                build_run_param_rows("pure", "Q", {"min_repeat_count": 6}),
                fieldnames=RUN_PARAM_FIELDNAMES,
            )
            write_tsv(
                seed_extend_params,
                build_run_param_rows(
                    "seed_extend",
                    "Q",
                    {
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
                build_run_param_rows("threshold", "Q", {"window_size": 8, "min_target_count": 6}),
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
            self.assertNotIn("source_file", merged_calls[0])
            self.assertEqual(
                [(row["method"], row["repeat_residue"], row["param_name"]) for row in merged_params],
                [
                    ("pure", "Q", "min_repeat_count"),
                    ("seed_extend", "Q", "extend_min_target_count"),
                    ("seed_extend", "Q", "extend_window_size"),
                    ("seed_extend", "Q", "min_total_length"),
                    ("seed_extend", "Q", "seed_min_target_count"),
                    ("seed_extend", "Q", "seed_window_size"),
                    ("threshold", "Q", "min_target_count"),
                    ("threshold", "Q", "window_size"),
                ],
            )

    def test_merge_call_tables_cli_accepts_multiple_repeat_residues_per_method(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            q_calls = tmp / "pure_q_calls.tsv"
            n_calls = tmp / "pure_n_calls.tsv"
            q_params = tmp / "pure_q_run_params.tsv"
            n_params = tmp / "pure_n_run_params.tsv"
            outdir = tmp / "publish" / "calls"

            write_tsv(
                q_calls,
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
                n_calls,
                [
                    build_call_row(
                        method="pure",
                        genome_id="genome_001",
                        taxon_id="9606",
                        sequence_id="seq_001",
                        protein_id="prot_001",
                        repeat_residue="N",
                        start=10,
                        end=15,
                        aa_sequence="NNNNNN",
                    )
                ],
                fieldnames=CALL_FIELDNAMES,
            )
            write_tsv(q_params, build_run_param_rows("pure", "Q", {"min_repeat_count": 6}), fieldnames=RUN_PARAM_FIELDNAMES)
            write_tsv(n_params, build_run_param_rows("pure", "N", {"min_repeat_count": 6}), fieldnames=RUN_PARAM_FIELDNAMES)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homorepeat.cli.merge_call_tables",
                    "--call-tsv", str(q_calls),
                    "--call-tsv", str(n_calls),
                    "--run-params-tsv", str(q_params),
                    "--run-params-tsv", str(n_params),
                    "--outdir", str(outdir),
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

            merged_params = read_tsv(outdir / "run_params.tsv")
            self.assertEqual(
                [(row["method"], row["repeat_residue"], row["param_name"], row["param_value"]) for row in merged_params],
                [
                    ("pure", "N", "min_repeat_count", "6"),
                    ("pure", "Q", "min_repeat_count", "6"),
                ],
            )

    def test_write_run_manifest_cli_records_published_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_root = tmp / "runs" / "run_001"
            publish_root = run_root / "publish"
            (publish_root / "acquisition").mkdir(parents=True, exist_ok=True)
            (publish_root / "calls").mkdir(parents=True, exist_ok=True)
            (publish_root / "calls" / "finalized" / "pure" / "Q" / "batch_0001").mkdir(parents=True, exist_ok=True)
            (publish_root / "database").mkdir(parents=True, exist_ok=True)
            (publish_root / "metadata" / "nextflow").mkdir(parents=True, exist_ok=True)
            (publish_root / "reports").mkdir(parents=True, exist_ok=True)
            (publish_root / "status").mkdir(parents=True, exist_ok=True)

            for path in [
                publish_root / "acquisition" / "genomes.tsv",
                publish_root / "calls" / "repeat_calls.tsv",
                publish_root / "calls" / "run_params.tsv",
                publish_root / "database" / "homorepeat.sqlite",
                publish_root / "reports" / "summary_by_taxon.tsv",
                publish_root / "status" / "accession_status.tsv",
                publish_root / "status" / "accession_call_counts.tsv",
                publish_root / "metadata" / "nextflow" / "trace.txt",
            ]:
                if path.name == "run_params.tsv":
                    path.write_text(
                        "method\trepeat_residue\tparam_name\tparam_value\n"
                        "pure\tQ\tmin_repeat_count\t6\n",
                        encoding="utf-8",
                    )
                elif path.name == "status_summary.json":
                    path.write_text('{"status":"partial"}\n', encoding="utf-8")
                else:
                    path.write_text("stub\n", encoding="utf-8")
            (publish_root / "status" / "status_summary.json").write_text('{"status":"partial"}\n', encoding="utf-8")

            accessions_file = tmp / "accessions.txt"
            taxonomy_db = tmp / "taxonomy.sqlite"
            launch_metadata = publish_root / "metadata" / "launch_metadata.json"
            manifest_path = publish_root / "metadata" / "run_manifest.json"
            accessions_file.write_text("GCF_000001405.40\n", encoding="utf-8")
            taxonomy_db.write_text("", encoding="utf-8")
            launch_metadata.write_text('{"run_id":"run_001"}\n', encoding="utf-8")

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
                    "--launch-metadata",
                    str(launch_metadata),
                    "--started-at-utc",
                    "2026-04-06T00:00:00Z",
                    "--finished-at-utc",
                    "2026-04-06T00:05:00Z",
                    "--status",
                    "success",
                    "--acquisition-publish-mode",
                    "merged",
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
            self.assertEqual(payload["publish_contract_version"], 1)
            self.assertEqual(payload["acquisition_publish_mode"], "merged")
            self.assertEqual(payload["enabled_methods"], ["pure"])
            self.assertEqual(payload["repeat_residues"], ["Q"])
            self.assertEqual(payload["params"]["detection"]["pure"]["Q"]["min_repeat_count"], "6")
            self.assertEqual(payload["artifacts"]["acquisition"]["genomes_tsv"], "publish/acquisition/genomes.tsv")
            self.assertEqual(payload["artifacts"]["calls"]["repeat_calls_tsv"], "publish/calls/repeat_calls.tsv")
            self.assertEqual(payload["artifacts"]["calls"]["run_params_tsv"], "publish/calls/run_params.tsv")
            self.assertEqual(payload["artifacts"]["calls"]["finalized_root"], "publish/calls/finalized")
            self.assertEqual(payload["artifacts"]["database"]["sqlite"], "publish/database/homorepeat.sqlite")
            self.assertEqual(payload["artifacts"]["status"]["accession_status_tsv"], "publish/status/accession_status.tsv")
            self.assertEqual(payload["artifacts"]["status"]["accession_call_counts_tsv"], "publish/status/accession_call_counts.tsv")
            self.assertEqual(payload["artifacts"]["status"]["status_summary_json"], "publish/status/status_summary.json")
            self.assertEqual(payload["artifacts"]["metadata"]["launch_metadata_json"], "publish/metadata/launch_metadata.json")
            self.assertEqual(payload["artifacts"]["metadata"]["trace_txt"], "publish/metadata/nextflow/trace.txt")

    def test_write_run_manifest_cli_records_multi_residue_detection_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_root = tmp / "runs" / "run_002"
            publish_root = run_root / "publish"
            (publish_root / "calls").mkdir(parents=True, exist_ok=True)
            (publish_root / "metadata" / "nextflow").mkdir(parents=True, exist_ok=True)

            (publish_root / "calls" / "run_params.tsv").write_text(
                "method\trepeat_residue\tparam_name\tparam_value\n"
                "pure\tQ\tmin_repeat_count\t6\n"
                "pure\tN\tmin_repeat_count\t6\n",
                encoding="utf-8",
            )
            accessions_file = tmp / "accessions.txt"
            taxonomy_db = tmp / "taxonomy.sqlite"
            launch_metadata = publish_root / "metadata" / "launch_metadata.json"
            manifest_path = publish_root / "metadata" / "run_manifest.json"
            accessions_file.write_text("GCF_000001405.40\n", encoding="utf-8")
            taxonomy_db.write_text("", encoding="utf-8")
            launch_metadata.write_text('{"run_id":"run_002"}\n', encoding="utf-8")
            (publish_root / "metadata" / "nextflow" / "trace.txt").write_text("stub\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homorepeat.cli.write_run_manifest",
                    "--pipeline-root", str(REPO_ROOT),
                    "--run-id", "run_002",
                    "--run-root", str(run_root),
                    "--publish-root", str(publish_root),
                    "--profile", "local",
                    "--accessions-file", str(accessions_file),
                    "--taxonomy-db", str(taxonomy_db),
                    "--launch-metadata", str(launch_metadata),
                    "--started-at-utc", "2026-04-06T00:00:00Z",
                    "--finished-at-utc", "2026-04-06T00:05:00Z",
                    "--status", "success",
                    "--acquisition-publish-mode", "raw",
                    "--outpath", str(manifest_path),
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
            self.assertEqual(payload["publish_contract_version"], 1)
            self.assertEqual(payload["acquisition_publish_mode"], "raw")
            self.assertEqual(payload["enabled_methods"], ["pure"])
            self.assertEqual(payload["repeat_residues"], ["N", "Q"])
            self.assertEqual(payload["params"]["detection"]["pure"]["N"]["min_repeat_count"], "6")
            self.assertEqual(payload["params"]["detection"]["pure"]["Q"]["min_repeat_count"], "6")
            self.assertEqual(payload["artifacts"]["metadata"]["trace_txt"], "publish/metadata/nextflow/trace.txt")

    def test_write_run_manifest_cli_records_raw_batch_acquisition_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_root = tmp / "runs" / "run_raw"
            publish_root = run_root / "publish"
            (publish_root / "acquisition" / "batches" / "batch_0001").mkdir(parents=True, exist_ok=True)
            (publish_root / "calls").mkdir(parents=True, exist_ok=True)
            (publish_root / "metadata" / "nextflow").mkdir(parents=True, exist_ok=True)
            (publish_root / "status").mkdir(parents=True, exist_ok=True)

            (publish_root / "acquisition" / "batches" / "batch_0001" / "taxonomy.tsv").write_text("stub\n", encoding="utf-8")
            (publish_root / "calls" / "repeat_calls.tsv").write_text("stub\n", encoding="utf-8")
            (publish_root / "calls" / "run_params.tsv").write_text(
                "method\trepeat_residue\tparam_name\tparam_value\n"
                "pure\tQ\tmin_repeat_count\t6\n",
                encoding="utf-8",
            )
            (publish_root / "metadata" / "nextflow" / "trace.txt").write_text("stub\n", encoding="utf-8")
            (publish_root / "status" / "accession_status.tsv").write_text("stub\n", encoding="utf-8")

            accessions_file = tmp / "accessions.txt"
            taxonomy_db = tmp / "taxonomy.sqlite"
            launch_metadata = publish_root / "metadata" / "launch_metadata.json"
            manifest_path = publish_root / "metadata" / "run_manifest.json"
            accessions_file.write_text("GCF_000001405.40\n", encoding="utf-8")
            taxonomy_db.write_text("", encoding="utf-8")
            launch_metadata.write_text('{"run_id":"run_raw"}\n', encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homorepeat.cli.write_run_manifest",
                    "--pipeline-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "run_raw",
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
                    "--launch-metadata",
                    str(launch_metadata),
                    "--started-at-utc",
                    "2026-04-06T00:00:00Z",
                    "--finished-at-utc",
                    "2026-04-06T00:05:00Z",
                    "--status",
                    "success",
                    "--acquisition-publish-mode",
                    "raw",
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
            self.assertEqual(payload["publish_contract_version"], 1)
            self.assertEqual(payload["acquisition_publish_mode"], "raw")
            self.assertEqual(payload["artifacts"]["acquisition"]["batches_root"], "publish/acquisition/batches")
            self.assertNotIn("genomes_tsv", payload["artifacts"]["acquisition"])
            self.assertEqual(payload["artifacts"]["calls"]["repeat_calls_tsv"], "publish/calls/repeat_calls.tsv")
            self.assertEqual(payload["artifacts"]["calls"]["run_params_tsv"], "publish/calls/run_params.tsv")
            self.assertEqual(payload["artifacts"]["database"], {})
            self.assertEqual(payload["artifacts"]["reports"], {})

    def test_write_run_manifest_cli_records_effective_params_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_root = tmp / "runs" / "run_effective"
            publish_root = run_root / "publish"
            (publish_root / "calls").mkdir(parents=True, exist_ok=True)
            (publish_root / "metadata" / "nextflow").mkdir(parents=True, exist_ok=True)

            (publish_root / "calls" / "run_params.tsv").write_text(
                "method\trepeat_residue\tparam_name\tparam_value\n"
                "pure\tQ\tmin_repeat_count\t6\n",
                encoding="utf-8",
            )
            (publish_root / "metadata" / "nextflow" / "trace.txt").write_text("stub\n", encoding="utf-8")

            accessions_file = tmp / "accessions.txt"
            taxonomy_db = tmp / "taxonomy.sqlite"
            params_file = tmp / "params.json"
            launch_metadata = publish_root / "metadata" / "launch_metadata.json"
            manifest_path = publish_root / "metadata" / "run_manifest.json"
            accessions_file.write_text("GCF_000001405.40\n", encoding="utf-8")
            taxonomy_db.write_text("", encoding="utf-8")
            params_file.write_text(
                json.dumps({"repeat_residues": "Q", "run_pure": True, "run_threshold": True, "batch_size": 10}),
                encoding="utf-8",
            )
            launch_metadata.write_text('{"run_id":"run_effective"}\n', encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "homorepeat.cli.write_run_manifest",
                    "--pipeline-root",
                    str(REPO_ROOT),
                    "--run-id",
                    "run_effective",
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
                    "--launch-metadata",
                    str(launch_metadata),
                    "--started-at-utc",
                    "2026-04-06T00:00:00Z",
                    "--finished-at-utc",
                    "2026-04-06T00:05:00Z",
                    "--status",
                    "success",
                    "--acquisition-publish-mode",
                    "raw",
                    "--params-file",
                    str(params_file),
                    "--effective-params-json",
                    json.dumps({"batch_size": 2, "run_pure": True, "run_threshold": True, "repeat_residues": "Q"}),
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
            self.assertEqual(payload["publish_contract_version"], 1)
            self.assertEqual(payload["params"]["params_file_values"]["batch_size"], 10)
            self.assertEqual(payload["params"]["effective_values"]["batch_size"], 2)


if __name__ == "__main__":
    unittest.main()
