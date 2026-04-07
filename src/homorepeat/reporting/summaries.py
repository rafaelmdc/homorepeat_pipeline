"""Summary and reporting-table helpers for finalized repeat-call outputs."""

from __future__ import annotations

import json
from collections import defaultdict
from statistics import mean, median
from typing import Iterable, Sequence

from homorepeat.contracts.repeat_features import validate_call_row
from homorepeat.io.tsv_io import ContractError


SUMMARY_FIELDNAMES = [
    "method",
    "repeat_residue",
    "taxon_id",
    "taxon_name",
    "n_genomes",
    "n_proteins",
    "n_calls",
    "mean_length",
    "mean_purity",
    "codon_metric_name",
    "mean_codon_metric",
    "median_length",
    "max_length",
    "mean_start_fraction",
]

REGRESSION_FIELDNAMES = [
    "method",
    "repeat_residue",
    "group_label",
    "repeat_length",
    "n_observations",
    "codon_metric_name",
    "mean_codon_metric",
    "filtered_max_length",
    "transformed_codon_metric",
]


def build_summary_by_taxon(
    call_rows: Sequence[dict[str, str]],
    proteins_rows: Sequence[dict[str, str]],
    taxonomy_rows: Sequence[dict[str, str]],
) -> list[dict[str, object]]:
    """Aggregate finalized calls directly by taxon and method."""

    taxonomy_name_by_id = {row.get("taxon_id", ""): row.get("taxon_name", "") for row in taxonomy_rows}
    protein_rows_by_id = {row.get("protein_id", ""): row for row in proteins_rows}

    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in call_rows:
        validate_call_row(row)
        method = row.get("method", "")
        repeat_residue = row.get("repeat_residue", "")
        taxon_id = row.get("taxon_id", "")
        grouped[(method, repeat_residue, taxon_id)].append(row)

    summary_rows: list[dict[str, object]] = []
    for (method, repeat_residue, taxon_id), rows in sorted(grouped.items()):
        lengths = [int(row["length"]) for row in rows]
        purities = [float(row["purity"]) for row in rows]
        start_fractions: list[float] = []
        genome_ids = {row["genome_id"] for row in rows}
        protein_ids = {row["protein_id"] for row in rows}
        for row in rows:
            protein_length_text = protein_rows_by_id.get(row["protein_id"], {}).get("protein_length", "")
            if not protein_length_text:
                continue
            protein_length = int(protein_length_text)
            if protein_length <= 0:
                continue
            start_fractions.append(int(row["start"]) / protein_length)

        summary_rows.append(
            {
                "method": method,
                "repeat_residue": repeat_residue,
                "taxon_id": taxon_id,
                "taxon_name": taxonomy_name_by_id.get(taxon_id, ""),
                "n_genomes": len(genome_ids),
                "n_proteins": len(protein_ids),
                "n_calls": len(rows),
                "mean_length": _format_decimal(mean(lengths)),
                "mean_purity": _format_decimal(mean(purities)),
                "codon_metric_name": "",
                "mean_codon_metric": "",
                "median_length": _format_decimal(median(lengths)),
                "max_length": max(lengths),
                "mean_start_fraction": _format_decimal(mean(start_fractions)) if start_fractions else "",
            }
        )
    return summary_rows


def build_regression_input(call_rows: Sequence[dict[str, str]], taxonomy_rows: Sequence[dict[str, str]]) -> list[dict[str, object]]:
    """Aggregate finalized calls into taxon-direct repeat-length observations."""

    taxonomy_name_by_id = {row.get("taxon_id", ""): row.get("taxon_name", "") for row in taxonomy_rows}

    grouped: dict[tuple[str, str, str, int], int] = defaultdict(int)
    for row in call_rows:
        validate_call_row(row)
        key = (
            row.get("method", ""),
            row.get("repeat_residue", ""),
            row.get("taxon_id", ""),
            int(row.get("length", "0")),
        )
        grouped[key] += 1

    regression_rows: list[dict[str, object]] = []
    for (method, repeat_residue, taxon_id, repeat_length), count in sorted(grouped.items()):
        regression_rows.append(
            {
                "method": method,
                "repeat_residue": repeat_residue,
                "group_label": taxonomy_name_by_id.get(taxon_id, ""),
                "repeat_length": repeat_length,
                "n_observations": count,
                "codon_metric_name": "",
                "mean_codon_metric": "",
                "filtered_max_length": "",
                "transformed_codon_metric": "",
            }
        )
    return regression_rows


def build_echarts_options(
    summary_rows: Sequence[dict[str, str]],
    regression_rows: Sequence[dict[str, str]],
) -> dict[str, object]:
    """Build one inspectable, renderer-neutral ECharts options bundle."""

    if not summary_rows:
        raise ContractError("summary_by_taxon.tsv is empty; cannot prepare report tables")

    overview_categories = [f"{row['taxon_name']} | {row['method']} | {row['repeat_residue']}" for row in summary_rows]
    overview_values = [int(row["n_calls"]) for row in summary_rows]

    regression_points = [
        {
            "group_label": row["group_label"],
            "method": row["method"],
            "repeat_residue": row["repeat_residue"],
            "repeat_length": int(row["repeat_length"]),
            "n_observations": int(row["n_observations"]),
        }
        for row in regression_rows
    ]

    return {
        "taxon_method_overview": {
            "title": {"text": "Calls by Taxon, Method, and Residue"},
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": overview_categories},
            "yAxis": {"type": "value", "name": "Calls"},
            "series": [
                {
                    "name": "n_calls",
                    "type": "bar",
                    "data": overview_values,
                }
            ],
        },
        "repeat_length_distribution": {
            "title": {"text": "Repeat Length Observations"},
            "dataset": {"source": regression_points},
            "series": [
                {
                    "type": "scatter",
                    "encode": {
                        "x": "repeat_length",
                        "y": "n_observations",
                        "tooltip": ["group_label", "method", "repeat_residue", "repeat_length", "n_observations"],
                    },
                }
            ],
            "xAxis": {"type": "value", "name": "Repeat length"},
            "yAxis": {"type": "value", "name": "Observations"},
        },
    }


def serialize_echarts_options(options: dict[str, object]) -> str:
    """Render stable JSON for report-prep outputs."""

    return json.dumps(options, indent=2, sort_keys=True) + "\n"


def _format_decimal(value: float) -> str:
    return f"{value:.10f}".rstrip("0").rstrip(".")
