# Operations

## Purpose

This is the minimal operator-facing guide for the pipeline product root.

Use it for:
- building local runtime images
- running the pipeline smoke path
- knowing where stable outputs land

## Standard entrypoints

Build the pipeline images expected by the Nextflow `docker` profile:

```bash
cd pipeline && docker compose build pipeline-acquisition pipeline-detection
```

Run the checked-in pipeline smoke:

```bash
cd pipeline && \
HOMOREPEAT_PHASE4_PROFILE=docker \
HOMOREPEAT_PARAMS_FILE=examples/params/smoke_default.json \
bash scripts/run_phase4_pipeline.sh examples/accessions/smoke_human.txt
```

## Focused smoke scripts

When you do not need a full pipeline run:
- `scripts/smoke_live_acquisition.sh`
- `scripts/smoke_live_detection.sh`

These are opt-in live checks. They are narrower than the full Nextflow smoke path.

## Runtime expectations

- taxonomy DB path defaults to `runtime/cache/taxonomy/ncbi_taxonomy.sqlite`
- the Nextflow `docker` profile expects `homorepeat-acquisition:dev` and `homorepeat-detection:dev`
- the wrapper host interpreter still needs `homorepeat` importable because it writes the run manifest after Nextflow finishes

## Published outputs

Stable downstream outputs live under:
- `runs/<run_id>/publish/acquisition/`
- `runs/<run_id>/publish/calls/`
- `runs/<run_id>/publish/database/sqlite/`
- `runs/<run_id>/publish/reports/`
- `runs/<run_id>/publish/manifest/run_manifest.json`

Execution state lives under:
- `runs/<run_id>/internal/`

## Verified baseline

Verified on April 6, 2026:
- `cd pipeline && docker compose build pipeline-acquisition pipeline-detection`
- `cd web && docker compose up web postgres`
- full Nextflow smoke run through the `docker` profile on `examples/accessions/smoke_human.txt`

Latest verified run:
- `runs/phase4_pipeline_2026-04-06_12-03-46Z`
