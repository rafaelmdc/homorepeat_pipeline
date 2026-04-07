"""Thin wrappers around the `taxon-weaver` CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from homorepeat.io.tsv_io import ContractError


class TaxonomyCommandError(RuntimeError):
    """Raised when `taxon-weaver` exits unsuccessfully."""


def require_taxonomy_db(path: Path | str) -> Path:
    """Validate that the configured taxonomy DB exists."""

    db_path = Path(path)
    if not db_path.is_file():
        raise ContractError(f"Taxonomy DB does not exist: {db_path}")
    return db_path


def get_build_info(
    db_path: Path | str,
    *,
    taxon_weaver_bin: str = "taxon-weaver",
) -> dict[str, Any]:
    """Read taxonomy build metadata from `taxon-weaver`."""

    payload = run_taxon_weaver(
        ["build-info", "--db", str(require_taxonomy_db(db_path))],
        taxon_weaver_bin=taxon_weaver_bin,
    )
    if not isinstance(payload, dict):
        raise TaxonomyCommandError("taxon-weaver build-info did not return a JSON object")
    return payload


def get_build_version(
    db_path: Path | str,
    *,
    taxon_weaver_bin: str = "taxon-weaver",
) -> str:
    """Return the stable taxonomy build version string."""

    build_info = get_build_info(db_path, taxon_weaver_bin=taxon_weaver_bin)
    return str(build_info.get("taxonomy_build_version", "")).strip()


def inspect_lineage(
    taxid: int,
    db_path: Path | str,
    *,
    taxon_weaver_bin: str = "taxon-weaver",
) -> list[dict[str, Any]]:
    """Read cached lineage for one taxid."""

    payload = run_taxon_weaver(
        ["inspect-lineage", "--db", str(require_taxonomy_db(db_path)), "--taxid", str(taxid)],
        taxon_weaver_bin=taxon_weaver_bin,
    )
    if not isinstance(payload, dict):
        raise TaxonomyCommandError("taxon-weaver inspect-lineage did not return a JSON object")
    lineage = payload.get("lineage", [])
    if not isinstance(lineage, list):
        raise TaxonomyCommandError("taxon-weaver inspect-lineage returned an invalid lineage payload")
    return lineage


def resolve_name(
    name: str,
    db_path: Path | str,
    *,
    provided_level: str | None = None,
    allow_fuzzy: bool = True,
    taxon_weaver_bin: str = "taxon-weaver",
) -> dict[str, Any]:
    """Resolve one name through `taxon-weaver` and return the JSON payload."""

    command = ["resolve-name", name, "--db", str(require_taxonomy_db(db_path))]
    if provided_level:
        command.extend(["--level", provided_level])
    if not allow_fuzzy:
        command.append("--no-fuzzy")

    payload = run_taxon_weaver(command, taxon_weaver_bin=taxon_weaver_bin)
    if not isinstance(payload, dict):
        raise TaxonomyCommandError("taxon-weaver resolve-name did not return a JSON object")
    return payload


def lineage_to_string(lineage: list[dict[str, Any]]) -> str:
    """Render lineage as a readable delimited string."""

    return " > ".join(str(entry.get("name", "")).strip() for entry in lineage if entry.get("name"))


def parent_lineage_entry(lineage: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the parent lineage entry for the terminal taxon when available."""

    if len(lineage) < 2:
        return {}
    return dict(lineage[-2])


def terminal_lineage_entry(lineage: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the most specific lineage entry, if available."""

    if not lineage:
        return {}
    return dict(lineage[-1])


def build_taxonomy_rows(
    lineage: list[dict[str, Any]],
    *,
    taxonomy_build_version: str,
) -> list[dict[str, str]]:
    """Shape one lineage payload into explicit taxonomy rows for every ancestor."""

    source = f"taxon_weaver:{taxonomy_build_version}"
    rows: list[dict[str, str]] = []
    previous_taxid = ""
    seen_taxids: set[str] = set()

    for entry in lineage:
        taxid = str(entry.get("taxid", "")).strip()
        if not taxid or taxid in seen_taxids:
            previous_taxid = taxid or previous_taxid
            continue
        rows.append(
            {
                "taxon_id": taxid,
                "taxon_name": str(entry.get("name", "")),
                "parent_taxon_id": previous_taxid,
                "rank": str(entry.get("rank", "")),
                "source": source,
            }
        )
        seen_taxids.add(taxid)
        previous_taxid = taxid

    return rows


def build_taxonomy_row(
    taxid: int | str,
    lineage: list[dict[str, Any]],
    *,
    taxonomy_build_version: str,
) -> dict[str, str]:
    """Shape one taxon-weaver lineage result into a taxonomy row."""

    terminal = terminal_lineage_entry(lineage)
    parent = parent_lineage_entry(lineage)
    return {
        "taxon_id": str(taxid),
        "taxon_name": str(terminal.get("name", "")),
        "parent_taxon_id": str(parent.get("taxid", "")),
        "rank": str(terminal.get("rank", "")),
        "source": f"taxon_weaver:{taxonomy_build_version}",
    }


def run_taxon_weaver(
    arguments: list[str],
    *,
    taxon_weaver_bin: str = "taxon-weaver",
) -> Any:
    """Run `taxon-weaver` and parse JSON output."""

    command = [taxon_weaver_bin, *arguments]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "no stderr"
        raise TaxonomyCommandError(f"taxon-weaver failed: {' '.join(command)} :: {stderr}")
    stdout = result.stdout.strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise TaxonomyCommandError(
            f"taxon-weaver returned invalid JSON for command: {' '.join(command)}"
        ) from exc
