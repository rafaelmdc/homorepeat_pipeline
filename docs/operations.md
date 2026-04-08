# Operations

## Purpose

This is the minimal operator-facing guide for the pipeline product root.

Use it for:
- building local runtime images
- running the pipeline smoke path
- knowing where stable outputs land
- checking the supported runtime contract for this MVP

## Supported runtime

- supported Nextflow release: `25.10.4`
- canonical operator entrypoint: `nextflow run .`
- canonical publication model: DSL2 workflow `publish:` plus `output {}`
- canonical failure surface: native Nextflow task failure and `publish/metadata/nextflow/report.html`
- `publish/status/` remains a supplemental accession-level ledger when that reporting path completes

## Standard entrypoints

Build the runtime images expected by the Nextflow `docker` profile:

```bash
bash scripts/build_dev_containers.sh
```

Run the checked-in pipeline smoke:

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

Run the intentional failure probe:

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

Expected result:
- the run exits nonzero
- `report.html` shows the failed task
- `publish/metadata/run_manifest.json` reports `failed`

## Focused smoke scripts

When you do not need a full pipeline run:
- `scripts/smoke_live_acquisition.sh`
- `scripts/smoke_live_detection.sh`

These are opt-in live checks. They are narrower than the full Nextflow smoke path.
They do not define the canonical published output contract for full pipeline runs.

## Runtime expectations

- taxonomy DB path defaults to `runtime/cache/taxonomy/ncbi_taxonomy.sqlite`
- the Nextflow `docker` profile expects `homorepeat-acquisition:dev` and `homorepeat-detection:dev`
- the canonical operator entrypoint is `nextflow run .`
- the `local` profile still requires the repo CLIs and Python environment on the host; the `docker` profile keeps task execution inside the runtime images
- batch planning defaults to `params.batch_size = 10`
- task-level parallelism is controlled by Nextflow labels in `conf/base.config`
- for larger runs, prefer `--work_dir` on fast local scratch; if unset, Nextflow work data defaults to `runs/<run_id>/internal/nextflow/work`

## Published outputs

Stable downstream outputs live under:
- `runs/<run_id>/publish/acquisition/`
- `runs/<run_id>/publish/calls/`
- `runs/<run_id>/publish/calls/finalized/`
- `runs/<run_id>/publish/status/`
- `runs/<run_id>/publish/database/`
- `runs/<run_id>/publish/reports/`
- `runs/<run_id>/publish/metadata/`

Operational note:
- `publish/calls/finalized/` contains method-specific finalized artifacts such as per-method call tables, run params, codon warnings, and codon-usage tables, grouped by method, repeat residue, and batch
- `publish/calls/` contains the canonical merged `repeat_calls.tsv` and `run_params.tsv` used downstream
- `publish/status/` contains the accession-level operational ledger in `accession_status.tsv`, the per-method/per-residue breakdown in `accession_call_counts.tsv`, and run-level counts in `status_summary.json` when the reporting path completes
- `publish/metadata/` contains `run_manifest.json`, `launch_metadata.json`, and stable relative symlinks under `publish/metadata/nextflow/` pointing back to `internal/nextflow/`
- native Nextflow run status and `publish/metadata/nextflow/report.html` are the authoritative failure surface

Execution state lives under:
- `runs/<run_id>/internal/`
- `runs/<run_id>/internal/nextflow/` stores the live Nextflow logs and source diagnostics used to build the published metadata bundle

## Verified baseline

Verified on April 8, 2026:
- `bash scripts/build_dev_containers.sh`
- full live Nextflow smoke run through the `docker` profile on 5 real NCBI accessions with `batch_size=2`
- canonical outputs confirmed after the contract cleanup removing row-level `download_path`, `sequence_path`, `protein_path`, and `source_file`
- one-accession Docker smoke run confirmed the published layout under `publish/`, including `publish/metadata/nextflow/` symlinks and `publish/calls/finalized/`

Latest verified run:
- `runs/smoke_e2e_workflow_outputs_v3`
