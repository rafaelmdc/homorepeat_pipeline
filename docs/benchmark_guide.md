# Benchmark Guide

## Benchmark Inputs

Use fixed accession sets when comparing changes.

Checked-in inputs:

- smoke-scale input: [`examples/accessions/smoke_human.txt`](../examples/accessions/smoke_human.txt)
- larger reference input: [`examples/accessions/chr_accessions.txt`](../examples/accessions/chr_accessions.txt)

Do not compare ad hoc runs against benchmark runs unless the input list, publish mode, and key parameters are the same.

## What to Measure

For each benchmark run, capture:

- peak RSS by process from `trace.txt`
- total disk footprint of the run root
- total disk footprint of any external `workDir`
- time to first translated batch completion
- time to first detection-task completion
- number of accessions in the benchmark input

## Summary CLI

Use the benchmark summary CLI to turn a run into one JSON comparison artifact:

```bash
env PYTHONPATH=src python -m homorepeat.cli.summarize_benchmark_run \
  --trace runs/<run_id>/internal/nextflow/trace.txt \
  --accessions-file examples/accessions/chr_accessions.txt \
  --size-path runs/<run_id> \
  --outpath runs/<run_id>/internal/benchmark_summary.json
```

If `workDir` lives outside the run root, include it explicitly:

```bash
env PYTHONPATH=src python -m homorepeat.cli.summarize_benchmark_run \
  --trace runs/<run_id>/internal/nextflow/trace.txt \
  --accessions-file examples/accessions/chr_accessions.txt \
  --size-path runs/<run_id> \
  --size-path /scratch/homorepeat_work/<run_id> \
  --outpath runs/<run_id>/internal/benchmark_summary.json
```

## What the Summary Contains

The summary JSON is derived from the Nextflow trace and the requested size paths. It records:

- total task counts and completed-task counts
- estimated elapsed time
- peak RSS by process
- milestone timings for first normalize, translate, and detection completions
- optional accession-count metadata
- optional size measurements for the run root and work directory

## Recommended Comparison Workflow

1. Choose a fixed accession set.
2. Keep the profile, publish mode, and key params stable between runs.
3. Save `benchmark_summary.json` beside each run.
4. Compare the JSON artifacts rather than relying on memory or terminal logs.
5. If a change improves throughput but increases memory or disk sharply, record that tradeoff explicitly.

## Implementation Notes

The summary CLI expects the standard Nextflow trace columns:

- `name`
- `status`
- `submit`
- `realtime`
- `peak_rss`

If those columns are missing, the benchmark summary will fail fast rather than silently under-reporting run characteristics.
