# Operations

## Requirements

- Nextflow `25.10.4`
- an existing taxonomy database at `runtime/cache/taxonomy/ncbi_taxonomy.sqlite`, unless you override `--taxonomy_db`
- Docker and the repo runtime images for the `docker` profile
- a local Python environment with the repo package dependencies for the `local` profile

The canonical operator entrypoint is:

```bash
nextflow run .
```

There is no repo-specific wrapper around the main workflow.

## Build Runtime Images

Build the images expected by the `docker` profile:

```bash
bash scripts/build_dev_containers.sh
```

That produces:

- `homorepeat-acquisition:dev`
- `homorepeat-detection:dev`

## Quick Start

Run the checked-in smoke example in the default `raw` publish mode:

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

Run the same workflow in `merged` mode so SQLite and reports are produced:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/smoke_human_merged/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  -params-file examples/params/smoke_default.json \
  --run_id smoke_human_merged \
  --accessions_file examples/accessions/smoke_human.txt \
  --acquisition_publish_mode merged
```

## Profiles

| Profile | Execution model | Typical use |
| --- | --- | --- |
| `docker` | Local executor with pinned acquisition and detection containers | Standard operator path |
| `local` | Local executor on the host | Tests, debugging, or environments where you want to use host-installed tools |

## Common Parameters

| Parameter | Default | Notes |
| --- | --- | --- |
| `--run_id` | timestamped value | Names the run root under `runs/` unless `--run_root` is overridden |
| `--run_root` | `runs/<run_id>` | Root for published outputs and internal Nextflow state |
| `--work_dir` | `runs/<run_id>/internal/nextflow/work` | Put this on fast scratch for larger runs |
| `--acquisition_publish_mode` | `raw` | `raw` publishes the v2 table contract only; `merged` also builds SQLite and reports |
| `--repeat_residues` | `Q` | Comma-separated one-letter amino-acid codes |
| `--run_pure` | `true` | Enables contiguous-run detection |
| `--run_threshold` | `true` | Enables sliding-window density detection |
| `--run_seed_extend` | `false` | Enables seed-and-extend detection |
| `--pure_min_repeat_count` | `6` | Pure-method minimum tract length |
| `--threshold_window_size` | `8` | Threshold-method window size |
| `--threshold_min_target_count` | `6` | Threshold-method minimum target count per window |
| `--seed_extend_seed_window_size` | `8` | Seed window size |
| `--seed_extend_seed_min_target_count` | `6` | Seed minimum target count |
| `--seed_extend_extend_window_size` | `12` | Extend window size |
| `--seed_extend_extend_min_target_count` | `8` | Extend minimum target count |
| `--seed_extend_min_total_length` | `10` | Minimum final tract length |
| `--batch_size` | `10` | Planner target batch size |
| `--ncbi_api_key` | unset | Passed through to the NCBI Datasets CLI |
| `--ncbi_cache_dir` | unset | Optional persistent download cache |
| `--ncbi_dehydrated` | `false` | Use dehydrated NCBI package download mode |
| `--ncbi_rehydrate` | `false` | Rehydrate after download |

Checked-in parameter examples:

- `examples/params/smoke_default.json`
- `examples/params/multi_residue_qn.json`

## Published Output Layout

Every run publishes under `runs/<run_id>/publish/`.

Default v2 outputs:

- `publish/calls/`
- `publish/tables/`
- `publish/summaries/`
- `publish/metadata/`

Important files:

- `publish/calls/repeat_calls.tsv`
- `publish/calls/run_params.tsv`
- `publish/tables/genomes.tsv`
- `publish/tables/taxonomy.tsv`
- `publish/tables/matched_sequences.tsv`
- `publish/tables/matched_proteins.tsv`
- `publish/tables/repeat_call_codon_usage.tsv`
- `publish/tables/repeat_context.tsv`
- `publish/tables/download_manifest.tsv`
- `publish/tables/normalization_warnings.tsv`
- `publish/tables/accession_status.tsv`
- `publish/tables/accession_call_counts.tsv`
- `publish/summaries/status_summary.json`
- `publish/summaries/acquisition_validation.json`
- `publish/metadata/run_manifest.json`
- `publish/metadata/launch_metadata.json`
- `publish/metadata/nextflow/report.html`

`--acquisition_publish_mode merged` additionally publishes:

- `publish/database/homorepeat.sqlite`
- `publish/reports/`

The default v2 contract does not publish `publish/acquisition/`,
`publish/status/`, `publish/calls/finalized/`, `cds.fna`, or `proteins.faa`.
Those remain internal execution artifacts.

`run_manifest.json` is the authoritative place to determine:

- whether the run used `raw` or `merged` acquisition publishing
- which methods and residues were enabled
- which top-level artifacts were produced

## Failure Handling and Troubleshooting

Primary failure surface:

- native Nextflow exit status
- `publish/metadata/nextflow/report.html`

Supplemental recovery and diagnosis:

- `publish/tables/accession_status.tsv` and `publish/tables/accession_call_counts.tsv`
- `publish/summaries/status_summary.json`
- `publish/metadata/run_manifest.json` and `publish/metadata/launch_metadata.json`

Recommended operator workflow after a failed or partial run:

1. Check the Nextflow report and trace under `publish/metadata/nextflow/`.
2. If present, inspect `publish/summaries/status_summary.json`.
3. Use `publish/tables/accession_status.tsv` to find accession-level failures or no-call completions.
4. Use `-resume` when continuing the same run root.

## Focused Smoke Scripts

When you do not need a full pipeline run:

- `scripts/smoke_live_acquisition.sh`
- `scripts/smoke_live_detection.sh`

These are narrow live checks. They are useful for toolchain debugging, but they do not define the full published contract of `nextflow run .`.
