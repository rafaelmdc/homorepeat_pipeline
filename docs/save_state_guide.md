# Save State Guide

## Purpose

This guide explains the two recovery layers now present in the pipeline:
- Nextflow task caching via `-resume`
- published accession-level status artifacts under `publish/status/`

You want both for large runs.

## What `-resume` does

`-resume` is task-cache recovery.

It helps when:
- the machine reboots
- a Docker image had to be rebuilt
- a run was interrupted after many completed tasks

It does not, by itself, tell you which accession inside a completed batch failed biologically or produced no calls.

## What the status ledger does

The pipeline now publishes:
- `publish/status/accession_status.tsv`
- `publish/status/accession_call_counts.tsv`
- `publish/status/status_summary.json`

These files are the operational source of truth after a run finishes.

### `accession_status.tsv`

One row per requested accession.

Useful columns include:
- `terminal_status`
- `failure_stage`
- `failure_reason`
- `n_genomes`
- `n_proteins`
- `n_repeat_calls`

### `accession_call_counts.tsv`

One row per accession x method x repeat residue.

Useful columns include:
- `method`
- `repeat_residue`
- `detect_status`
- `finalize_status`
- `n_repeat_calls`

### `status_summary.json`

Run-level summary used by the run manifest to distinguish:
- `success`
- `partial`
- `failed`

## Recommended rerun workflow

1. Check `publish/status/status_summary.json`.
2. If the run is `success`, no recovery action is needed.
3. If the run is `partial`, inspect `publish/status/accession_status.tsv`.
4. Build a new accession list from failed or skipped-upstream rows if you want a focused rerun.
5. Use `-resume` when continuing the same run root.

## Practical rule

Use `-resume` to save computation.
Use the status files to understand biology- and accession-level outcomes.
