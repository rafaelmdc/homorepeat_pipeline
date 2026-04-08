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

Install the local package first so the wrapper can write the final run manifest:

```bash
python3 -m pip install -e .
```

Build the runtime images expected by the Nextflow `docker` profile:

```bash
bash scripts/build_dev_containers.sh
```

The wrapper expects a taxonomy DB file at `runtime/cache/taxonomy/ncbi_taxonomy.sqlite` unless you override it with `HOMOREPEAT_TAXONOMY_DB`.
It also expects an accession list file, one assembly accession per line.

Example accession file:

```text
GCF_000001405.40
GCF_000001635.27
GCF_000005845.2
```

Comments and blank lines are allowed, and duplicate accession lines are ignored.

Run the pipeline in Docker mode:

```bash
HOMOREPEAT_PROFILE=docker \
bash scripts/run_pipeline.sh examples/accessions/my_accessions.txt
```

Useful wrapper environment variables:
- `HOMOREPEAT_PROFILE`: `docker` for container-backed Nextflow tasks
- `HOMOREPEAT_RUN_ID`: stable run name under `runs/`
- `HOMOREPEAT_RUN_ROOT`: override the full run root
- `HOMOREPEAT_OUTPUT_DIR`: override the publish directory
- `HOMOREPEAT_PARAMS_FILE`: path to a Nextflow params JSON file
- `HOMOREPEAT_ACCESSIONS_FILE`: alternative to passing the accessions file as the first positional argument
- `HOMOREPEAT_TAXONOMY_DB`: taxonomy SQLite path override
- `HOMOREPEAT_NXF_HOME`: Nextflow cache root override

Example with a fixed run ID and `-resume`:

```bash
HOMOREPEAT_PROFILE=docker \
HOMOREPEAT_RUN_ID=my_run \
bash scripts/run_pipeline.sh examples/accessions/my_accessions.txt -resume
```

The wrapper forwards any extra arguments after the accessions file directly to `nextflow run`.

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
HOMOREPEAT_PROFILE=docker \
bash scripts/run_pipeline.sh examples/accessions/my_accessions.txt \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend true
```

You can also change the repeat residues in the same way:

```bash
HOMOREPEAT_PROFILE=docker \
bash scripts/run_pipeline.sh examples/accessions/my_accessions.txt \
  --repeat_residues Q,N \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend true
```

`repeat_residues` is a comma-separated list of one-letter amino acid residue codes.

## Changing Settings

There are two supported ways to change pipeline settings.

Pass overrides directly after the accessions file:

```bash
HOMOREPEAT_PROFILE=docker \
bash scripts/run_pipeline.sh examples/accessions/my_accessions.txt \
  --batch_size 10 \
  --threshold_window_size 10 \
  --threshold_min_target_count 7 \
  --run_seed_extend true
```

Or put settings in a params JSON file and pass it through `HOMOREPEAT_PARAMS_FILE`:

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
HOMOREPEAT_PROFILE=docker \
HOMOREPEAT_PARAMS_FILE=path/to/params.json \
bash scripts/run_pipeline.sh examples/accessions/my_accessions.txt
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
- accession status ledgers in `publish/status/`
- the stable run manifest in `publish/manifest/run_manifest.json`
