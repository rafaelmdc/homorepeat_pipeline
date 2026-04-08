#!/usr/bin/env python3
"""Assemble validated flat outputs into the final HomoRepeat SQLite artifact."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from homorepeat.db.sqlite_build import (  # noqa: E402
    build_sqlite_database,
    write_sqlite_validation,
)
from homorepeat.io.tsv_io import ContractError  # noqa: E402


RESOURCE_SQL_DIR = Path(__file__).resolve().parents[1] / "resources" / "sql" / "sqlite"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy-tsv", required=True, help="Path to canonical taxonomy.tsv")
    parser.add_argument("--genomes-tsv", required=True, help="Path to canonical genomes.tsv")
    parser.add_argument("--sequences-tsv", required=True, help="Path to canonical sequences.tsv")
    parser.add_argument("--proteins-tsv", required=True, help="Path to canonical proteins.tsv")
    parser.add_argument(
        "--call-tsv",
        action="append",
        default=[],
        help="Path to one call table to import into repeat_calls",
    )
    parser.add_argument(
        "--run-params-tsv",
        action="append",
        default=[],
        help="Path to one run_params.tsv fragment",
    )
    parser.add_argument(
        "--schema-sql",
        default=str(RESOURCE_SQL_DIR / "schema.sql"),
        help="Path to the SQLite schema SQL file",
    )
    parser.add_argument(
        "--indexes-sql",
        default=str(RESOURCE_SQL_DIR / "indexes.sql"),
        help="Path to the SQLite indexes SQL file",
    )
    parser.add_argument("--outdir", required=True, help="Output directory for the SQLite artifact")
    parser.add_argument("--log-file", help="Reserved log file path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outdir = Path(args.outdir)
    sqlite_path = outdir / "homorepeat.sqlite"
    validation_path = outdir / "sqlite_validation.json"

    try:
        validation_payload = build_sqlite_database(
            sqlite_path,
            schema_sql_path=args.schema_sql,
            indexes_sql_path=args.indexes_sql,
            taxonomy_tsv=args.taxonomy_tsv,
            genomes_tsv=args.genomes_tsv,
            sequences_tsv=args.sequences_tsv,
            proteins_tsv=args.proteins_tsv,
            run_params_tsvs=args.run_params_tsv,
            repeat_call_tsvs=args.call_tsv,
        )
    except sqlite3.IntegrityError as exc:
        raise ContractError(f"SQLite import failed integrity checks: {exc}") from exc
    except sqlite3.DatabaseError as exc:
        raise ContractError(f"SQLite build failed: {exc}") from exc

    if validation_payload.get("status") != "pass":
        write_sqlite_validation(validation_path, validation_payload)
        raise ContractError("SQLite validation checks failed after import")

    write_sqlite_validation(validation_path, validation_payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3) from exc
