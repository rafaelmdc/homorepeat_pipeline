# Scale Guide

This guide summarizes the current scaling model, default resource shape, and operational advice for larger runs.

Related stable docs:
- [Benchmark Guide](./benchmark_guide.md)
- [Operations](./operations.md)
- [Contracts](./contracts.md)

## Current scaling model

The pipeline now parallelizes both major heavy phases:
- acquisition fans out by planned batch
- detection and codon finalization fan out by `batch_id x method x repeat_residue`

Current published-layout rule:
- `raw` is now the default acquisition publish mode and publishes acquisition artifacts under `publish/acquisition/batches/<batch_id>/`
- `merged` keeps the legacy flat acquisition bundle under `publish/acquisition/`
- canonical `publish/calls/` remains present in both modes
- `publish/database/` and `publish/reports/` are merged-only
- run metadata publishes separately under `publish/metadata/` and is the authoritative place to detect the mode

## Default concurrency and memory

The current defaults in [`conf/base.config`](../conf/base.config) are:
- `params.batch_size = 10`
- `planning.maxForks = 1`
- `acquisition_download.maxForks = 2`
- `acquisition_normalize.maxForks = 2`
- `acquisition_translate.maxForks = 2`
- `acquisition_merge.maxForks = 1`
- `detection.maxForks = 4`
- `database.maxForks = 1`
- `reporting.maxForks = 1`

Each task still requests `cpus = 1`. The bounded defaults now also set explicit memory requests:
- `acquisition_download.memory = 2 GB`
- `acquisition_normalize.memory = 6 GB`
- `acquisition_translate.memory = 4 GB`
- `acquisition_merge.memory = 2 GB`
- `detection.memory = 2 GB`

Scaling still comes from more concurrent tasks, not from multithreaded Python CLIs.

## Recommended shape for ~900 genomes

For a one-host Docker run:
- keep the `docker` profile
- keep batches small enough to balance uneven genomes and make `-resume` useful
- keep the default `batch_size = 10` unless benchmark data on that host supports raising it
- prefer a scratch-backed `workDir` on local NVMe or other fast local storage for large runs

The intended operational pattern is:
1. prepare a plain-text accession list with one assembly accession per line
2. run `nextflow run .` with the `docker` profile, a stable `--run_id`, and an explicit scratch `--work_dir` when available
3. use `-resume` if the run is interrupted or if container images are rebuilt mid-run
4. use `publish/status/accession_status.tsv` to identify accession-level failures instead of reconstructing them from Nextflow work dirs

Example:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id run_900_genomes \
  --accessions_file path/to/accessions.txt \
  --work_dir /scratch/homorepeat/run_900_genomes/work \
  -resume
```

## What is published for recovery

Large runs now publish a stable operational ledger under `publish/status/`:
- `accession_status.tsv`: one row per requested accession
- `accession_call_counts.tsv`: one row per accession x method x repeat residue
- `status_summary.json`: accession-level outcome counts when the reporting path completes

This complements Nextflow caching:
- `-resume` knows which tasks do not need to rerun
- the status ledger tells you which accessions succeeded, failed, or produced no calls

## What was verified

As of April 9, 2026:
- live Docker smokes against NCBI completed successfully in both `raw` and `merged` acquisition publish modes
- live multi-batch Docker runs with `batch_size=2` completed successfully in both `raw` and `merged` modes
- `raw` runs published flat batch roots under `publish/acquisition/batches/<batch_id>/`
- `merged` runs published the legacy flat acquisition bundle plus merged-only database and report artifacts
- manifests now distinguish `params.params_file_values` from `params.effective_values`, so CLI overrides such as `--batch_size 1` are recorded correctly
