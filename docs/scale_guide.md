# Scale Guide

This guide summarizes the current scaling model, resource defaults, and operational advice for larger runs.

Related docs:

- [Operations](./operations.md)
- [Benchmark Guide](./benchmark_guide.md)
- [Save State Guide](./save_state_guide.md)

## Current Scaling Model

The main fan-out points are:

- acquisition by `batch_id`
- detection and codon finalization by `batch_id x method x repeat_residue`

The main fan-in points are:

- merged acquisition assembly in `merged` mode
- canonical call table merge
- accession status reduction
- SQLite and reporting in `merged` mode

`raw` mode is the lighter operational shape because it skips SQLite build and
report generation while still publishing the default v2 table contract.

## Default Resource Profile

Current defaults from `conf/base.config`:

| Label | CPUs | Memory | Max forks |
| --- | --- | --- | --- |
| `planning` | 1 | `1 GB` | 1 |
| `acquisition_download` | 1 | `2 GB` | 2 |
| `acquisition_normalize` | 1 | `6 GB` | 2 |
| `acquisition_translate` | 1 | `4 GB` | 2 |
| `acquisition_merge` | 1 | `2 GB` | 1 |
| `detection` | 1 | `2 GB` | 4 |
| `database` | 1 | `2 GB` | 1 |
| `reporting` | 1 | `1 GB` | 1 |

Other relevant defaults:

- `batch_size = 10`
- `run_pure = true`
- `run_threshold = true`
- `run_seed_extend = false`

The Python CLIs are effectively single-core tasks. Scaling comes from bounded task parallelism, not from multithreaded workers inside each task.

## Resource Control Knobs

The workflow uses Nextflow's local executor in both `docker` and `local`
profiles. Resource controls are therefore a combination of per-task requests and
task concurrency limits:

| Knob | Scope | Use when |
| --- | --- | --- |
| `-qs <N>` | Overall local task queue/concurrency cap | You want a simple upper bound on simultaneous local tasks |
| `-process.withLabel:<label>.maxForks <N>` | Concurrency cap for one process label | One stage is too aggressive, such as detection or normalization |
| `-process.withLabel:<label>.memory '<N> GB'` | Memory requested per task for one process label | A stage needs more memory per running task |
| `-process.withLabel:<label>.cpus <N>` | CPU slots requested per task for one process label | You need the scheduler/container metadata to reserve more cores |
| `--batch_size <N>` | Number of accessions per planned batch | You want to change biological/workflow batching, not directly cap CPU or memory |

Most pipeline tasks currently run single-core Python code, so raising `cpus`
usually does not make a task faster. To control host load, prefer `-qs` and
label-specific `maxForks`.

Examples:

```bash
# Limit total local task concurrency.
nextflow run . \
  -profile docker \
  -qs 4
```

```bash
# Run fewer detection tasks at once.
nextflow run . \
  -profile docker \
  -process.withLabel:detection.maxForks 2
```

```bash
# Give normalization tasks more memory.
nextflow run . \
  -profile docker \
  -process.withLabel:acquisition_normalize.memory '10 GB'
```

## Practical Tuning Order

1. Put `--work_dir` on fast local scratch before changing workflow parallelism.
2. Keep `batch_size` near the default until you have trace data showing that larger batches help on your host.
3. Use `--ncbi_cache_dir` if repeated downloads are a significant cost in your environment.
4. Increase concurrency only after checking peak RSS from the Nextflow trace.
5. Use `raw` mode when you want to defer merged-only steps and focus on acquisition plus calling throughput.

## Large-Run Recommendations

For a larger single-host Docker run:

- use the `docker` profile
- use a stable `--run_id`
- set an explicit `--work_dir` on fast scratch when available
- keep `NXF_HOME` persistent
- use `-resume` rather than restarting from scratch

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

Conservative CHR example with all three detection methods enabled:

```bash
RUN_ID="chr_v2_$(date -u +%Y%m%d_%H%M%SZ)"

NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log "runs/${RUN_ID}/internal/nextflow/nextflow.log" \
  run . \
  -profile docker \
  -qs 4 \
  -process.withLabel:acquisition_normalize.memory '8 GB' \
  -process.withLabel:detection.maxForks 3 \
  --run_id "${RUN_ID}" \
  --accessions_file examples/accessions/chr_accessions.txt \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend true
```

## Recovery at Scale

Large runs should rely on both:

- Nextflow cache recovery via `-resume`
- accession-level ledgers under `publish/tables/` and `publish/summaries/`

That combination lets you:

- avoid recomputing successful tasks
- identify which accessions actually failed or produced no calls
- build smaller rerun lists when needed

Use `publish/tables/accession_status.tsv` for accession-level diagnosis and
`publish/summaries/status_summary.json` for run-level reduction.

## Benchmark Before Tuning

Before changing `batch_size`, `maxForks`, or publish mode for a large accession set:

- run a representative benchmark
- record `trace.txt`
- summarize it with `homorepeat.cli.summarize_benchmark_run`
- compare peak RSS and time-to-first-result across runs

Use the [Benchmark Guide](./benchmark_guide.md) for the recommended workflow.
