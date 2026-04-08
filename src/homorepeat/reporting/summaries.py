"""Summary and reporting-table helpers for finalized repeat-call outputs."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Iterable

from homorepeat.contracts.repeat_features import validate_call_row


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
    call_rows: Iterable[dict[str, str]],
    proteins_rows: Iterable[dict[str, str]],
    taxonomy_rows: Iterable[dict[str, str]],
) -> list[dict[str, object]]:
    """Aggregate finalized calls directly by taxon and method."""

    summary_rows, _ = build_summary_tables(
        call_rows=call_rows,
        proteins_rows=proteins_rows,
        taxonomy_rows=taxonomy_rows,
    )
    return summary_rows


def build_regression_input(
    call_rows: Iterable[dict[str, str]],
    taxonomy_rows: Iterable[dict[str, str]],
) -> list[dict[str, object]]:
    """Aggregate finalized calls into taxon-direct repeat-length observations."""

    _, regression_rows = build_summary_tables(
        call_rows=call_rows,
        proteins_rows=[],
        taxonomy_rows=taxonomy_rows,
    )
    return regression_rows


def build_summary_tables(
    *,
    call_rows: Iterable[dict[str, str]],
    proteins_rows: Iterable[dict[str, str]],
    taxonomy_rows: Iterable[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Build both summary tables in one streaming pass over call rows."""

    taxonomy_name_by_id = {row.get("taxon_id", ""): row.get("taxon_name", "") for row in taxonomy_rows}
    protein_length_by_id = {row.get("protein_id", ""): row.get("protein_length", "") for row in proteins_rows}

    summary_groups: dict[tuple[str, str, str], dict[str, object]] = {}
    regression_groups: Counter[tuple[str, str, str, int]] = Counter()
    for row in call_rows:
        validate_call_row(row)
        method = row.get("method", "")
        repeat_residue = row.get("repeat_residue", "")
        taxon_id = row.get("taxon_id", "")
        length = int(row.get("length", "0"))

        summary_key = (method, repeat_residue, taxon_id)
        summary_group = summary_groups.setdefault(
            summary_key,
            {
                "sum_length": 0,
                "sum_purity": 0.0,
                "length_counts": Counter(),
                "max_length": 0,
                "genome_ids": set(),
                "protein_ids": set(),
                "call_count": 0,
                "start_fraction_sum": 0.0,
                "start_fraction_count": 0,
            },
        )
        summary_group["sum_length"] += length
        summary_group["sum_purity"] += float(row.get("purity", "0"))
        summary_group["length_counts"][length] += 1
        summary_group["max_length"] = max(int(summary_group["max_length"]), length)
        summary_group["call_count"] += 1
        genome_id = row.get("genome_id", "")
        protein_id = row.get("protein_id", "")
        if genome_id:
            summary_group["genome_ids"].add(genome_id)
        if protein_id:
            summary_group["protein_ids"].add(protein_id)
        protein_length_text = protein_length_by_id.get(protein_id, "")
        if protein_length_text:
            protein_length = int(protein_length_text)
            if protein_length > 0:
                summary_group["start_fraction_sum"] += int(row.get("start", "0")) / protein_length
                summary_group["start_fraction_count"] += 1

        regression_groups[(method, repeat_residue, taxon_id, length)] += 1

    summary_rows: list[dict[str, object]] = []
    for (method, repeat_residue, taxon_id), group in sorted(summary_groups.items()):
        call_count = int(group["call_count"])
        start_fraction_count = int(group["start_fraction_count"])
        summary_rows.append(
            {
                "method": method,
                "repeat_residue": repeat_residue,
                "taxon_id": taxon_id,
                "taxon_name": taxonomy_name_by_id.get(taxon_id, ""),
                "n_genomes": len(group["genome_ids"]),
                "n_proteins": len(group["protein_ids"]),
                "n_calls": call_count,
                "mean_length": _format_decimal(int(group["sum_length"]) / call_count),
                "mean_purity": _format_decimal(float(group["sum_purity"]) / call_count),
                "codon_metric_name": "",
                "mean_codon_metric": "",
                "median_length": _format_decimal(_counter_median(group["length_counts"], call_count)),
                "max_length": int(group["max_length"]),
                "mean_start_fraction": _format_decimal(float(group["start_fraction_sum"]) / start_fraction_count)
                if start_fraction_count
                else "",
            }
        )

    regression_rows: list[dict[str, object]] = []
    for (method, repeat_residue, taxon_id, repeat_length), count in sorted(regression_groups.items()):
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
    return summary_rows, regression_rows


def build_echarts_options(
    summary_rows: Sequence[dict[str, str]],
    regression_rows: Sequence[dict[str, str]],
) -> dict[str, object]:
    """Build one inspectable, renderer-neutral ECharts options bundle."""

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


def _counter_median(counts: Counter[int], total_count: int) -> float:
    midpoint_low = (total_count - 1) // 2
    midpoint_high = total_count // 2
    seen = 0
    low_value = 0
    high_value = 0
    for value in sorted(counts):
        next_seen = seen + counts[value]
        if seen <= midpoint_low < next_seen:
            low_value = value
        if seen <= midpoint_high < next_seen:
            high_value = value
            break
        seen = next_seen
    return (low_value + high_value) / 2
