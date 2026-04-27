# Phase 1 Taxonomy Auto-Build Design

Date: 2026-04-27

This document records the Phase 1 design decision for taxonomy database
auto-build. It should be read with [baseline.md](./baseline.md) and
[plan.md](./plan.md).

## Goal

Make the common first run simpler:

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt
```

That command should create or reuse the default NCBI taxonomy SQLite database
without requiring the user to understand `taxon-weaver` first.

## Required Behavior

| Case | Required behavior |
| --- | --- |
| user omits `--taxonomy_db`, default DB exists | reuse default DB |
| user omits `--taxonomy_db`, default DB missing | build default DB automatically |
| user passes `--taxonomy_db`, file exists | use that DB |
| user passes `--taxonomy_db`, file missing | fail with actionable message |
| user passes `--taxonomy_auto_build false`, default DB missing | fail with actionable message |

## Parameter Design

### `--taxonomy_db`

Effective path to the taxonomy SQLite database.

Default:

```text
runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

Design rule:

- If omitted, this is a pipeline-managed default cache path.
- If supplied explicitly, this is a user-managed input and must already exist.

### `--taxonomy_cache_dir`

Directory used for the auto-built default taxonomy artifacts.

Default:

```text
runtime/cache/taxonomy
```

This exists for two reasons:

- normal users get the same default path as before
- tests and advanced users can redirect the auto-build cache without touching
  the repository-level runtime cache

### `--taxonomy_auto_build`

Boolean flag controlling whether the default cache may be built automatically.

Default:

```text
true
```

Design rule:

- Applies only when `--taxonomy_db` was not explicitly supplied.
- If false and the default DB is missing, fail early.

### Internal `taxonomy_db_supplied`

Boolean computed before assigning the default taxonomy DB path.

Reason:

- Once `params.taxonomy_db` is filled with the default, workflow code can no
  longer distinguish a user-supplied DB from the default path.
- This distinction is required to preserve strict behavior for explicit paths
  while allowing auto-build for the default cache.

## Workflow Design

Add one process:

```text
modules/local/acquisition/build_taxonomy_db.nf
```

Process:

```text
BUILD_TAXONOMY_DB
```

Label:

```text
taxonomy_build
```

Outputs:

- `ncbi_taxonomy.sqlite`
- `taxdump.tar.gz`
- `ncbi_taxonomy_build.json`

Command:

```bash
taxon-weaver build-db \
  --download \
  --dump taxdump.tar.gz \
  --db ncbi_taxonomy.sqlite \
  --report-json ncbi_taxonomy_build.json
```

Publish behavior:

- copy outputs to `params.taxonomy_cache_dir`
- overwrite existing cache artifacts only when the build task runs

## Acquisition Workflow Decision

Replace the old unconditional existence check:

```groovy
def taxonomyDb = file(params.taxonomy_db, checkIfExists: true)
```

with decision logic:

```text
if effective taxonomy DB exists:
    use it
else if user supplied taxonomy DB or auto-build disabled:
    fail with actionable message
else:
    run BUILD_TAXONOMY_DB and feed its DB output to normalization
```

Important detail:

- The build process output should be converted to a single reusable channel for
  `NORMALIZE_CDS_BATCH`.
- Avoid introducing extra anonymous channel operators that increase DAG noise
  unnecessarily.

## Container/Profile Design

The taxonomy build needs `taxon-weaver`, so it belongs in the acquisition
runtime.

Docker profile mapping:

```groovy
withLabel: taxonomy_build {
  container = params.acquisition_container
}
```

Resource defaults:

```groovy
withLabel: taxonomy_build {
  cpus = 1
  memory = '4 GB'
  maxForks = 1
}
```

## Manifest Design

The existing `inputs.taxonomy_db` field should continue to record the effective
taxonomy DB path.

Add effective params for:

- `taxonomy_auto_build`
- `taxonomy_cache_dir`
- `taxonomy_db_supplied`

Reason:

- downstream review can tell whether the run used pipeline-managed default
  taxonomy cache behavior or an explicit user-managed DB path.

## Test Design

Add workflow tests for:

- missing default DB auto-builds into a temporary cache
- explicit missing `--taxonomy_db` fails and does not create the missing path
- existing publish-mode workflow tests still pass

Fake `taxon-weaver` behavior needed in tests:

- `build-db` writes:
  - fake `taxdump.tar.gz`
  - fake `ncbi_taxonomy.sqlite`
  - fake `ncbi_taxonomy_build.json`
- existing `build-info` and `inspect-lineage` fake behavior remains unchanged

Validation commands:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest \
  tests.workflow.test_pipeline_config \
  tests.workflow.test_publish_modes \
  tests.workflow.test_workflow_output_failures
git diff --check
```

## Documentation Design

Update active docs to say:

- default runs auto-build the default taxonomy DB when it is missing
- explicit `--taxonomy_db` paths must already exist
- manual `taxon-weaver build-db` remains available for controlled environments
- first-run commands should omit `--taxonomy_db`

Docs to update:

- `README.md`
- `docs/operations.md`
- `docs/background.md`
- `docs/contracts.md`
- `docs/README.md`
- `docs/containers.md`
- `docs/development.md`

## Deferred Decisions

These are intentionally outside Phase 1/2:

- Docker Hub namespace and image tag policy
- generated `publish/START_HERE.md`
- broader preflight CLI
- validation of malformed residue symbols
- whether taxonomy build metadata should also be copied into each run's
  `publish/metadata/`
