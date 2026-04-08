# Operations

## Purpose

This is the minimal operator-facing guide for the pipeline product root.

Use it for:
- building local runtime images
- running the pipeline smoke path
- knowing where stable outputs land

## Standard entrypoints

Install the package locally so the wrapper can write the final run manifest:

```bash
python3 -m pip install -e .
```

Build the runtime images expected by the Nextflow `docker` profile:

```bash
bash scripts/build_dev_containers.sh
```

Run the checked-in pipeline smoke:

```bash
HOMOREPEAT_PROFILE=docker \
HOMOREPEAT_PARAMS_FILE=examples/params/smoke_default.json \
bash scripts/run_pipeline.sh examples/accessions/smoke_human.txt
```

## Focused smoke scripts

When you do not need a full pipeline run:
- `scripts/smoke_live_acquisition.sh`
- `scripts/smoke_live_detection.sh`

These are opt-in live checks. They are narrower than the full Nextflow smoke path.
They currently stage direct CLI detection outputs under `publish/detection/raw/` and finalized codon-linked outputs under `publish/detection/finalized/`.

## Runtime expectations

- taxonomy DB path defaults to `runtime/cache/taxonomy/ncbi_taxonomy.sqlite`
- the Nextflow `docker` profile expects `homorepeat-acquisition:dev` and `homorepeat-detection:dev`
- the wrapper host interpreter still needs `homorepeat` importable because it writes the run manifest after Nextflow finishes
- batch planning defaults to `params.batch_size = 25`
- task-level parallelism is controlled by Nextflow labels in `conf/base.config`

## Published outputs

Stable downstream outputs live under:
- `runs/<run_id>/publish/acquisition/`
- `runs/<run_id>/publish/detection/finalized/`
- `runs/<run_id>/publish/calls/`
- `runs/<run_id>/publish/status/`
- `runs/<run_id>/publish/database/sqlite/`
- `runs/<run_id>/publish/reports/`
- `runs/<run_id>/publish/manifest/run_manifest.json`

Operational note:
- `publish/detection/finalized/` contains method-specific finalized artifacts such as per-method call tables, run params, codon warnings, and codon-usage tables
- `publish/calls/` contains the canonical merged `repeat_calls.tsv` and `run_params.tsv` used downstream
- `publish/status/` contains the accession-level operational ledger in `accession_status.tsv`, the per-method/per-residue breakdown in `accession_call_counts.tsv`, and run-level counts in `status_summary.json`

Execution state lives under:
- `runs/<run_id>/internal/`

## Verified baseline

Verified on April 8, 2026:
- `bash scripts/build_dev_containers.sh`
- full live Nextflow smoke run through the `docker` profile on 5 real NCBI accessions with `batch_size=2`
- canonical outputs confirmed after the contract cleanup removing row-level `download_path`, `sequence_path`, `protein_path`, and `source_file`

Latest verified run:
- `runs/smoke_contract_cleanup_live`
