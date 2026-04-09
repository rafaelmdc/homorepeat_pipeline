from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_support import CLI_ENV, REPO_ROOT


class WorkflowOutputFailureRegressionTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_failed_run_preserves_workflow_outputs_without_publishop_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            accessions_file = tmp / "accessions.txt"
            taxonomy_db = tmp / "taxonomy.sqlite"
            run_root = tmp / "run"
            publish_root = run_root / "publish"
            log_file = run_root / "internal" / "nextflow" / "nextflow.log"

            accessions_file.write_text("GCF_000001405.40\n", encoding="utf-8")
            taxonomy_db.write_text("", encoding="utf-8")

            env = {
                **CLI_ENV,
                "NXF_HOME": os.environ.get("NXF_HOME", str(REPO_ROOT / "runtime" / "cache" / "nextflow")),
            }
            result = subprocess.run(
                [
                    "nextflow",
                    "-log",
                    str(log_file),
                    "run",
                    ".",
                    "-profile",
                    "local",
                    "--run_id",
                    "workflow_output_failure_regression",
                    "--run_root",
                    str(run_root),
                    "--accessions_file",
                    str(accessions_file),
                    "--taxonomy_db",
                    str(taxonomy_db),
                    "--python_bin",
                    "missing_python_for_failure_probe",
                    "--batch_size",
                    "1",
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

            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Cannot access first() element from an empty List", result.stdout)
            self.assertNotIn("Cannot access first() element from an empty List", result.stderr)

            self.assertTrue((run_root / "internal" / "nextflow" / "report.html").is_file())
            self.assertTrue((publish_root / "metadata" / "run_manifest.json").is_file())
            self.assertTrue((publish_root / "metadata" / "launch_metadata.json").is_file())
            self.assertFalse((publish_root / ".nf_placeholders").exists())

            nextflow_log = log_file.read_text(encoding="utf-8")
            self.assertNotIn("Cannot access first() element from an empty List", nextflow_log)

            manifest = json.loads((publish_root / "metadata" / "run_manifest.json").read_text(encoding="utf-8"))
            launch = json.loads((publish_root / "metadata" / "launch_metadata.json").read_text(encoding="utf-8"))

            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(launch["status"], "failed")
            self.assertEqual(manifest["acquisition_publish_mode"], "raw")
            self.assertEqual(launch["acquisition_publish_mode"], "raw")
            self.assertEqual(manifest["params"]["effective_values"]["batch_size"], 1)
            self.assertFalse((publish_root / "calls").exists())
