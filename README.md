# HomoRepeat

HomoRepeat is a Nextflow pipeline for homorepeat acquisition, detection, codon-aware finalization, SQLite assembly, and downstream reporting.

Version `0.1` is the first release-focused rebuild of the project. It is scoped to:
- acquisition from assembly accession lists
- taxonomy-aware normalization
- three homorepeat detection strategies: `pure`, `threshold`, and optional `seed_extend`
- configurable repeat residues
- canonical flat-file outputs plus a SQLite database
- reproducible reporting artifacts under one run root

The workflow orchestration lives in Nextflow. The scientific logic lives in package-backed Python CLIs under `src/homorepeat/`.

## Version 0.1 Scope

This release is intended to be a usable, reproducible MVP rather than a broad platform release.

Included in `0.1`:
- accession-driven runs through `nextflow run .`
- `docker` and `local` profiles
- NCBI-backed acquisition using the runtime containers
- merged canonical outputs under `runs/<run_id>/publish/`
- run metadata and published Nextflow diagnostics

Not included in `0.1`:
- web applications or interactive front ends
- domain enrichment or annotation-heavy downstream biology
- broad compatibility across arbitrary Nextflow releases

## Requirements

- Nextflow `25.10.4`
- Docker for the `docker` profile
- the runtime images built from this repo
- a taxonomy database at `runtime/cache/taxonomy/ncbi_taxonomy.sqlite`, unless overridden with `--taxonomy_db`

The repo pins the supported Nextflow version in [nextflow.config](./nextflow.config).

## Quick Start

Build the runtime images expected by the `docker` profile:

```bash
bash scripts/build_dev_containers.sh
```

Create an accession file with one assembly accession per line:

```text
GCF_000001405.40
GCF_000001635.27
GCF_000005845.2
```

Comments and blank lines are allowed. Duplicate accession lines are ignored.

Run the pipeline:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id my_run \
  --accessions_file examples/accessions/my_accessions.txt
```

The canonical operator interface is `nextflow run .`. There is no repo-specific wrapper script.

## Core Concepts

The pipeline is organized around four stages:

1. Acquisition
2. Detection
3. Database assembly
4. Reporting

Scientific behavior is implemented in Python. Nextflow is responsible for:
- orchestration
- task execution
- profiles
- caching and resume
- resource settings
- publication of run outputs

## Detection Methods

Version `0.1` exposes three method toggles:
- `run_pure`
- `run_threshold`
- `run_seed_extend`

Current defaults:
- `run_pure = true`
- `run_threshold = true`
- `run_seed_extend = false`

That means the default run already executes `pure` and `threshold`.

To run all three methods:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id my_run \
  --accessions_file examples/accessions/my_accessions.txt \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend true
```

To target multiple residues:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id my_run \
  --accessions_file examples/accessions/my_accessions.txt \
  --repeat_residues Q,N \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend true
```

`repeat_residues` is a comma-separated list of one-letter amino-acid residue codes.

## Configuration

The supported configuration paths are:
- direct Nextflow parameter overrides
- a JSON params file passed through `-params-file`

Direct override example:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id my_run \
  --accessions_file examples/accessions/my_accessions.txt \
  --batch_size 10 \
  --threshold_window_size 10 \
  --threshold_min_target_count 7 \
  --run_seed_extend true
```

Params-file example:

```json
{
  "repeat_residues": "Q,N",
  "run_pure": true,
  "pure_min_repeat_count": 6,
  "run_threshold": true,
  "threshold_window_size": 8,
  "threshold_min_target_count": 6,
  "run_seed_extend": true,
  "seed_extend_seed_window_size": 8,
  "seed_extend_seed_min_target_count": 6,
  "seed_extend_extend_window_size": 12,
  "seed_extend_extend_min_target_count": 8,
  "seed_extend_min_total_length": 10,
  "batch_size": 10
}
```

Run with that file:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  -params-file path/to/params.json \
  --run_id my_run \
  --accessions_file examples/accessions/my_accessions.txt
```

Checked-in examples:
- `examples/params/smoke_default.json`
- `examples/params/multi_residue_qn.json`

### Supported Settings

Detection and biology:
- `repeat_residues`
- `run_pure`
- `pure_min_repeat_count`
- `run_threshold`
- `threshold_window_size`
- `threshold_min_target_count`
- `run_seed_extend`
- `seed_extend_seed_window_size`
- `seed_extend_seed_min_target_count`
- `seed_extend_extend_window_size`
- `seed_extend_extend_min_target_count`
- `seed_extend_min_total_length`

Acquisition and batching:
- `batch_size`
- `ncbi_api_key`
- `ncbi_cache_dir`
- `ncbi_dehydrated`
- `ncbi_rehydrate`
- `ncbi_rehydrate_workers`

Runtime and paths:
- `accessions_file`
- `taxonomy_db`
- `run_id`
- `run_root`
- `output_dir`
- `python_bin`
- `datasets_bin`
- `taxon_weaver_bin`
- `acquisition_container`
- `detection_container`

Method parameter meanings:
- `pure_min_repeat_count`: minimum contiguous tract length for `pure`
- `threshold_window_size`: sliding-window size for `threshold`
- `threshold_min_target_count`: minimum target count inside each threshold window
- `seed_extend_seed_window_size`: seed window size for `seed_extend`
- `seed_extend_seed_min_target_count`: minimum target count required for a seed window
- `seed_extend_extend_window_size`: extension window size for `seed_extend`
- `seed_extend_extend_min_target_count`: minimum target count required while extending
- `seed_extend_min_total_length`: minimum final tract length after seed-and-extend merging

## Run Layout

By default:
- `run_root` is `runs/<run_id>`
- `output_dir` is `runs/<run_id>/publish`
- `workDir` is `runs/<run_id>/internal/nextflow/work`

Published outputs live under `runs/<run_id>/publish/`:
- `publish/acquisition/`
- `publish/calls/`
- `publish/calls/finalized/<method>/<repeat_residue>/<batch_id>/`
- `publish/database/`
- `publish/reports/`
- `publish/status/`
- `publish/metadata/`

Important published artifacts:
- `publish/calls/repeat_calls.tsv`
- `publish/calls/run_params.tsv`
- `publish/database/homorepeat.sqlite`
- `publish/metadata/run_manifest.json`
- `publish/metadata/launch_metadata.json`

`publish/metadata/nextflow/` exposes stable relative symlinks back to the live files under `runs/<run_id>/internal/nextflow/`.

## Failure Behavior

Version `0.1` uses native Nextflow task failure semantics.

That means:
- a real failed task should appear as failed in the Nextflow report
- the run should exit nonzero on failure
- `publish/metadata/nextflow/report.html` is the authoritative run-level failure surface
- `publish/status/` is supplemental and may be absent or partial on failed runs

DSL2 workflow `publish:` plus `output {}` is the canonical publication model for the repo.

## Smoke Commands

Success smoke:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/smoke_human/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  -params-file examples/params/smoke_default.json \
  --run_id smoke_human \
  --accessions_file examples/accessions/smoke_human.txt
```

Intentional failure probe:

```bash
cat > /tmp/homorepeat_failure_probe.txt <<'EOF'
GCF_000001405.40
GCF_BOGUS_FAILURE_TEST.1
EOF

NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/failure_probe/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id failure_probe \
  --batch_size 1 \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend false \
  --accessions_file /tmp/homorepeat_failure_probe.txt
```

Expected failure-probe behavior:
- `nextflow run` exits nonzero
- `runs/failure_probe/internal/nextflow/report.html` shows the failed task
- `runs/failure_probe/publish/metadata/run_manifest.json` reports `failed`

## Repository Layout

Main workflow paths:
- `main.nf`
- `nextflow.config`
- `conf/`
- `workflows/`
- `modules/`

Scientific implementation:
- `src/homorepeat/`

Supporting material:
- `examples/`
- `containers/`
- `scripts/`
- `tests/`
- `docs/`
- `runtime/`
- `runs/`

## Development

The `docker` profile is the primary operator path.

The `local` profile is mainly for:
- tests
- offline development
- debugging without container execution

Useful checks:

```bash
nextflow config .
PYTHONPATH=src python3 -m unittest
```

## Documentation

For more detail, see:
- [docs/operations.md](./docs/operations.md)
- [docs/methods.md](./docs/methods.md)
- [docs/architecture.md](./docs/architecture.md)
- [docs/contracts.md](./docs/contracts.md)

## License

See [LICENSE](./LICENSE).
