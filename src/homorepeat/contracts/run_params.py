"""Helpers for `run_params.tsv` artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from homorepeat.io.tsv_io import write_tsv


RUN_PARAM_FIELDNAMES = ["method", "param_name", "param_value"]


def build_run_param_rows(method: str, params: Mapping[str, object]) -> list[dict[str, object]]:
    """Shape method settings into canonical run-param rows."""

    return [
        {
            "method": method,
            "param_name": name,
            "param_value": value,
        }
        for name, value in sorted(params.items())
    ]


def write_run_params(path: Path | str, method: str, params: Mapping[str, object]) -> None:
    """Write one method's parameters to `run_params.tsv`."""

    write_tsv(path, build_run_param_rows(method, params), fieldnames=RUN_PARAM_FIELDNAMES)
