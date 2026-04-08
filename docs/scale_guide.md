# Scale Guide

For the redesign plan and implementation order, see:

- [Benchmark Guide](./benchmark_guide.md)
- [Pipeline Performance and Scalability Roadmap](./performance_roadmap.md)
- [Pipeline Performance Implementation Slices](./performance_slices.md)
- [Remaining Memory Streaming Roadmap](./memory_streaming_roadmap.md)
- [Remaining Memory Streaming Slices](./memory_streaming_slices.md)

## Current scaling model

The pipeline now parallelizes both major heavy phases:
- acquisition fans out by planned batch
- detection and codon finalization fan out by `batch_id x method x repeat_residue`

Canonical outputs remain merged under `publish/acquisition/`, `publish/calls/`, `publish/database/`, and `publish/reports/`.
Run metadata publishes separately under `publish/metadata/`.

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

As of April 8, 2026:
- a real Docker benchmark run on 1 live NCBI accession completed successfully after the canonical ID migration
- batch fan-out was observed in the Nextflow trace
- multi-residue runs (`Q,N`) now merge correctly into canonical `repeat_calls.tsv` and residue-scoped `run_params.tsv`
- accession status and per-method/per-residue call counts were published correctly
- source-derived canonical IDs were verified in live published outputs and SQLite import
