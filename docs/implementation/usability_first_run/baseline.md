# Phase 0 Baseline and Inventory

Date: 2026-04-27

This document records the first-run usability baseline for the taxonomy
auto-build work. It is a backfilled Phase 0 note because the taxonomy auto-build
slice was implemented before this inventory was written. The pre-change
evidence below comes from `HEAD` versions of the relevant files before the
working-tree implementation edits.

## Validation Run

Commands run on the current working tree after Phase 2 implementation started:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_pipeline_config
```

Results:

- `nextflow config .` passes.
- `tests.workflow.test_pipeline_config` passes: 3 tests.

Current config now exposes the intended taxonomy usability controls:

- `params.taxonomy_db`
- `params.taxonomy_cache_dir`
- `params.taxonomy_db_supplied`
- `params.taxonomy_auto_build`
- process label `taxonomy_build`

## Pre-Change Taxonomy Behavior

Evidence from pre-change `conf/base.config`:

```groovy
params {
  accessions_file = null
  taxonomy_db = params.taxonomy_db ?: "${projectDir}/runtime/cache/taxonomy/ncbi_taxonomy.sqlite"
}
```

Evidence from pre-change `workflows/acquisition_from_accessions.nf`:

```groovy
def accessionsFile = file(params.accessions_file, checkIfExists: true)
def taxonomyDb = file(params.taxonomy_db, checkIfExists: true)
```

Observed implication:

- The workflow always had a `params.taxonomy_db` value because the config filled
  in a default path.
- The acquisition workflow required that path to exist before any process could
  run.
- Because `checkIfExists: true` happened at workflow construction time, the
  workflow had no chance to build the default database itself.

## Pre-Change Docs Behavior

Evidence from pre-change `README.md`:

```text
The main Nextflow pipeline does not create the taxonomy database automatically.
Build it once before running, or pass an existing database with --taxonomy_db.
```

Observed implication:

- The docs correctly described the old behavior.
- The user-facing setup path required a manual taxonomy DB build before the
  first pipeline run.
- The common run examples included `--taxonomy_db
  runtime/cache/taxonomy/ncbi_taxonomy.sqlite`, which made the first command
  longer and implied users needed to understand the taxonomy cache before
  running a biological smoke test.

## First-Run Friction Inventory

### Missing default taxonomy DB

Pre-change behavior:

- A default path was assigned.
- The workflow tried to resolve that path with `checkIfExists: true`.
- If the file was missing, the run failed before acquisition or normalization.

Usability problem:

- A first-time user needed to know that `taxon-weaver build-db` had to be run
  before `nextflow run .`.
- The pipeline could not self-heal even though the acquisition image contained
  `taxon-weaver`.

Target behavior:

- If `--taxonomy_db` is omitted and the default cache is missing, build it
  automatically.

### Missing explicit taxonomy DB

Pre-change behavior:

- Missing explicit and missing default DBs both failed through the same
  `checkIfExists: true` path.

Usability problem:

- The workflow did not distinguish "user supplied a path that is wrong" from
  "default cache needs to be initialized".

Target behavior:

- Explicit `--taxonomy_db` paths remain strict and must already exist.
- Error message should say to pass an existing DB or omit `--taxonomy_db` to use
  the auto-built default cache.

### Missing Docker image

Pre-change behavior:

- Docker profile referenced local image tags:
  - `homorepeat-acquisition:dev`
  - `homorepeat-detection:dev`

Usability problem:

- A fresh user needed to build images locally.
- Missing image errors came from Docker/Nextflow rather than a HomoRepeat
  preflight.

Target behavior:

- Publish user-facing images to Docker Hub in a later phase.
- Keep local `:dev` images for development.

### Missing `--accessions_file`

Pre-change behavior:

```groovy
if( !params.accessions_file ) {
    error "params.accessions_file is required"
}
```

Usability problem:

- This is already a clear basic guard, but it could be improved later by
  pointing users to `examples/accessions/smoke_human.txt`.

Target behavior:

- Keep the hard failure.
- Later preflight phase can add a more helpful example path.

### Invalid `--repeat_residues`

Pre-change behavior:

- The detection workflow checks that `repeat_residues` is not empty.
- More detailed validation of one-letter amino-acid symbols is a Phase 5
  preflight concern.

Target behavior:

- Fail early with a short message if residue symbols are malformed.

## Phase 0 Decisions

- Treat taxonomy DB initialization as the first implementation slice because it
  blocks the shortest first-run command.
- Preserve explicit `--taxonomy_db` strictness.
- Do not solve Docker image publishing in the same slice.
- Keep manual taxonomy DB build documentation for controlled environments.
- Move detailed preflight/error improvements to Phase 5.
