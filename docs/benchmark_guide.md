# Benchmark Guide

## Reference benchmark

The reference scale benchmark for this optimization phase is:

- [`examples/accessions/chr_accessions.txt`](../examples/accessions/chr_accessions.txt)

This file contains the same `897` accessions used by the April 8, 2026 chromosome-scale run stored under `runs/real_run_chr_v2/internal/planning/selected_accessions.txt`.

Use this accession set when comparing performance changes across slices unless a change explicitly needs a smaller fixture first.

## Current baseline

The current baseline came from `runs/real_run_chr_v2`:

- run root size was roughly `491G`
- `NORMALIZE_CDS_BATCH` peak RSS ranged from roughly `2.3 GB` to `4.2 GB`
- the run failed during normalize, before translate or detection began

That means later improvements should be judged against the same benchmark input and these same measurement categories, not against ad hoc smoke runs alone.

## Measurement checklist

For each benchmark rerun, capture:

- peak RSS by process from `trace.txt`
- total size of the run root and any external work directory
- time to first translated batch completion
- time to first detection task completion

## Summary command

Use the benchmark summary CLI to normalize these measurements into one JSON artifact:

```bash
env PYTHONPATH=src python -m homorepeat.cli.summarize_benchmark_run \
  --trace runs/<run_id>/internal/nextflow/trace.txt \
  --accessions-file examples/accessions/chr_accessions.txt \
  --size-path runs/<run_id> \
  --outpath runs/<run_id>/internal/benchmark_summary.json
```

If `workDir` lives outside the run root, add another `--size-path`:

```bash
env PYTHONPATH=src python -m homorepeat.cli.summarize_benchmark_run \
  --trace runs/<run_id>/internal/nextflow/trace.txt \
  --accessions-file examples/accessions/chr_accessions.txt \
  --size-path runs/<run_id> \
  --size-path /scratch/homorepeat_work/<run_id> \
  --outpath runs/<run_id>/internal/benchmark_summary.json
```

The summary JSON is the comparison artifact for later slices. It is intentionally simple and trace-derived, so it can be regenerated after every optimization change.
