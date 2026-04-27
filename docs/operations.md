# Operations

This guide is the practical runbook for using HomoRepeat. It assumes you want
to run the pipeline and inspect the biological output tables, not change the
code.

## Before You Run

You need:

- Nextflow `25.10.4`
- Docker
- internet access to NCBI
- one accession-list text file
- the HomoRepeat Docker images
- an existing taxonomy database

The main entrypoint is:

```bash
nextflow run .
```

There is no project-specific wrapper script.

## Build Runtime Images

Build the images expected by the `docker` profile:

```bash
bash scripts/build_dev_containers.sh
```

That produces:

- `homorepeat-acquisition:dev`
- `homorepeat-detection:dev`

Quick checks:

```bash
docker run --rm homorepeat-acquisition:dev taxon-weaver --help
docker run --rm homorepeat-acquisition:dev datasets version
docker run --rm homorepeat-detection:dev python --version
```

## Taxonomy Database

The taxonomy database is required for lineage information in `taxonomy.tsv`.

**The pipeline does not auto-create this database during `nextflow run .`.** It
expects an existing SQLite file at the value of `--taxonomy_db`. If you do not
set `--taxonomy_db`, the default path is:

```text
runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

Build it once with the acquisition container:

```bash
mkdir -p runtime/cache/taxonomy

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$PWD":/work \
  -w /work \
  homorepeat-acquisition:dev \
  taxon-weaver build-db \
    --download \
    --dump runtime/cache/taxonomy/taxdump.tar.gz \
    --db runtime/cache/taxonomy/ncbi_taxonomy.sqlite \
    --report-json runtime/cache/taxonomy/ncbi_taxonomy_build.json
```

Confirm it:

```bash
ls -lh runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

Read build metadata:

```bash
docker run --rm \
  -v "$PWD":/work \
  -w /work \
  homorepeat-acquisition:dev \
  taxon-weaver build-info \
    --db runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

If you already have a `taxon-weaver` SQLite database elsewhere, use it directly:

```bash
--taxonomy_db /path/to/ncbi_taxonomy.sqlite
```

## Prepare Accessions

Use NCBI assembly accessions, one per line:

```bash
mkdir -p inputs

printf '%s\n' \
  GCF_000001405.40 \
  GCF_000001635.27 \
  > inputs/my_accessions.txt
```

Rules:

- blank lines are ignored
- lines beginning with `#` are ignored
- duplicate lines are removed while preserving order
- non-RefSeq accessions may be resolved to a paired downloadable RefSeq
  accession when appropriate

## Quick Smoke Run

This is the smallest checked-in run:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/smoke_human/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  -params-file examples/params/smoke_default.json \
  --run_id smoke_human \
  --accessions_file examples/accessions/smoke_human.txt \
  --taxonomy_db runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

Expected result folder:

```text
runs/smoke_human/publish/
```

## Typical Run

Run `Q` and `N` repeats with the default `pure` and `threshold` methods:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/my_qn_run/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id my_qn_run \
  --accessions_file inputs/my_accessions.txt \
  --taxonomy_db runtime/cache/taxonomy/ncbi_taxonomy.sqlite \
  --repeat_residues Q,N \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend false
```

Run all three methods:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/my_all_methods/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id my_all_methods \
  --accessions_file inputs/my_accessions.txt \
  --taxonomy_db runtime/cache/taxonomy/ncbi_taxonomy.sqlite \
  --repeat_residues Q,N \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend true
```

Run with SQLite and HTML reports:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/my_qn_merged/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id my_qn_merged \
  --accessions_file inputs/my_accessions.txt \
  --taxonomy_db runtime/cache/taxonomy/ncbi_taxonomy.sqlite \
  --repeat_residues Q,N \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend false \
  --acquisition_publish_mode merged
```

Use an NCBI API key when available:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/my_qn_api/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id my_qn_api \
  --accessions_file inputs/my_accessions.txt \
  --taxonomy_db runtime/cache/taxonomy/ncbi_taxonomy.sqlite \
  --repeat_residues Q,N \
  --ncbi_api_key "$NCBI_API_KEY"
```

## Resume An Interrupted Run

Use the same command, same `--run_id`, same `--run_root` if you set one, and add
`-resume`:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/my_qn_run/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id my_qn_run \
  --accessions_file inputs/my_accessions.txt \
  --taxonomy_db runtime/cache/taxonomy/ncbi_taxonomy.sqlite \
  --repeat_residues Q,N \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend false \
  -resume
```

## Published Output Layout

Every run publishes under:

```text
runs/<run_id>/publish/
```

Default v2 outputs:

```text
publish/
  calls/
    repeat_calls.tsv
    run_params.tsv
  tables/
    genomes.tsv
    taxonomy.tsv
    matched_sequences.tsv
    matched_proteins.tsv
    repeat_call_codon_usage.tsv
    repeat_context.tsv
    download_manifest.tsv
    normalization_warnings.tsv
    accession_status.tsv
    accession_call_counts.tsv
  summaries/
    status_summary.json
    acquisition_validation.json
  metadata/
    launch_metadata.json
    run_manifest.json
    nextflow/
```

First files to open:

| File | Use |
| --- | --- |
| `calls/repeat_calls.tsv` | Main repeat-call table |
| `tables/repeat_context.tsv` | Flanking context around calls |
| `tables/matched_proteins.tsv` | Protein sequences for called repeats |
| `tables/matched_sequences.tsv` | CDS nucleotide sequences for called repeats |
| `tables/repeat_call_codon_usage.tsv` | Codon usage for validated calls |
| `tables/accession_status.tsv` | Per-accession success, failure, or no-call status |
| `tables/accession_call_counts.tsv` | Number of calls per accession |
| `summaries/status_summary.json` | Quick run-level status |
| `metadata/nextflow/report.html` | Runtime report for debugging |

`matched_sequences.tsv` and `matched_proteins.tsv` include the retained
sequence bodies. Broad public `cds.fna` and `proteins.faa` files are not part of
the default output contract.

`--acquisition_publish_mode merged` additionally publishes:

- `publish/database/homorepeat.sqlite`
- `publish/database/sqlite_validation.json`
- `publish/reports/*`

## Common Parameters

| Parameter | Default | Notes |
| --- | --- | --- |
| `--run_id` | timestamped value | Names the run root under `runs/` unless `--run_root` is overridden |
| `--run_root` | `runs/<run_id>` | Root for published outputs and internal Nextflow state |
| `--work_dir` | `runs/<run_id>/internal/nextflow/work` | Put this on fast scratch for larger runs |
| `--taxonomy_db` | `runtime/cache/taxonomy/ncbi_taxonomy.sqlite` | Must already exist |
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

For CPU, memory, and concurrency controls such as `-qs` and
`-process.withLabel:<label>.maxForks`, see [Scale Guide](./scale_guide.md).

## Troubleshooting

### Taxonomy database missing

Symptom:

```text
Path value cannot be null
```

or an error that `runtime/cache/taxonomy/ncbi_taxonomy.sqlite` does not exist.

Fix: build the taxonomy database or pass a valid `--taxonomy_db` path.

### Docker image missing

Symptom: Nextflow says it cannot find `homorepeat-acquisition:dev` or
`homorepeat-detection:dev`.

Fix:

```bash
bash scripts/build_dev_containers.sh
```

### NCBI download problems

Check:

- internet access
- whether NCBI is rate-limiting your connection
- whether using `--ncbi_api_key "$NCBI_API_KEY"` helps
- `publish/metadata/nextflow/report.html`
- `publish/tables/accession_status.tsv`, if it was produced

### Run succeeded but there are no calls

This can be a valid biological result. Check:

- `tables/accession_status.tsv`
- `tables/accession_call_counts.tsv`
- `calls/run_params.tsv`
- whether you searched the intended residues with `--repeat_residues`

### Failed or partial run

Recommended order:

1. Open `publish/metadata/nextflow/report.html` if it exists.
2. Check `publish/summaries/status_summary.json` if it exists.
3. Check `publish/tables/accession_status.tsv` if it exists.
4. Resume with `-resume` after fixing the cause.

## Focused Smoke Scripts

When you do not need a full pipeline run:

- `scripts/smoke_live_acquisition.sh`
- `scripts/smoke_live_detection.sh`

These are narrow live checks for toolchain debugging. They do not define the
full published contract of `nextflow run .`.
