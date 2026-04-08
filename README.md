# HomoRepeat Pipeline

This product root owns the Nextflow workflow, package-backed CLIs, runtime images, tests, examples, runtime caches, and published run artifacts.

Key paths:
- `main.nf`
- `nextflow.config`
- `conf/`
- `modules/`
- `workflows/`
- `scripts/`
- `src/homorepeat/`
- `tests/`
- `examples/`
- `runtime/`
- `runs/`

## Docker Run

Build the runtime images expected by the Nextflow `docker` profile:

```bash
bash scripts/build_dev_containers.sh
```

The pipeline expects an accession list file, one assembly accession per line.
The default taxonomy DB path is `runtime/cache/taxonomy/ncbi_taxonomy.sqlite`.
Override it with `--taxonomy_db` when needed.

Example accession file:

```text
GCF_000001405.40
GCF_000001635.27
GCF_000005845.2
```

Comments and blank lines are allowed, and duplicate accession lines are ignored.

Run the pipeline in Docker mode:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id my_run \
  --accessions_file examples/accessions/my_accessions.txt
```

Recommended standard flags:
- `-profile docker`
- `--run_id my_run`
- `--accessions_file path/to/accessions.txt`
- `--taxonomy_db path/to/ncbi_taxonomy.sqlite` when not using the default
- `-output-dir path/to/publish` when you want a Nextflow-native publish override
- `-params-file path/to/params.json`
- `-resume`

By default:
- `run_root` lands under the repo root at `runs/<run_id>`
- `output_dir` lands under the repo root at `runs/<run_id>/publish`
- `workDir` lands under the repo root at `runs/<run_id>/internal/nextflow/work`

Example with `-resume` and an explicit Nextflow log path:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/my_run/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id my_run \
  --accessions_file examples/accessions/my_accessions.txt \
  -resume
```

## Choosing Methods

The detection workflow exposes three method toggles:
- `run_pure`
- `run_threshold`
- `run_seed_extend`

Current defaults are:
- `run_pure = true`
- `run_threshold = true`
- `run_seed_extend = false`

That means the default pipeline run already executes `pure` and `threshold`.
To run all three methods, enable `run_seed_extend` as well.

Example using direct Nextflow param overrides:

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

You can also change the repeat residues in the same way:

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

`repeat_residues` is a comma-separated list of one-letter amino acid residue codes.

## Changing Settings

There are two supported ways to change pipeline settings.

Pass overrides directly to `nextflow run`:

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

Or put settings in a params JSON file and pass it through `-params-file`:

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

See `examples/params/smoke_default.json` and `examples/params/multi_residue_qn.json` for checked-in examples.

## Available Settings

The current pipeline params exposed in `conf/base.config` are:

Detection and biology settings:
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

Acquisition and batching settings:
- `batch_size`
- `ncbi_api_key`
- `ncbi_cache_dir`
- `ncbi_dehydrated`
- `ncbi_rehydrate`
- `ncbi_rehydrate_workers`

Runtime and tool-path settings:
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

What the method-specific settings mean:
- `pure_min_repeat_count`: minimum contiguous tract length for the `pure` method
- `threshold_window_size`: sliding window size for the `threshold` method
- `threshold_min_target_count`: minimum number of target residues required inside each threshold window
- `seed_extend_seed_window_size`: seed window size for the `seed_extend` method
- `seed_extend_seed_min_target_count`: minimum target residues required for a seed window
- `seed_extend_extend_window_size`: extension window size for `seed_extend`
- `seed_extend_extend_min_target_count`: minimum target residues required while extending
- `seed_extend_min_total_length`: minimum final tract length after seed-and-extend merging

Published run artifacts live under `runs/<run_id>/publish/`, including:
- canonical acquisition outputs in `publish/acquisition/`
- canonical merged calls in `publish/calls/`
- method-level finalized call bundles in `publish/calls/finalized/<method>/<repeat_residue>/<batch_id>/`
- SQLite outputs in `publish/database/`
- summaries and ECharts assets in `publish/reports/`
- accession status ledgers in `publish/status/`
- run metadata in `publish/metadata/`
- the stable run manifest in `publish/metadata/run_manifest.json`

Metadata note:
- `publish/metadata/nextflow/` exposes stable relative symlinks to the live files under `runs/<run_id>/internal/nextflow/`
- native Nextflow failure state is the run-level source of truth; `publish/status/` remains a supplemental accession-level ledger when it is produced
