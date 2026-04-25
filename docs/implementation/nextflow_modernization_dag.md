# Nextflow Modernization and DAG Cleanup

## Goal

Make the workflow structure match modern Nextflow 25.10 usage while fixing the
generated DAG at the source. The DAG should communicate the biological and
reporting stages, not a tangle of anonymous channel placeholders.

**This is not a DSL1 → DSL2 migration.** Every `.nf` file already uses DSL2:
`nextflow.enable.dsl = 2`, `workflow {}` / `process {}` with `emit:`, and
`include {}` statements are already in place. The problem is channel topology
noise introduced by the placeholder publishing pattern, not the DSL version.

Success criteria:

- `publish/metadata/nextflow/dag.html` shows named workflow and process nodes
  without large rows of blank square/circle nodes.
- Public artifacts are still published through workflow outputs, not
  process-level `publishDir` rules.
- The v2 publish contract does not change unless explicitly planned.
- Failed runs still produce metadata and Nextflow diagnostics without the
  prior empty-output crash.

## Nextflow Direction

Use workflow outputs as the public publishing interface. Seqera's workflow
output migration guide describes workflow outputs as the replacement for
`publishDir`, stable in Nextflow 25.10, with output assignment in the entry
workflow `publish:` section and destination rules in the top-level `output`
block.

Implications for this repo:

- Keep `workflow.output.mode = 'copy'` and `outputDir = params.output_dir`.
- Keep public contract routing in `main.nf` through `workflow { publish: ... }`
  plus `output { ... }`.
- Remove process-level `publishDir` from reusable modules unless it is only for
  internal diagnostics and not part of the public contract.
- Keep modules reusable: process files emit structured outputs and do not know
  public contract directories.

## Current DAG Problem

The current DAG is noisy because `main.nf` manufactures extra channel graph
nodes for publishing:

- `publishablePathChannel(channel)` mixes each real output with
  `Channel.value(WORKFLOW_OUTPUT_PLACEHOLDER_FILE)`.
- Every optional output therefore creates an additional anonymous source node,
  a `mix` operator node, and a sink node in the Mermaid DAG.
- Acquisition modules also declare un-emitted `path("publish_batch/...")`
  outputs used only by disabled `publishDir` rules. These create anonymous
  leaf nodes even though they are not meaningful workflow stages.

The generated DAG is therefore accurately drawing the channel graph, but the
channel graph contains publishing scaffolding that should not be part of the
pipeline topology.

## Target Structure

The DAG-friendly structure is:

```text
main.nf
  workflow
    ACQUISITION_FROM_ACCESSIONS
    DETECTION_FROM_ACQUISITION
    reducers/reporting
    publish: direct named channels only
  output
    one output entry per public contract group/file

workflows/
  acquisition_from_accessions.nf
  detection_from_acquisition.nf
  database_reporting.nf

modules/local/
  processes emit only files consumed by downstream workflow outputs
```

The entry workflow should publish direct process or reducer outputs:

```nextflow
workflow {
  main:
  acquisition = ACQUISITION_FROM_ACCESSIONS()
  detection = DETECTION_FROM_ACQUISITION(acquisition.batch_rows)
  canonicalCalls = MERGE_CALL_TABLES(detection.call_tsvs, detection.run_params_tsvs)

  publish:
  calls_repeat = canonicalCalls.repeat_calls_tsv
  calls_params = canonicalCalls.run_params_tsv
}

output {
  calls_repeat {
    path 'calls'
  }

  calls_params {
    path 'calls'
  }
}
```

Do not wrap published channels in `mix`, `Channel.value`, placeholder files, or
publication-only operators.

## Handling Optional Outputs

The hard part is optional public outputs. In `raw` mode, `database/*` and
`reports/*` do not exist. The previous placeholder approach avoided empty
workflow-output failures, but it polluted the DAG.

Preferred implementation options, in order:

1. Conditional workflow outputs — the preferred path if NF 25.10 handles
   `Channel.empty()` in `publish:` as a graceful no-op instead of crashing.
   - The placeholder exists precisely to prevent an empty-channel crash in
     workflow outputs. Before removing it, verify that NF 25.10 tolerates an
     empty channel in `publish:` by running `nextflow config .` then a minimal
     dry run with `acquisition_publish_mode = 'raw'` before committing to this
     approach.
   - If confirmed safe: remove `publishablePathChannel`, assign channels
     directly in `publish:`, and let the optional `database_*` / `reports_*`
     channels remain as `Channel.empty()` when in raw mode.
   - If NF 25.10 still crashes on empty workflow outputs, fall back to Option 2.

2. Split entry workflows by publish mode.
   - Keep shared subworkflows and modules.
   - Provide a raw entry path with only raw-mode public outputs.
   - Provide a merged entry path with database/report outputs.
   - This avoids empty optional channels and keeps each DAG honest.

3. Always generate small terminal reducer outputs for optional sections.
   - Add explicit named no-op/reporting processes that write empty or skipped
     marker files only if the contract intentionally wants them.
   - Do not use anonymous placeholder value channels.
   - This should be avoided unless the public contract accepts those files.

Do not reintroduce process `publishDir` as the primary solution. It hides the
problem from workflow outputs but moves publication back toward the older
process-scoped model.

## Detection Workflow Channel Pattern

The `detection_from_acquisition.nf` subworkflow also uses `Channel.empty()` +
`mix()` — for the `run_pure`, `run_threshold`, and `run_seed_extend` paths.
These nodes in the DAG are **intentional topology**, not noise. They represent
the merge point of conditionally-enabled detection methods and should remain
unchanged. Do not apply the placeholder-cleanup logic to this subworkflow.

## Module Cleanup

Remove publication-only outputs from acquisition modules:

- `NORMALIZE_CDS_BATCH` should emit `normalized_batch` only.
- `TRANSLATE_CDS_BATCH` should emit `translated_batch` only.
- Delete disabled `publishDir(...)` blocks and `publish_batch/*` outputs once
  no test or workflow path depends on them.

The files are still available inside `normalized_batch` and `translated_batch`
for reducers. Public flat tables should continue to come from
`EXPORT_PUBLISH_TABLES`, not from batch-level acquisition publication.

`acquisition_from_accessions.nf` also has a minor duplicate: `batchRowsForEmit`
and `batchRowsForReduction` (lines 33–34) perform the exact same `.join()` on
the same upstream channels. Collapse them into a single channel used in both the
`emit:` and the reduction inputs.

## Main Workflow Cleanup

Refactor `main.nf` in a small sequence:

1. Remove `WORKFLOW_OUTPUT_PLACEHOLDER_FILE`, `publishablePathChannel`, and
   `publishTarget`.
2. Delete `runtime/output_placeholders/workflow_output_placeholder.txt` and its
   directory. The `checkIfExists: true` reference on the file in `main.nf` will
   cause a startup error if the variable is removed but the file is not.
3. Assign publish outputs directly from named reducer channels.
4. Simplify the `output {}` block: once `publishTarget` is gone, replace every
   `path { artifact -> ... }` closure with a plain string, e.g. `path 'calls'`.
5. Remove or trim the `emit:` block. The entry workflow currently emits ~30
   named channels (lines 128–162) that duplicate what is already in `publish:`.
   Entry workflows cannot be composed, so `emit:` is dead weight there; remove
   channels that are not consumed by tests or external callers.
6. Make optional merged-mode outputs conditional rather than placeholder-backed.
7. Keep `workflow.onComplete` responsible for metadata, run manifest, and
   Nextflow diagnostic links only.
8. Remove placeholder cleanup once no `.nf_placeholders` path can be created.

The target is for every node in the DAG to be one of:

- a named input value such as `accessions_file` or `taxonomy_db`
- a named process
- a named subworkflow
- a meaningful named public output

## Validation Plan

Use narrow checks first:

```bash
nextflow config .
```

Then run focused workflow checks:

```bash
env PYTHONPATH=src python -m unittest tests.workflow.test_workflow_output_failures
env PYTHONPATH=src python -m unittest tests.workflow.test_publish_modes
```

Inspect generated DAGs for both modes:

```bash
rg 'v[0-9]+\\[" "\\]|v[0-9]+\\(\\( \\)\\)' \
  runs/<run_id>/internal/nextflow/dag.html
```

The command should return no blank Mermaid nodes, or only a very small number
that correspond to unavoidable Nextflow internals. If blank nodes remain, trace
them back to channel operators in `main.nf` or un-emitted process outputs before
considering any HTML post-processing.

## References

- Seqera Docs, "Migrating to workflow outputs": workflow outputs are stable in
  Nextflow 25.10 and replace `publishDir` for top-level workflow publication.
- Seqera Docs, "Syntax": top-level script declarations include workflow
  definitions, process definitions, function definitions, and the output block;
  statements and declarations should not be mixed at the same level.
- Seqera Docs, "Process reference": `publishDir` is still supported, but the
  docs point users to workflow outputs as the migration path.
