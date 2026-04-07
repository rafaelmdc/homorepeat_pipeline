from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHONPATH = str(REPO_ROOT / "src")
if existing_pythonpath := os.environ.get("PYTHONPATH"):
    PYTHONPATH = os.pathsep.join([PYTHONPATH, existing_pythonpath])
CLI_ENV = {**os.environ, "PYTHONPATH": PYTHONPATH}


def cli_command(name: str) -> list[str]:
    return [sys.executable, "-m", f"homorepeat.cli.{name}"]
