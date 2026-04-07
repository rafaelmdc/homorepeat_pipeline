from __future__ import annotations

import shutil
import subprocess
import unittest

from tests.test_support import REPO_ROOT


class PipelineConfigTest(unittest.TestCase):
    def test_pipeline_app_layout_exists(self) -> None:
        for relative_path in [
            "main.nf",
            "nextflow.config",
            "conf/base.config",
            "modules/local",
            "workflows",
            "scripts",
        ]:
            self.assertTrue((REPO_ROOT / relative_path).exists(), relative_path)

    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_nextflow_config_parses(self) -> None:
        result = subprocess.run(
            ["nextflow", "config", "."],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                f"nextflow config failed with exit code {result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
