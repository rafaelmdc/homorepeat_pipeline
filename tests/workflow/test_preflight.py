from __future__ import annotations

import os
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

    def _run_preflight_probe(
        self,
        *,
        run_root: Path,
        accessions_file: Path,
        taxonomy_db: Path,
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
            "--taxonomy_db",
            str(taxonomy_db),
        ]
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
