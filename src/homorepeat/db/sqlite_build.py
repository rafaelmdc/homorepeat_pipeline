"""Helpers for assembling the final HomoRepeat SQLite artifact."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

from homorepeat.contracts.repeat_features import CALL_FIELDNAMES, validate_call_row
from homorepeat.contracts.run_params import RUN_PARAM_FIELDNAMES
from homorepeat.io.tsv_io import ContractError, ensure_directory, read_tsv


GENOMES_FIELDNAMES = [
    "genome_id",
    "source",
    "accession",
    "genome_name",
    "assembly_type",
    "taxon_id",
    "assembly_level",
    "species_name",
    "download_path",
    "notes",
]
TAXONOMY_FIELDNAMES = ["taxon_id", "taxon_name", "parent_taxon_id", "rank", "source"]
SEQUENCES_FIELDNAMES = [
    "sequence_id",
    "genome_id",
    "sequence_name",
    "sequence_length",
    "sequence_path",
    "gene_symbol",
    "transcript_id",
    "isoform_id",
    "assembly_accession",
    "taxon_id",
    "source_record_id",
    "protein_external_id",
    "translation_table",
    "gene_group",
    "linkage_status",
    "partial_status",
]
PROTEINS_FIELDNAMES = [
    "protein_id",
    "sequence_id",
    "genome_id",
    "protein_name",
    "protein_length",
    "protein_path",
    "gene_symbol",
    "translation_method",
    "translation_status",
    "assembly_accession",
    "taxon_id",
    "gene_group",
    "protein_external_id",
]
VALID_METHODS = {"pure", "threshold"}


def load_import_rows(path: Path | str, *, required_columns: Sequence[str]) -> list[dict[str, str]]:
    """Read one import TSV and enforce its required columns."""

    return read_tsv(path, required_columns=required_columns)


def validate_unique_keys(rows: Sequence[dict[str, str]], key_field: str, *, label: str) -> None:
    """Reject duplicate primary keys before import."""

    seen: set[str] = set()
    duplicates: list[str] = []
    for row in rows:
        key = row.get(key_field, "")
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    if duplicates:
        duplicate_text = ", ".join(sorted(set(duplicates))[:5])
        raise ContractError(f"{label} contains duplicate {key_field} values: {duplicate_text}")


def validate_run_params_rows(rows: Sequence[dict[str, str]]) -> None:
    """Validate the flat run-parameter contract before import."""

    seen_keys: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for row in rows:
        method = row.get("method", "")
        param_name = row.get("param_name", "")
        param_value = row.get("param_value", "")
        if not method or not param_name or param_value == "":
            raise ContractError("run_params.tsv contains an empty required field")
        key = (method, param_name)
        if key in seen_keys:
            duplicates.append(key)
        seen_keys.add(key)
    if duplicates:
        duplicate_text = ", ".join(f"{method}:{param}" for method, param in duplicates[:5])
        raise ContractError(f"run_params.tsv contains duplicate method/param_name pairs: {duplicate_text}")


def validate_repeat_call_rows(rows: Sequence[dict[str, str]]) -> None:
    """Validate repeat-call rows before import."""

    validate_unique_keys(rows, "call_id", label="repeat_calls")
    for row in rows:
        method = row.get("method", "")
        if method not in VALID_METHODS:
            raise ContractError(f"repeat_calls contains an invalid method: {method!r}")
        try:
            purity = float(row.get("purity", ""))
        except ValueError as exc:
            raise ContractError("repeat_calls contains a non-numeric purity value") from exc
        if purity < 0.0 or purity > 1.0:
            raise ContractError(f"repeat_calls contains an out-of-range purity value: {purity}")
        validate_call_row(row)


def build_sqlite_database(
    sqlite_path: Path | str,
    *,
    schema_sql_path: Path | str,
    indexes_sql_path: Path | str,
    taxonomy_rows: Sequence[dict[str, str]],
    genomes_rows: Sequence[dict[str, str]],
    sequences_rows: Sequence[dict[str, str]],
    proteins_rows: Sequence[dict[str, str]],
    run_params_rows: Sequence[dict[str, str]],
    repeat_call_rows: Sequence[dict[str, str]],
) -> dict[str, object]:
    """Build the SQLite artifact and return a validation payload."""

    sqlite_file = Path(sqlite_path)
    ensure_directory(sqlite_file)
    if sqlite_file.exists():
        sqlite_file.unlink()

    schema_sql = Path(schema_sql_path).read_text(encoding="utf-8")
    indexes_sql = Path(indexes_sql_path).read_text(encoding="utf-8")

    connection = sqlite3.connect(sqlite_file)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema_sql)

        with connection:
            _insert_rows(connection, "taxonomy", TAXONOMY_FIELDNAMES, taxonomy_rows)
            _insert_rows(connection, "genomes", GENOMES_FIELDNAMES, genomes_rows)
            _insert_rows(connection, "sequences", SEQUENCES_FIELDNAMES, sequences_rows)
            _insert_rows(connection, "proteins", PROTEINS_FIELDNAMES, proteins_rows)
            _insert_rows(connection, "run_params", RUN_PARAM_FIELDNAMES, run_params_rows)
            _insert_rows(connection, "repeat_calls", CALL_FIELDNAMES, repeat_call_rows)

        connection.executescript(indexes_sql)
        validation_payload = _build_validation_payload(
            connection,
            taxonomy_rows=taxonomy_rows,
            genomes_rows=genomes_rows,
            sequences_rows=sequences_rows,
            proteins_rows=proteins_rows,
            run_params_rows=run_params_rows,
            repeat_call_rows=repeat_call_rows,
        )
        return validation_payload
    finally:
        connection.close()


def write_sqlite_validation(path: Path | str, payload: dict[str, object]) -> None:
    """Write the SQLite validation payload as stable JSON."""

    file_path = Path(path)
    ensure_directory(file_path)
    file_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _insert_rows(
    connection: sqlite3.Connection,
    table_name: str,
    fieldnames: Sequence[str],
    rows: Sequence[dict[str, str]],
) -> None:
    if not rows:
        return
    placeholders = ", ".join("?" for _ in fieldnames)
    column_list = ", ".join(fieldnames)
    sql = f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})"
    values = [tuple(_coerce_import_value(row.get(field, ""), field) for field in fieldnames) for row in rows]
    connection.executemany(sql, values)


def _coerce_import_value(value: str, fieldname: str) -> object:
    if fieldname in {
        "sequence_length",
        "protein_length",
        "start",
        "end",
        "length",
        "repeat_count",
        "non_repeat_count",
    }:
        return int(value)
    if fieldname == "purity":
        return float(value)
    return value


def _build_validation_payload(
    connection: sqlite3.Connection,
    *,
    taxonomy_rows: Sequence[dict[str, str]],
    genomes_rows: Sequence[dict[str, str]],
    sequences_rows: Sequence[dict[str, str]],
    proteins_rows: Sequence[dict[str, str]],
    run_params_rows: Sequence[dict[str, str]],
    repeat_call_rows: Sequence[dict[str, str]],
) -> dict[str, object]:
    counts = {
        "taxonomy": _count_rows(connection, "taxonomy"),
        "genomes": _count_rows(connection, "genomes"),
        "sequences": _count_rows(connection, "sequences"),
        "proteins": _count_rows(connection, "proteins"),
        "run_params": _count_rows(connection, "run_params"),
        "repeat_calls": _count_rows(connection, "repeat_calls"),
    }
    expected_counts = {
        "taxonomy": len(taxonomy_rows),
        "genomes": len(genomes_rows),
        "sequences": len(sequences_rows),
        "proteins": len(proteins_rows),
        "run_params": len(run_params_rows),
        "repeat_calls": len(repeat_call_rows),
    }
    checks = {
        "taxonomy_row_count_matches": counts["taxonomy"] == expected_counts["taxonomy"],
        "genomes_row_count_matches": counts["genomes"] == expected_counts["genomes"],
        "sequences_row_count_matches": counts["sequences"] == expected_counts["sequences"],
        "proteins_row_count_matches": counts["proteins"] == expected_counts["proteins"],
        "run_params_row_count_matches": counts["run_params"] == expected_counts["run_params"],
        "repeat_calls_row_count_matches": counts["repeat_calls"] == expected_counts["repeat_calls"],
        "all_sequences_belong_to_genomes": _count_query(
            connection,
            "SELECT COUNT(*) FROM sequences LEFT JOIN genomes USING(genome_id) WHERE genomes.genome_id IS NULL",
        )
        == 0,
        "all_proteins_belong_to_sequences": _count_query(
            connection,
            "SELECT COUNT(*) FROM proteins LEFT JOIN sequences USING(sequence_id) WHERE sequences.sequence_id IS NULL",
        )
        == 0,
        "all_proteins_belong_to_genomes": _count_query(
            connection,
            "SELECT COUNT(*) FROM proteins LEFT JOIN genomes USING(genome_id) WHERE genomes.genome_id IS NULL",
        )
        == 0,
        "all_calls_belong_to_proteins": _count_query(
            connection,
            "SELECT COUNT(*) FROM repeat_calls LEFT JOIN proteins USING(protein_id) WHERE proteins.protein_id IS NULL",
        )
        == 0,
        "all_calls_belong_to_sequences": _count_query(
            connection,
            "SELECT COUNT(*) FROM repeat_calls LEFT JOIN sequences USING(sequence_id) WHERE sequences.sequence_id IS NULL",
        )
        == 0,
        "all_calls_belong_to_genomes": _count_query(
            connection,
            "SELECT COUNT(*) FROM repeat_calls LEFT JOIN genomes USING(genome_id) WHERE genomes.genome_id IS NULL",
        )
        == 0,
        "all_calls_have_taxonomy": _count_query(
            connection,
            "SELECT COUNT(*) FROM repeat_calls LEFT JOIN taxonomy USING(taxon_id) WHERE taxonomy.taxon_id IS NULL",
        )
        == 0,
    }
    status = "pass" if all(checks.values()) else "fail"
    return {
        "status": status,
        "scope": "sqlite",
        "counts": counts,
        "expected_counts": expected_counts,
        "checks": checks,
    }


def _count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    return _count_query(connection, f"SELECT COUNT(*) FROM {table_name}")


def _count_query(connection: sqlite3.Connection, sql: str) -> int:
    row = connection.execute(sql).fetchone()
    return int(row[0]) if row is not None else 0
