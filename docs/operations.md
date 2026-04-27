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
- internet access to pull the published HomoRepeat Docker images on first use
- a taxonomy database, which the default run can build automatically if missing

The main entrypoint is:

```bash
nextflow run .
```

There is no project-specific wrapper script.

## Which Command Should I Use?

| Situation | Command style |
| --- | --- |
| First check that inputs are valid | Add `--dry_run_inputs true` |
| First real smoke run | `nextflow run . -profile docker --accessions_file examples/accessions/smoke_human.txt` |
| A run you want to keep and resume | Set `NXF_HOME`, `-log`, and `--run_id` |
| You changed code or Dockerfiles | Build dev images and use `-profile docker_dev` |
| You need SQLite and report files | Add `--acquisition_publish_mode merged` |

## Runtime Images

The normal user profile is:

```bash
-profile docker
```

It uses published Docker Hub images. Docker pulls them automatically if they are
not already on your machine:

- `rafaelmdc/homorepeat-acquisition:0.1.0`
- `rafaelmdc/homorepeat-detection:0.1.0`

Quick checks:

```bash
docker run --rm rafaelmdc/homorepeat-acquisition:0.1.0 taxon-weaver --help
docker run --rm rafaelmdc/homorepeat-acquisition:0.1.0 datasets version
docker run --rm rafaelmdc/homorepeat-detection:0.1.0 python --version
```

Developers who are changing code can build local `:dev` images and run with
`-profile docker_dev`. See [Containers](./containers.md) for that workflow.

## Taxonomy Database

The taxonomy database is required for lineage information in `taxonomy.tsv`.

If you do not set `--taxonomy_db`, the pipeline uses this default path:

```text
runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

If that default file is missing, the pipeline builds it automatically with
`taxon-weaver build-db` and reuses it on later runs.

If you pass `--taxonomy_db /path/to/db.sqlite`, that file must already exist.
Explicit taxonomy DB paths are treated as user-managed inputs.

Manual build remains available for controlled environments:

```bash
mkdir -p runtime/cache/taxonomy

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$PWD":/work \
  -w /work \
  rafaelmdc/homorepeat-acquisition:0.1.0 \
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
  rafaelmdc/homorepeat-acquisition:0.1.0 \
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

Validate the checked-in human smoke example without downloading data:

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt \
  --dry_run_inputs true
```

Expected dry-run output includes:

```text
HomoRepeat input dry run passed.
Usable accessions: 1
Repeat residues: Q
```

If the default taxonomy database is absent, the dry run says `will_auto_build`.
That means the real run will build the default cache.

This is the smallest checked-in run:

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt
```

That writes results under a timestamped folder in `runs/`.

After it finishes, open:

```text
runs/<run_id>/publish/START_HERE.md
```

For a named, resumable smoke run:

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

Named-run result folder:

```text
runs/smoke_human/publish/
```

## Typical Run

Run `Q` and `N` repeats with the default `pure` and `threshold` methods:

Preflight first:

```bash
nextflow run . \
  -profile docker \
  --accessions_file inputs/my_accessions.txt \
  --repeat_residues Q,N \
  --dry_run_inputs true
```

Then run:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/my_qn_run/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id my_qn_run \
  --accessions_file inputs/my_accessions.txt \
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
  START_HERE.md
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
| `START_HERE.md` | Run-specific guide with the key settings and first files to inspect |
| `calls/repeat_calls.tsv` | Main repeat-call table |
| `tables/repeat_context.tsv` | Flanking context around calls |
| `tables/matched_proteins.tsv` | Protein sequences for called repeats |
| `tables/matched_sequences.tsv` | CDS nucleotide sequences for called repeats |
| `tables/repeat_call_codon_usage.tsv` | Codon usage for validated calls |
| `tables/accession_status.tsv` | Per-accession success, failure, or no-call status |
| `tables/accession_call_counts.tsv` | Number of calls per accession |
| `summaries/status_summary.json` | Quick run-level status |
| `metadata/nextflow/report.html` | Runtime report for debugging |

Recommended inspection order:

1. Open `START_HERE.md`.
2. Open `calls/repeat_calls.tsv` for the calls.
3. Open `tables/accession_status.tsv` to check whether any accession failed.
4. Open `tables/accession_call_counts.tsv` to identify successful no-call accessions.
5. Use `metadata/nextflow/report.html` only when diagnosing runtime behavior.

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
| `--dry_run_inputs` | `false` | Validate inputs and settings, then stop before downloading data or running detection |
| `--taxonomy_db` | `runtime/cache/taxonomy/ncbi_taxonomy.sqlite` | Taxonomy SQLite database to use; default path is auto-built if missing |
| `--taxonomy_auto_build` | `true` | Build the default taxonomy DB when missing and `--taxonomy_db` was not explicitly supplied |
| `--taxonomy_cache_dir` | `runtime/cache/taxonomy` | Cache directory for the auto-built taxonomy DB |
| `--dockerhub_namespace` | `rafaelmdc` | Docker Hub namespace used by the default `docker` profile |
| `--container_tag` | `0.1.0` | Published image tag used by the default `docker` profile |
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

### Error Matrix

| Error text | Likely cause | Next action |
| --- | --- | --- |
| `params.accessions_file is required` | No accession list was supplied | Add `--accessions_file path/to/accessions.txt` |
| `accessions file not found` | The supplied path is wrong or not visible from the launch directory | Check the path and rerun `--dry_run_inputs true` |
| `accessions file has no usable accession lines` | The file is empty after ignoring blanks and `#` comments | Add one NCBI assembly accession per line |
| `params.repeat_residues contains invalid residue code` | A repeat residue is not a standard one-letter amino-acid code | Use values such as `--repeat_residues Q,N` |
| `taxonomy database not found` | An explicit `--taxonomy_db` path is missing, or auto-build is disabled | Use an existing DB path, or omit `--taxonomy_db` for default auto-build |
| `Cannot pull image` or `pull access denied` | Docker cannot reach or pull the published runtime image | Check Docker Hub access and Docker daemon status |
| `No assembly summary records were returned` | NCBI could not resolve the requested accession | Confirm the accession in NCBI Assembly or Datasets |
| `Batch ... produced no normalized CDS sequences` | The downloaded package lacks usable annotated CDS records | Check `tables/accession_status.tsv` and try a current annotated assembly |

For input-only validation, run the same command with:

```bash
--dry_run_inputs true
```

Dry runs still create a small `publish/` folder with metadata and
`START_HERE.md`, but they do not download NCBI data or create call tables.

### Explicit taxonomy database missing

Symptom:

```text
taxonomy database not found
```

or an error that the path passed with `--taxonomy_db` does not exist.

Fix: pass an existing `--taxonomy_db` path, or omit `--taxonomy_db` and let the
pipeline build the default cache automatically.

### Accessions file has no usable accessions

Symptom:

```text
accessions file has no usable accession lines
```

Fix: add one NCBI assembly accession per line. Blank lines and lines beginning
with `#` are ignored.

Example:

```text
GCF_000001405.40
GCF_000001635.27
```

### Invalid repeat residues

Symptom:

```text
params.repeat_residues contains invalid residue code
```

Fix: use comma-separated standard one-letter amino-acid codes, such as:

```bash
--repeat_residues Q,N
```

### Docker image pull or local image missing

Symptom: Docker or Nextflow says it cannot pull
`rafaelmdc/homorepeat-acquisition:0.1.0` or
`rafaelmdc/homorepeat-detection:0.1.0`.

Fix: check that Docker is running and that the machine can access Docker Hub.

If you are intentionally using local development images, build them and use the
development profile:

```bash
bash scripts/build_dev_containers.sh
nextflow run . -profile docker_dev --accessions_file examples/accessions/smoke_human.txt
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
