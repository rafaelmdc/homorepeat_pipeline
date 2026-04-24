# Resume and Recovery

## Two Recovery Layers

The workflow has two complementary recovery mechanisms:

- Nextflow task caching via `-resume`
- published metadata and accession-level status artifacts under `publish/`

Use both for any non-trivial run.

## What `-resume` Does

`-resume` is cache recovery at the task level.

It helps when:

- the machine reboots
- a run is interrupted
- containers are rebuilt
- you want to continue the same run root without recomputing successful tasks

It does not tell you which accession failed biologically or produced zero retained proteins or zero calls. That is what the status ledger is for.

## Metadata That Survives Failures

Even on failed runs, the workflow tries to publish:

- `publish/metadata/launch_metadata.json`
- `publish/metadata/run_manifest.json`
- `publish/metadata/nextflow/report.html`
- `publish/metadata/nextflow/trace.txt`

Start there when the run exits nonzero.

## Accession-Level Status Ledger

When the reducer completes, the workflow publishes:

- `publish/status/accession_status.tsv`
- `publish/status/accession_call_counts.tsv`
- `publish/status/status_summary.json`

These files are supplemental diagnostics. Native Nextflow success/failure remains the run-level source of truth.

### `accession_status.tsv`

One row per requested accession.

Most useful fields:

- `download_status`
- `normalize_status`
- `translate_status`
- `detect_status`
- `finalize_status`
- `terminal_status`
- `failure_stage`
- `failure_reason`
- `n_genomes`
- `n_proteins`
- `n_repeat_calls`

Current `terminal_status` values:

- `completed`
- `completed_no_calls`
- `failed`
- `skipped_upstream_failed`

### `accession_call_counts.tsv`

One row per accession x method x repeat residue.

Useful when you need to distinguish:

- a method that failed
- a method that ran and produced zero calls
- a method that was skipped because an upstream stage failed

### `status_summary.json`

Run-level reduction of the accession ledger.

Current top-level `status` values:

- `success`
- `partial`

`partial` means at least one accession failed or was skipped upstream.

## Recommended Rerun Workflow

1. Check the native Nextflow exit status and `publish/metadata/nextflow/report.html`.
2. Read `publish/metadata/run_manifest.json` to confirm run mode, enabled methods, and published artifacts.
3. If present, inspect `publish/status/status_summary.json`.
4. If you need accession-level diagnosis, inspect `publish/status/accession_status.tsv`.
5. Build a new accession list from `failed` or `skipped_upstream_failed` rows if you want a focused rerun.
6. Use `-resume` when continuing the same run root and work directory.

## Practical Rule

Use `-resume` to save computation.

Use the status ledger to decide what actually needs to be rerun.
