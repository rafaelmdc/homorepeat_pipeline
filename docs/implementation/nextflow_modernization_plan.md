# Nextflow Modernization Implementation Plan

This plan implements the design in
[`nextflow_modernization_dag.md`](./nextflow_modernization_dag.md) in small,
reviewable slices. The first priority is fixing the generated DAG at the
workflow-graph source while keeping the v2 publish contract stable.

## Phase 0: Baseline and Reproduction

Goal: capture the current behavior before changing workflow structure.

Changes:

- Do not edit workflow code yet.
- Add a small local helper command or documented manual check for counting blank
  Mermaid nodes in `dag.html`.
- Run one raw-mode workflow with existing fixtures and save the run id.
- If feasible, run one merged-mode workflow with existing fixtures and save the
  run id.

Validation:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
rg 'v[0-9]+\\[" "\\]|v[0-9]+\\(\\( \\)\\)' \
  runs/<run_id>/internal/nextflow/dag.html
```

Expected outcome:

- Tests still pass before refactoring.
- Current DAG noise is measured and attributable to placeholder publishing and
  acquisition publication-only outputs.
- Blank node count from the raw-mode DAG is recorded here and used as the upper
  threshold for the Phase 6 regression guard.

## Phase 0 Results (recorded 2026-04-25)

Pre-refactor baseline:

- `nextflow config .` — passes, NF 25.10.4.
- `tests.workflow.test_publish_modes` — 2/2 pass.
- `tests.workflow.test_workflow_output_failures` — 1/1 pass.
- Raw-mode blank node count: **68** (run `smoke_human`,
  `runs/smoke_human/internal/nextflow/dag.html`).
  - 38 square `v[" "]` nodes — anonymous channel sources / sinks.
  - 30 circle `v(( ))` nodes — anonymous operator merge/fan-out points.
  - Attributed to two sources: `publishablePathChannel` placeholder injection in
    `main.nf` and un-emitted `publish_batch/*` outputs in `NORMALIZE_CDS_BATCH`
    / `TRANSLATE_CDS_BATCH`.
- Helper script added: `scripts/count_dag_noise.sh [dag.html]`.

The Phase 6 regression guard should assert blank node count ≤ 0 (or a small
single-digit number if Nextflow itself introduces unavoidable internals).

## Phase 1: Verify Empty Workflow Output Semantics

Goal: decide whether Option 1 from the design is safe in Nextflow 25.10.

Changes:

- Create a temporary minimal Nextflow probe outside production workflow code, or
  use a throwaway branch edit, to test workflow outputs assigned directly from
  `Channel.empty()`.
- Test a raw-mode run path where `database_*` and `reports_*` outputs are empty.
- Confirm whether the previous `Cannot access first() element from an empty
  List` failure still occurs without placeholder injection.

Validation:

```bash
nextflow config .
nextflow run <minimal_probe_or_throwaway_workflow>
```

Decision:

- If `Channel.empty()` workflow outputs are graceful no-ops, implement Phase 2A.
- If they still crash, skip Phase 2A and implement Phase 2B.

Expected outcome:

- A clear recorded decision in this document or a session log:
  `empty workflow outputs supported: yes/no`.

## Phase 1 Results (recorded 2026-04-25)

**Empty workflow outputs supported: YES.**

Probe: `runtime/probe/empty_output_probe.nf` with `runtime/probe/probe.config`.
NF 25.10.4, local executor.

| Scenario | Channel | Outcome |
|---|---|---|
| `always_present` | real file | published to `present/out.txt` ✓ |
| `always_empty` | `Channel.empty()` | no file, no directory, no crash ✓ |
| `conditional_out` (emit_real=true) | real file | published to `cond/out.txt` ✓ |
| `conditional_out` (emit_real=false) | `Channel.empty()` | no file, no directory, no crash ✓ |

NF 25.10 treats an empty-channel `publish:` binding as a silent no-op — it does
not create the target directory and does not raise an error. The placeholder
mechanism is no longer needed.

**Proceed with Phase 2A.**

## Phase 2A: Remove Placeholder Publishing

Use this phase only if Phase 1 confirms empty workflow outputs are safe.

Goal: remove the main source of blank DAG nodes.

Changes:

- In `main.nf`, remove:
  - `WORKFLOW_OUTPUT_PLACEHOLDER_FILE`
  - `publishablePathChannel`
  - `publishTarget`
- In `workflow { publish: }`, assign public outputs directly:
  - `calls_repeat = canonicalCalls.repeat_calls_tsv`
  - `database_sqlite = databaseSqliteCh`
  - and so on.
- In `output {}`, replace dynamic `path { artifact -> ... }` closures with
  plain destination strings:
  - `path 'calls'`
  - `path 'tables'`
  - `path 'summaries'`
  - `path 'database'`
  - `path 'reports'`
- Remove placeholder cleanup from `lib/HomorepeatRuntimeArtifacts.groovy`:
  delete the `cleanupWorkflowOutputPlaceholders` method (lines 132–138) and
  remove its single call site on line 80 (`cleanupWorkflowOutputPlaceholders(publishRoot)`).
- Delete `runtime/output_placeholders/workflow_output_placeholder.txt` and the
  now-empty placeholder directory.

Validation:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_workflow_output_failures
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
```

DAG check:

```bash
rg 'WORKFLOW_OUTPUT_PLACEHOLDER|publishablePathChannel|publishTarget|\\.nf_placeholders' \
  main.nf lib runtime tests docs
rg 'v[0-9]+\\[" "\\]|v[0-9]+\\(\\( \\)\\)' \
  runs/<raw_run_id>/internal/nextflow/dag.html
```

Expected outcome:

- Raw-mode workflow still publishes the same v2 contract.
- Merged-mode workflow still publishes database/report outputs.
- Failed-run regression no longer needs placeholder files to avoid a workflow
  output crash.
- DAG loses the large blank rows caused by placeholder `mix()` channels.

## Phase 2B: Split Entry Workflows by Publish Mode

Use this phase only if Phase 1 shows empty workflow outputs still crash.

Goal: avoid optional empty workflow outputs without placeholder channels.

Changes:

- Keep one shared implementation path for the actual pipeline graph.
- Split the entry workflow publication path by mode:
  - raw mode publishes only raw contract outputs.
  - merged mode publishes raw contract outputs plus `database/*` and `reports/*`.
- Keep `output {}` declarations aligned with the active publish bindings.
- Avoid `Channel.value()` placeholders and publication-only `mix()` calls.

Implementation options to evaluate:

- Two named workflows plus a thin entry workflow that chooses one mode.
- One entry workflow with mode-specific `publish:` assignments if Nextflow
  permits conditional output bindings cleanly.
- Separate launch entry points only if the single-entry approach is not
  maintainable.

Validation:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_workflow_output_failures
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
```

DAG check:

```bash
rg 'v[0-9]+\\[" "\\]|v[0-9]+\\(\\( \\)\\)' \
  runs/<raw_run_id>/internal/nextflow/dag.html
rg 'v[0-9]+\\[" "\\]|v[0-9]+\\(\\( \\)\\)' \
  runs/<merged_run_id>/internal/nextflow/dag.html
```

Expected outcome:

- Raw-mode DAG does not contain optional database/report publishing scaffolding.
- Merged-mode DAG includes database/report tasks as named nodes.
- Public output paths remain identical to the current v2 contract.

## Phase 3: Remove Acquisition Publication-Only Outputs

**Note:** This phase is independent of the Phase 2A/2B decision. The acquisition
module cleanup has no dependency on the placeholder removal outcome and can be
done before Phase 2, after Phase 2, or on a parallel branch.

Goal: remove un-emitted acquisition output leaves from the DAG.

Changes:

- In `modules/local/acquisition/normalize_cds_batch.nf`:
  - remove the disabled `publishDir(...)` block.
  - remove un-emitted outputs:
    - `path("publish_batch/taxonomy.tsv")`
    - `path("publish_batch/sequences.tsv")`
    - `path("publish_batch/cds.fna")`
  - remove `mkdir -p publish_batch` and symlink commands.
  - keep `tuple val(batch_id), path("normalized_batch"), emit: normalized_batch`.
- In `modules/local/acquisition/translate_cds_batch.nf`:
  - remove the disabled `publishDir(...)` block.
  - remove un-emitted `publish_batch/*` outputs.
  - remove `mkdir -p publish_batch` and symlink commands.
  - keep `tuple val(batch_id), path("translated_batch"), emit: translated_batch`.

Validation:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
```

Contract checks:

- `publish/acquisition/` remains absent in default raw and merged runs.
- `publish/tables/*`, `publish/calls/*`, and `publish/summaries/*` are
  unchanged.
- No test depends on `publish_batch/*`.

Expected outcome:

- Fewer blank sink nodes in the acquisition region of the DAG.
- Acquisition modules emit only meaningful downstream channels.

## Phase 4: Collapse Duplicate Acquisition Join

Goal: remove duplicate channel construction in `acquisition_from_accessions.nf`.

Changes:

- Replace:
  - `batchRowsForEmit = normalized.normalized_batch.join(translated.translated_batch)`
  - `batchRowsForReduction = normalized.normalized_batch.join(translated.translated_batch)`
- With one shared channel, for example:
  - `batchRows = normalized.normalized_batch.join(translated.translated_batch)`
- Use `batchRows` for both:
  - `emit: batch_rows = batchRows`
  - `batchInputs = batchRows.toList().map { ... }`

Risk:

- In DSL2, channels are multi-consumer by design — unlike DSL1 where a channel
  could only be consumed once. Feeding the same channel into both `emit` and
  `.toList()` is safe. This phase is low-risk; the duplicate join exists for no
  technical reason and can be collapsed.

Validation:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
```

Expected outcome:

- One less duplicated operator path if Nextflow allows shared consumption here.
- No change to published outputs.

## Phase 5: Trim Entry Workflow Emits

Goal: reduce dead top-level graph surface if it contributes DAG noise.

Changes:

- Audit the entry `workflow { emit: }` block in `main.nf`.
- Remove emitted channels that are not consumed by tests, external entrypoint
  composition, or documented API.
- Keep only emissions that are demonstrably useful.

Constraints:

- Do not remove subworkflow emits from `workflows/*.nf`; those are used for
  composition.
- Do not change process emits.
- If no concrete consumer exists for entry workflow emits, prefer deleting them
  all after tests confirm no impact.

Validation:

```bash
rg '\\.out\\.|emit:|workflow .*take:' tests docs main.nf workflows modules
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
```

Note: the `rg` command finds intra-workflow channel references (`.out.`, `emit:`)
and subworkflow `take:` inputs. It will **not** catch test-level consumers
because the Python tests assert against published file paths, not Nextflow channel
names. Before removing an emit, also verify no test asserts on a file that is
only reachable via that specific emit (as opposed to via the matching `publish:`
entry).

Expected outcome:

- Entry workflow publishes public outputs but does not expose unnecessary
  duplicate channels.
- DAG contains less top-level output clutter.

## Phase 6: DAG Regression Guard

Goal: prevent the placeholder pattern from returning.

Changes:

- Add a workflow-level regression test or helper assertion that inspects
  generated `dag.html` after the existing fixture runs.
- Count blank Mermaid nodes with a regex:
  - `v[0-9]+[" "]`
  - `v[0-9]+(( ))`
- Assert either zero blank nodes or a threshold no greater than the Phase 0
  baseline count for a clean (non-placeholder) run. Any remaining blank nodes
  must be attributed to unavoidable Nextflow internals, not repo code.
- Assert forbidden placeholder symbols are absent from `main.nf`.

Suggested test location:

- `tests/workflow/test_publish_modes.py`, because it already performs raw and
  merged end-to-end fixture runs.

Validation:

```bash
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
```

Expected outcome:

- Future changes that reintroduce placeholder publishing or publication-only
  DAG leaves fail in tests.

## Phase 7: Documentation and Cleanup

Goal: make docs match the new maintained structure.

Changes:

- Update `docs/architecture.md` to state that public publication is exclusively
  via workflow outputs.
- Update `docs/development.md` process guidance:
  - process modules emit structured outputs.
  - public contract routing belongs in `main.nf` workflow outputs.
  - avoid process `publishDir` for public artifacts.
- Update `docs/contracts.md` only if artifact paths changed. They should not
  change in this project.
- Remove or update references to placeholders and `.nf_placeholders`.

Validation:

```bash
rg 'publishDir|placeholder|\\.nf_placeholders|workflow_output_placeholder' docs README.md main.nf lib tests runtime
git diff --check
```

Expected outcome:

- Documentation describes current behavior rather than historical scaffolding.
- No placeholder artifact remains in code, tests, docs, or runtime support.

## Final Acceptance

Run the focused suite:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest tests.workflow.test_workflow_output_failures
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
```

Then inspect raw and merged DAGs:

```bash
rg 'v[0-9]+\\[" "\\]|v[0-9]+\\(\\( \\)\\)' \
  runs/<raw_run_id>/internal/nextflow/dag.html
rg 'v[0-9]+\\[" "\\]|v[0-9]+\\(\\( \\)\\)' \
  runs/<merged_run_id>/internal/nextflow/dag.html
```

The work is complete when:

- public output paths are unchanged.
- failed runs still write metadata and diagnostics.
- `publish/metadata/nextflow/dag.html` no longer has the placeholder-driven
  rows of anonymous nodes.
- any remaining blank nodes are documented as intentional or unavoidable
  Nextflow internals, not repo-created publication scaffolding.
