"""Helpers for `run_params.tsv` artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from homorepeat.io.tsv_io import ContractError
from homorepeat.io.tsv_io import write_tsv


RUN_PARAM_FIELDNAMES = ["method", "repeat_residue", "param_name", "param_value"]


def build_run_param_rows(
    method: str,
    repeat_residue: str,
    params: Mapping[str, object],
) -> list[dict[str, object]]:
    """Shape residue-scoped method settings into canonical run-param rows."""

    normalized_residue = repeat_residue.strip().upper()
    if len(normalized_residue) != 1:
        raise ContractError(f"repeat_residue must be one amino-acid symbol: {repeat_residue!r}")
    if "repeat_residue" in params:
        raise ContractError("repeat_residue must be carried by the run_params.tsv repeat_residue column, not params")

    return [
        {
            "method": method,
            "repeat_residue": normalized_residue,
            "param_name": name,
            "param_value": value,
        }
        for name, value in sorted(params.items())
    ]


def write_run_params(
    path: Path | str,
    method: str,
    repeat_residue: str,
    params: Mapping[str, object],
) -> None:
    """Write one method+residue parameter block to `run_params.tsv`."""

    write_tsv(path, build_run_param_rows(method, repeat_residue, params), fieldnames=RUN_PARAM_FIELDNAMES)
