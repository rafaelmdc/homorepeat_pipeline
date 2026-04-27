# First-Run Usability Implementation Plan

Date: 2026-04-27

This is an exploratory plan for making HomoRepeat easy to run for a new user,
especially a biologist who has not used this repository before. It deliberately
does not prescribe one large refactor. The goal is to remove first-run friction
in small, reviewable slices while keeping the scientific outputs and v2 publish
contract stable.

Implementation status:

- Phase 0 baseline is recorded in [baseline.md](./baseline.md).
- Phase 1 taxonomy auto-build design is recorded in
  [taxonomy_auto_build_design.md](./taxonomy_auto_build_design.md).
- Phase 2 taxonomy auto-build has been started in this branch.
- Phase 3 README and operations simplification has been completed in this
  branch.
- Phase 4 generated `START_HERE.md` has been started in this branch.
- Docker Hub image publishing remains planned but is not implemented here
  because the Docker Hub namespace and tag policy still need a project decision.

## Problem Statement

The current workflow is usable by someone who already understands Nextflow,
Docker, local caches, and `taxon-weaver`, but it has several points of friction
for a first-time biological user:

- the taxonomy database must currently exist before the workflow can normalize
  accessions
- the docs explain how to build that database, but the run command still feels
  like a multi-step informatics procedure
- users must know which files to inspect after a run
- error messages can expose Nextflow or internal details before giving a clear
  biological/operator action
- `nextflow run .` is the canonical entrypoint, but the simplest successful
  command still requires too much prior knowledge

The desired end state is:

```bash
nextflow run . -profile docker --accessions_file inputs/accessions.txt
```

For a default Docker run, that command should be enough to:

- use the default `Q` repeat settings
- create or reuse the taxonomy database
- place all outputs under a predictable `runs/<run_id>/publish/` folder
- leave clear status and troubleshooting artifacts
- tell the user what to open next

## Non-Goals

- Do not change the v2 output contract unless a usability improvement truly
  requires it.
- Do not add a separate wrapper as the only supported path unless the team
  explicitly decides to move away from `nextflow run .`.
- Do not hide failures. Make them clearer and more actionable.
- Do not add new external dependencies unless they remove substantial user
  friction.
- Do not broaden the scientific scope into domain enrichment, interpretation, or
  non-accession input modes in this plan.

## Design Principles

- The shortest command should do the correct default thing.
- Manual setup should become optional, not mandatory.
- Defaults should be reproducible and visible in `run_manifest.json`.
- Any long download/build step should be cached and resumable.
- If a user supplies an explicit path, respect it and fail clearly if it is
  invalid.
- Keep code changes narrow: one usability issue per implementation slice.
- Keep docs aligned with actual runtime behavior in the same PR as the change.

## Current Friction Points

### Taxonomy database setup

Current behavior:

- `conf/base.config` defaults `params.taxonomy_db` to
  `runtime/cache/taxonomy/ncbi_taxonomy.sqlite`.
- `workflows/acquisition_from_accessions.nf` calls
  `file(params.taxonomy_db, checkIfExists: true)`.
- If the default file is missing, the workflow fails before a process can build
  it.

Desired behavior:

- If the user does not specify `--taxonomy_db` and the default database is
  missing, the pipeline builds it automatically with `taxon-weaver build-db`.
- If the user specifies `--taxonomy_db /some/path.sqlite`, the pipeline treats
  that as an explicit input and fails clearly if the file is missing.
- The auto-built database is cached at the default path and reused on future
  runs.

### First command complexity

Current behavior:

- Recommended commands include `NXF_HOME`, `-log`, `--run_id`,
  `--taxonomy_db`, and sometimes `-params-file`.
- These are useful for reproducibility but make the first command visually
  heavy.

Desired behavior:

- The README starts with the shortest useful command.
- Advanced run hygiene, such as explicit `NXF_HOME`, `-log`, and stable
  `--run_id`, remains documented under "recommended production run".

### Runtime image availability

Current behavior:

- The Docker profile uses local development images:
  - `homorepeat-acquisition:dev`
  - `homorepeat-detection:dev`
- A fresh user does not have these images, so they must currently run
  `bash scripts/build_dev_containers.sh` before the pipeline can run.
- If missing, Nextflow/Docker errors are not very explanatory.

Desired behavior:

- Publish versioned runtime images to Docker Hub.
- Make the normal user-facing Docker profile reference those published images,
  so Docker pulls them automatically on first run.
- Keep local `:dev` image builds documented for development and testing.
- Add preflight guidance or a small preflight process only as a fallback for
  cases where image pulls or local overrides fail.

### Output discovery

Current behavior:

- Output layout is documented, but users still need to know which files matter.

Desired behavior:

- Every successful run should have an obvious "start here" artifact.
- Candidate: `publish/README.txt` or `publish/START_HERE.md` generated from
  runtime metadata.
- It should point to `calls/repeat_calls.tsv`,
  `tables/accession_status.tsv`, `tables/accession_call_counts.tsv`, and
  `metadata/nextflow/report.html`.

### Error handling

Current behavior:

- Some failures are Nextflow-level or tool-level and may be hard to interpret.

Desired behavior:

- Missing accession file, missing explicit taxonomy DB, missing Docker images,
  and invalid residue input should produce short actionable messages.
- Status tables should distinguish:
  - accession downloaded and no calls found
  - accession failed acquisition
  - accession failed normalization
  - accession failed translation
  - workflow-level setup failure

## Proposed Implementation Phases

### Phase 0: Baseline and Inventory

Goal: record the current first-run experience before changing behavior.

Tasks:

- Run `nextflow config .`.
- Run a fixture/local smoke test if available.
- Run or dry-run a Docker command on a machine with no taxonomy DB at the
  default path, if feasible.
- Record current failure messages for:
  - missing default taxonomy DB
  - missing explicit taxonomy DB
  - missing Docker image
  - missing `--accessions_file`
  - invalid `--repeat_residues`
- Confirm whether generated docs currently state manual DB creation or
  auto-build.

Deliverables:

- Notes recorded in [baseline.md](./baseline.md).
- A short list of exact failures to improve.

Validation:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_pipeline_config
```

### Phase 1: Taxonomy Auto-Build Design

Goal: decide the exact behavior and edge cases before editing workflow code.

Design record: [taxonomy_auto_build_design.md](./taxonomy_auto_build_design.md).

Proposed behavior:

| Case | Behavior |
| --- | --- |
| user omits `--taxonomy_db`, default DB exists | reuse default DB |
| user omits `--taxonomy_db`, default DB missing | build default DB automatically |
| user passes `--taxonomy_db`, file exists | use that DB |
| user passes `--taxonomy_db`, file missing | fail with actionable message |
| user passes `--taxonomy_auto_build false`, default DB missing | fail with actionable message |

New or clarified parameters:

| Parameter | Default | Purpose |
| --- | --- | --- |
| `--taxonomy_db` | `runtime/cache/taxonomy/ncbi_taxonomy.sqlite` | DB path to use |
| `--taxonomy_auto_build` | `true` | Build default DB if missing and not explicitly overridden |
| `--taxonomy_build_mode` | `download` | Future-proof hook; initial implementation may omit |

Open design point:

- Nextflow config currently cannot easily distinguish "user supplied
  `--taxonomy_db`" after it assigns the default. The implementation needs a
  robust flag such as `taxonomy_db_supplied` computed before default assignment,
  or a different parameter shape such as `taxonomy_db = null` plus an internal
  effective path.

Preferred implementation sketch:

- Add a `BUILD_TAXONOMY_DB` process under `modules/local/acquisition/`.
- Label it `taxonomy_build`.
- Map `taxonomy_build` to the acquisition image in `conf/docker.config`.
- Build into the default cache path through `publishDir` or a controlled copy
  step.
- Feed the built DB path into `NORMALIZE_CDS_BATCH`.
- Avoid `checkIfExists: true` on the default path before the build decision.

Validation:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_pipeline_config
```

### Phase 2: Implement Taxonomy Auto-Build

Goal: make the shortest default Docker run create the taxonomy DB when absent.

Expected file set:

- `conf/base.config`
- `conf/docker.config`
- `workflows/acquisition_from_accessions.nf`
- `modules/local/acquisition/build_taxonomy_db.nf`
- possibly `modules/local/acquisition/normalize_cds_batch.nf`
- workflow tests under `tests/workflow/`
- README and operations docs

Implementation notes:

- Keep explicit `--taxonomy_db` behavior strict.
- Cache auto-built artifacts in `runtime/cache/taxonomy/`.
- Emit or preserve `ncbi_taxonomy_build.json` for provenance.
- Ensure `run_manifest.json` records the effective taxonomy DB path.
- Decide whether the build task should run before or after accession planning.
  Building before download gives earlier failure for taxonomy setup; building in
  parallel with acquisition may reduce wall time.

Test cases:

- default missing DB triggers build process
- default existing DB skips build process
- explicit missing DB fails before acquisition
- `--taxonomy_auto_build false` with missing default DB fails clearly
- explicit existing DB still works

Suggested fake `taxon-weaver` support:

- Extend existing workflow fake `taxon-weaver` test helper to implement
  `build-db` by writing an empty SQLite placeholder and JSON report.
- Keep `build-info` and `inspect-lineage` behavior as existing tests expect.

Validation:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_pipeline_config
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
```

Optional live validation:

```bash
bash scripts/build_dev_containers.sh
rm -f runtime/cache/taxonomy/ncbi_taxonomy.sqlite
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id auto_taxonomy_smoke \
  --accessions_file examples/accessions/smoke_human.txt
```

Expected outcome:

- The default run creates `runtime/cache/taxonomy/ncbi_taxonomy.sqlite`.
- The run no longer requires users to pass `--taxonomy_db` in the common case.

### Phase 3: Simplify the README Run Path

Goal: make the first visible user path short and biologically oriented.

README structure:

1. What the pipeline answers biologically.
2. Minimal requirements.
3. Build images.
4. Create or provide accessions.
5. Run the shortest command.
6. Open these files first.
7. Optional production command with explicit `NXF_HOME`, `-log`, and `--run_id`.
8. Background jargon.
9. Developer section.

Recommended shortest command:

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt
```

Recommended production command:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/my_run/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id my_run \
  --accessions_file inputs/my_accessions.txt \
  --repeat_residues Q,N
```

Docs changes:

- Remove wording that says the main pipeline does not create the DB.
- Explain that the default taxonomy DB is auto-built if missing.
- Keep a manual DB build section for offline, shared-cache, or controlled
  provenance environments.
- Clearly state that an explicitly supplied missing `--taxonomy_db` is an
  error.

Validation:

```bash
rg -n "does not create|does not auto-create|not auto-created" README.md docs/*.md
rg -n -- "--taxonomy_db runtime/cache/taxonomy/ncbi_taxonomy.sqlite" README.md docs/*.md
```

Expected outcome:

- New users see one short command first.
- Advanced users still see reproducible run commands and manual cache control.
- Active user-facing docs no longer tell users to pass `--taxonomy_db` for the
  default path.

### Phase 4: Add a Generated Start-Here Artifact

Goal: make each run self-explanatory after completion.

Candidate artifact:

```text
runs/<run_id>/publish/START_HERE.md
```

Contents:

- run status
- run ID
- accessions file
- repeat residues
- methods enabled
- taxonomy DB path
- main output files and what they mean
- how to distinguish no calls from failed accessions
- where the Nextflow report is

Implementation options:

- Extend `HomorepeatRuntimeArtifacts.finalizeRun`.
- Add a small Python CLI under `src/homorepeat/cli/`.
- Generate from `run_manifest.json` after finalization.

Preferred initial approach:

- Extend `HomorepeatRuntimeArtifacts.finalizeRun`, because it already owns
  launch metadata, run manifest, and completion-time artifacts.

Validation:

```bash
env PYTHONPATH=src python -m unittest tests.cli.test_runtime_artifacts
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
env PYTHONPATH=src python -m unittest tests.workflow.test_workflow_output_failures
```

### Phase 5: Preflight and Actionable Errors

Goal: fail early with helpful messages for common setup mistakes.

Candidate checks:

- accession file exists and has at least one non-comment accession
- residue list contains valid one-letter amino-acid codes
- Docker image availability for `docker` profile
- explicit taxonomy DB path exists
- `taxon-weaver` supports `build-db`, `build-info`, and `inspect-lineage`
- NCBI `datasets` binary is available in the acquisition runtime

Implementation options:

- Pure Nextflow guards for parameter and file checks.
- A lightweight Python preflight CLI for richer validation and messages.
- Documentation-only checklist for image checks if Docker probing inside
  Nextflow is too brittle.

Preferred order:

1. Add simple parameter guards in Nextflow where possible.
2. Add focused unit tests around validation helpers.
3. Consider a Python preflight CLI only if Nextflow guard logic becomes
   awkward.

Validation:

```bash
env PYTHONPATH=src python -m unittest tests.workflow.test_pipeline_config
```

Expected outcome:

- New users get messages that say what to do next, not just what failed.

### Phase 6: Publish User-Facing Docker Images

Goal: remove the local image-build step from the normal first-run path.

Recommended direction:

- Publish versioned images to Docker Hub.
- Make the default user-facing Docker profile use immutable Docker Hub tags.
- Keep `homorepeat-acquisition:dev` and `homorepeat-detection:dev` as local dev
  tags.
- Add a separate development profile or parameter override for local `:dev`
  images.

Example target image names:

```text
<dockerhub-user-or-org>/homorepeat-acquisition:0.1.0
<dockerhub-user-or-org>/homorepeat-detection:0.1.0
```

Configuration options:

| Option | User experience | Developer experience | Notes |
| --- | --- | --- | --- |
| Change existing `docker` profile to Docker Hub images | best default user path | devs need override/profile | recommended once images are published |
| Add new `dockerhub` profile and keep `docker` local | users must learn another profile | least disruptive | safer transition, less ideal UX |
| Keep local-only images | users must build images | current behavior | not good enough for first-run usability |

Open questions:

- Who owns releases and rebuild cadence?
- What Docker Hub namespace should be used?
- Should `latest` exist, or should docs use only pinned version tags?
- Should image tags track pipeline git tags, for example `0.1.0`, or dated
  builds?

Suggested decision:

- Publish images to Docker Hub.
- After images are available, make the main documented `-profile docker` path
  pull those images automatically.
- Keep local image building under a dev-specific section and/or profile.

### Phase 7: Larger Usability Backlog

Potential improvements after the main friction is removed:

- Add `examples/accessions/README.md` explaining how to choose accessions.
- Add `examples/outputs/` with tiny representative output snippets.
- Add an R/Python import example for `repeat_calls.tsv` and status tables.
- Add a troubleshooting matrix keyed by error text.
- Add a `docs/quickstart.md` that is shorter than `docs/operations.md`.
- Add a `--dry_run_inputs` or preflight-only mode if Nextflow supports it
  cleanly.
- Add a benchmark-free "small vs large run" decision table.

## Documentation Changes Checklist

When the auto-build behavior is implemented, update:

- `README.md`
- `docs/operations.md`
- `docs/background.md`
- `docs/contracts.md`
- `docs/README.md`
- `docs/containers.md`
- `runtime/README.md`, if cache semantics change

Required wording:

- Default runs auto-build the default taxonomy DB when it is missing.
- Explicit `--taxonomy_db` paths are treated as user-owned inputs.
- Manual taxonomy DB creation remains available for controlled environments.
- The first recommended command should omit `--taxonomy_db`.

## Testing Checklist

Narrow checks:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_pipeline_config
```

Workflow regression:

```bash
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
env PYTHONPATH=src python -m unittest tests.workflow.test_workflow_output_failures
```

Docs consistency:

```bash
rg -n "does not create|does not auto-create|not auto-created|must already exist" README.md docs
rg -n "--taxonomy_db runtime/cache/taxonomy/ncbi_taxonomy.sqlite" README.md docs
```

Live Docker smoke, if network and time allow:

```bash
bash scripts/build_dev_containers.sh
rm -f runtime/cache/taxonomy/ncbi_taxonomy.sqlite
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id auto_taxonomy_smoke \
  --accessions_file examples/accessions/smoke_human.txt
```

## Open Questions

- Should auto-build happen only for the default taxonomy path, or should there
  be an explicit `--taxonomy_auto_build true --taxonomy_db custom.sqlite` mode
  for custom paths?
- Should auto-build run before accession planning, or in parallel with download?
- Should the taxonomy build report be copied into `publish/metadata/` for each
  run, or is the cache-level JSON enough?
- Should a successful run publish `START_HERE.md` as part of the v2 contract, or
  as a convenience artifact outside the strict table contract?
- Should local image building remain mandatory, or should the project publish
  versioned images before advertising the shortest command?

## Proposed First PR Scope

Keep the first implementation PR small:

- add taxonomy auto-build for the default DB path
- add tests for missing default DB and missing explicit DB
- update README and operations docs to show the shorter run command
- avoid adding generated `START_HERE.md` in the same PR

Reasoning:

- Taxonomy auto-build is the largest current first-run blocker.
- It changes runtime behavior and deserves focused review.
- Output-discovery improvements can follow without entangling workflow setup
  behavior.
