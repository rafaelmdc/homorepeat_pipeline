# Scale Guide

For the redesign plan and implementation order, see:

- [Pipeline Performance and Scalability Roadmap](./performance_roadmap.md)
- [Pipeline Performance Implementation Slices](./performance_slices.md)

## Current scaling model

The pipeline now parallelizes both major heavy phases:
- acquisition fans out by planned batch
- detection and codon finalization fan out by `batch_id x method x repeat_residue`

Canonical outputs remain merged under `publish/acquisition/`, `publish/calls/`, `publish/database/`, and `publish/reports/`.
Run metadata publishes separately under `publish/metadata/`.

## Default concurrency

The current defaults in [`conf/base.config`](../conf/base.config) are:
- `params.batch_size = 25`
- `planning.maxForks = 1`
- `acquisition_download.maxForks = 2`
- `acquisition_normalize.maxForks = 4`
- `acquisition_merge.maxForks = 1`
- `detection.maxForks = 4`
- `database.maxForks = 1`
- `reporting.maxForks = 1`

Each task currently requests `cpus = 1`. Scaling today comes from more concurrent tasks, not from multithreaded Python CLIs.

## Recommended shape for ~900 genomes

For a one-host Docker run:
- keep the `docker` profile
- keep batches small enough to balance uneven genomes and make `-resume` useful
- prefer the default `batch_size = 25` unless host limits force a change

The intended operational pattern is:
1. prepare a plain-text accession list with one assembly accession per line
2. run `nextflow run .` with the `docker` profile and a stable `--run_id`
3. use `-resume` if the run is interrupted or if container images are rebuilt mid-run
4. use `publish/status/accession_status.tsv` to identify accession-level failures instead of reconstructing them from Nextflow work dirs

Example:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id run_900_genomes \
  --accessions_file path/to/accessions.txt \
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

As of April 8, 2026:
- real Docker smoke runs on 5 live NCBI accessions completed successfully
- batch fan-out was observed in the Nextflow trace
- multi-residue runs (`Q,N`) now merge correctly into canonical `repeat_calls.tsv` and residue-scoped `run_params.tsv`
- accession status and per-method/per-residue call counts were published correctly
