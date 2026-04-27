from __future__ import annotations

import os
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_support import CLI_ENV, REPO_ROOT


class WorkflowPreflightTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_comment_only_accessions_file_fails_with_actionable_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            accessions_file = tmp / "accessions.txt"
            taxonomy_db = tmp / "taxonomy.sqlite"
            run_root = tmp / "run_empty_accessions"

            accessions_file.write_text("# no accessions yet\n\n", encoding="utf-8")
            taxonomy_db.write_text("", encoding="utf-8")

            result = self._run_preflight_probe(
                run_root=run_root,
                accessions_file=accessions_file,
                taxonomy_db=taxonomy_db,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("accessions file has no usable accession lines", combined_output)
            self.assertIn("GCF_000001405.40", combined_output)

    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_invalid_repeat_residue_fails_with_actionable_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            accessions_file = tmp / "accessions.txt"
            taxonomy_db = tmp / "taxonomy.sqlite"
            run_root = tmp / "run_invalid_residue"

            accessions_file.write_text("GCF_000001405.40\n", encoding="utf-8")
            taxonomy_db.write_text("", encoding="utf-8")

            result = self._run_preflight_probe(
                run_root=run_root,
                accessions_file=accessions_file,
                taxonomy_db=taxonomy_db,
                extra_args=["--repeat_residues", "Q,QQ,1"],
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("params.repeat_residues contains invalid residue code(s): QQ,1", combined_output)
            self.assertIn("Q,N", combined_output)

    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_dry_run_inputs_validates_without_running_pipeline_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            accessions_file = tmp / "accessions.txt"
            taxonomy_cache_dir = tmp / "taxonomy_cache"
            run_root = tmp / "run_dry_inputs"

            accessions_file.write_text("GCF_000001405.40\n", encoding="utf-8")

            result = self._run_preflight_probe(
                run_root=run_root,
                accessions_file=accessions_file,
                taxonomy_db=None,
                extra_args=[
                    "--taxonomy_cache_dir",
                    str(taxonomy_cache_dir),
                    "--dry_run_inputs",
                    "true",
                ],
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            combined_output = result.stdout + result.stderr
            self.assertIn("HomoRepeat input dry run passed.", combined_output)
            self.assertIn("Usable accessions: 1", combined_output)
            self.assertIn("Taxonomy DB:", combined_output)
            self.assertIn("will_auto_build", combined_output)
            self.assertFalse((run_root / "publish" / "calls" / "repeat_calls.tsv").exists())

            manifest = json.loads((run_root / "publish" / "metadata" / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "dry_run_success")
            self.assertTrue(manifest["dry_run_inputs"])

    def _run_preflight_probe(
        self,
        *,
        run_root: Path,
        accessions_file: Path,
        taxonomy_db: Path | None,
        extra_args: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        log_file = run_root / "internal" / "nextflow" / "nextflow.log"
        env = {
            **CLI_ENV,
            "NXF_HOME": os.environ.get("NXF_HOME", str(REPO_ROOT / "runtime" / "cache" / "nextflow")),
        }
        cmd = [
            "nextflow",
            "-log",
            str(log_file),
            "run",
            ".",
            "-profile",
            "local",
            "--run_id",
            run_root.name,
            "--run_root",
            str(run_root),
            "--accessions_file",
            str(accessions_file),
        ]
        if taxonomy_db is not None:
            cmd.extend(["--taxonomy_db", str(taxonomy_db)])
        if extra_args:
            cmd.extend(extra_args)
        return subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
