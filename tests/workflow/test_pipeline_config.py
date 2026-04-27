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

    def test_nextflow_version_is_pinned(self) -> None:
        config_text = (REPO_ROOT / "nextflow.config").read_text(encoding="utf-8")
        self.assertIn("nextflowVersion = '!25.10.4'", config_text)

    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_nextflow_config_parses(self) -> None:
        self._nextflow_config()

    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_docker_profile_uses_published_images(self) -> None:
        config_text = self._nextflow_config("-profile", "docker")
        self.assertIn(
            "acquisition_container = 'rafaelmdc/homorepeat-acquisition:0.1.0'",
            config_text,
        )
        self.assertIn(
            "detection_container = 'rafaelmdc/homorepeat-detection:0.1.0'",
            config_text,
        )

    @unittest.skipUnless(shutil.which("nextflow"), "nextflow is not installed")
    def test_docker_dev_profile_uses_local_images(self) -> None:
        config_text = self._nextflow_config("-profile", "docker_dev")
        self.assertIn(
            "acquisition_container = 'homorepeat-acquisition:dev'",
            config_text,
        )
        self.assertIn(
            "detection_container = 'homorepeat-detection:dev'",
            config_text,
        )

    def test_dockerhub_release_scripts_exist(self) -> None:
        for relative_path in [
            "scripts/build_dockerhub_containers.sh",
            "scripts/push_dockerhub_containers.sh",
        ]:
            script = REPO_ROOT / relative_path
            self.assertTrue(script.exists(), relative_path)
            self.assertTrue(script.stat().st_mode & 0o111, relative_path)

    def _nextflow_config(self, *args: str) -> str:
        result = subprocess.run(
            ["nextflow", "config", *args, "."],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            command = " ".join(["nextflow", "config", *args, "."])
            self.fail(
                f"{command} failed with exit code {result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return result.stdout
