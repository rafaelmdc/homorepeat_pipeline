# Publish Contract Codebase Slices

This document translates the frozen plan in
`docs/implementation/publish_contract_optimization/` into implementation-sized
slices that match the current repository layout.

It does not replace the frozen plan. It is the execution breakdown for the
current codebase.

Planning assumption for this document:

- there is no backward-compatibility requirement for the publish contract
- the rollout can hard-cut from the current MVP contract to the new one
- explicit contract versioning can stay, but consumers may fail fast on
  unsupported versions instead of carrying dual-read logic

## Scope Boundaries

- This repo is the pipeline repo.
- The frozen implementation plan also includes work for the sister import repo.
- Slices below are split into:
  - pipeline slices that map directly to files in this workspace
  - external handoff slices for the import/browser repo

## Current Code Anchors

The publish-contract work in this repo centers on these existing files:

- Top-level workflow and publish wiring:
  - `main.nf`
  - `workflows/acquisition_from_accessions.nf`
  - `workflows/detection_from_acquisition.nf`
  - `workflows/database_reporting.nf`
- Batch acquisition and finalization processes:
  - `modules/local/acquisition/*.nf`
  - `modules/local/detection/*.nf`
  - `modules/local/reporting/*.nf`
- Manifest and runtime metadata:
  - `lib/HomorepeatRuntimeArtifacts.groovy`
  - `src/homorepeat/runtime/run_manifest.py`
  - `src/homorepeat/runtime/accession_status.py`
- Contract and table logic:
  - `src/homorepeat/contracts/*.py`
  - `src/homorepeat/io/*.py`
  - `src/homorepeat/db/sqlite_build.py`
  - `src/homorepeat/reporting/*.py`
- Existing regression coverage:
  - `tests/workflow/test_publish_modes.py`
  - `tests/workflow/test_workflow_output_failures.py`
  - `tests/cli/test_runtime_artifacts.py`
  - `tests/cli/test_accession_status.py`
  - `tests/cli/test_slice2_acquisition.py`
  - `tests/cli/test_slice8_summaries.py`

## Phase 1: Define The v2 Contract

### Slice 1.1: Add explicit contract versioning to runtime metadata

Goal:

- make v2 dispatch explicit in the manifest instead of inferred from directory shape
- keep the hard switch machine-readable even without a migration window

Main files:

- `lib/HomorepeatRuntimeArtifacts.groovy`
- `src/homorepeat/runtime/run_manifest.py`
- `main.nf`

Changes:

- add `publish_contract_version`
- add v2 artifact keys for the new flat table layout
- keep `acquisition_publish_mode` as provenance, not the primary dispatch key
- current state can remain version `1` until the v2 flat publish surface lands

Tests:

- `tests/cli/test_runtime_artifacts.py`
- `tests/workflow/test_publish_modes.py`
- `tests/workflow/test_workflow_output_failures.py`

Dependency:

- none

### Slice 1.2: Create shared v2 table definitions and validators

Goal:

- stop scattering fieldnames and shape rules across future CLIs

Recommended new files:

- `src/homorepeat/contracts/publish_contract_v2.py`

Likely contents:

- fieldnames for:
  - `genomes.tsv`
  - `taxonomy.tsv`
  - `matched_sequences.tsv`
  - `matched_proteins.tsv`
  - `repeat_call_codon_usage.tsv`
  - `repeat_context.tsv`
  - flat `download_manifest.tsv`
  - flat `normalization_warnings.tsv`
- lightweight row validators

Tests:

- new unit test file such as `tests/unit/test_publish_contract_v2.py`

Dependency:

- Slice 1.1 is not required, but both should land before pipeline publish rewiring

### Slice 1.3: Document the v2 surface outside the frozen plan

Goal:

- keep current-state docs in sync with the future implementation

Main files:

- `docs/contracts.md`
- `docs/operations.md`
- `docs/architecture.md`
- `docs/README.md`

Dependency:

- best done after Slice 2.5, when the output layout is real

## Phase 2: Pipeline Changes In This Repo

### Slice 2.1: Add one flat export reducer for always-kept provenance tables

Goal:

- build the flat v2 `tables/` layer without relying on published batch directories

Recommended new files:

- `src/homorepeat/runtime/publish_contract_v2.py`
- `src/homorepeat/cli/export_publish_tables.py`
- `modules/local/reporting/export_publish_tables.nf`

Inputs that already exist in the workflow:

- `batch_table`
- `batch_inputs`
- `statusBuild.*`
- merged call tables

Outputs to derive here:

- `tables/genomes.tsv`
- `tables/taxonomy.tsv`
- `tables/download_manifest.tsv`
- `tables/normalization_warnings.tsv`
- `tables/accession_status.tsv`
- `tables/accession_call_counts.tsv`
- `summaries/status_summary.json`
- optional `summaries/acquisition_validation.json`

Why this slice is separate:

- these tables keep all requested accessions, including zero-hit accessions
- they do not depend on hit-linked filtering logic

Tests:

- extend `tests/workflow/test_publish_modes.py`
- extend `tests/cli/test_accession_status.py`
- add a CLI reducer test for the flat table export

Dependency:

- Slice 1.2

### Slice 2.2: Export `matched_sequences.tsv` from repeat-linked IDs

Goal:

- publish only sequence rows referenced by `repeat_calls.tsv`

Likely implementation points:

- `src/homorepeat/runtime/publish_contract_v2.py`
- `src/homorepeat/cli/export_publish_tables.py`

Current source data:

- per-batch `sequences.tsv` inside normalized batch dirs
- canonical merged `repeat_calls.tsv`

Required logic:

- scan `repeat_calls.tsv` for retained `sequence_id`s
- join back to batch-local `sequences.tsv`
- emit only matched rows
- add explicit `batch_id`

Tests:

- new CLI coverage for matched-sequence filtering
- workflow assertion that unmatched sequence IDs are not published

Dependency:

- Slice 2.1

### Slice 2.3: Export `matched_proteins.tsv` from repeat-linked IDs

Goal:

- publish only protein rows referenced by `repeat_calls.tsv`

Likely implementation points:

- same reducer path as Slice 2.2

Current source data:

- per-batch `proteins.tsv` inside translated batch dirs
- canonical merged `repeat_calls.tsv`

Required logic:

- scan `repeat_calls.tsv` for retained `protein_id`s
- join back to batch-local `proteins.tsv`
- emit only matched rows
- add explicit `batch_id`

Tests:

- new CLI coverage for matched-protein filtering
- workflow assertion that zero-hit proteins are not published

Dependency:

- Slice 2.1

### Slice 2.4: Merge codon-usage fragments into one canonical export

Goal:

- stop treating per-finalizer codon-usage fragments as the public import surface

Current source files:

- `modules/local/detection/extract_repeat_codons.nf`
- `src/homorepeat/cli/extract_repeat_codons.py`
- `src/homorepeat/detection/codon_extract.py`

Recommended new files:

- `src/homorepeat/cli/merge_codon_usage_tables.py`
- `modules/local/reporting/merge_codon_usage_tables.nf`

Output:

- `tables/repeat_call_codon_usage.tsv`

Implementation note:

- this should mirror the existing `merge_call_tables` pattern
- the merge is mechanical and can land before repeat-context work

Tests:

- new CLI regression for codon-usage merge
- workflow assertion that the merged table exists and finalized fragment crawling is no longer required

Dependency:

- none beyond existing codon finalizer outputs

### Slice 2.5: Add repeat-context export

Goal:

- replace default published full FASTA bodies with compact context windows

Current usable data sources:

- `repeat_calls.tsv`
- per-batch `sequences.tsv`
- per-batch `cds.fna`
- per-batch `proteins.faa`

Recommended new files:

- `src/homorepeat/detection/repeat_context.py`
- `src/homorepeat/cli/export_repeat_context.py`
- `modules/local/reporting/export_repeat_context.nf`

Output:

- `tables/repeat_context.tsv`

Recommended columns:

- `call_id`
- `protein_id`
- `sequence_id`
- `aa_left_flank`
- `aa_right_flank`
- `nt_left_flank`
- `nt_right_flank`
- `aa_context_window_size`
- `nt_context_window_size`

Implementation note:

- this slice still reads internal FASTA artifacts
- it does not require publishing those FASTA files in the final default contract

Tests:

- unit tests for flank extraction
- CLI test for boundary conditions at sequence ends
- workflow test that `repeat_context.tsv` exists and is keyed by `call_id`

Dependency:

- Slice 2.2 and Slice 2.3 are helpful but not strictly required

### Slice 2.6: Rewire the default publish surface to the v2 flat layout

Goal:

- make the v2 `tables/` and `summaries/` tree the default publish contract
- switch the manifest to `publish_contract_version = 2`

Main files:

- `main.nf`
- `workflows/database_reporting.nf`
- `modules/local/reporting/*.nf`
- `lib/HomorepeatRuntimeArtifacts.groovy`
- `src/homorepeat/runtime/run_manifest.py`

Key changes:

- publish flat `tables/` outputs
- publish `summaries/status_summary.json`
- stop default-publication of:
  - batch-scoped `sequences.tsv`
  - batch-scoped `proteins.tsv`
  - `cds.fna`
  - `proteins.faa`
  - per-finalizer duplicate call tables
  - per-finalizer duplicate run-params tables
- keep finalized fragments only if they remain useful as optional diagnostics

Important constraint:

- the workflow may still generate broad sequence/protein/FASTA artifacts internally
- the change is to the default public contract, not the internal execution model

Tests:

- rewrite `tests/workflow/test_publish_modes.py` expectations around the new `tables/` surface
- extend `tests/cli/test_runtime_artifacts.py`
- add negative assertions that default v2 publish no longer includes `cds.fna` and `proteins.faa`

Dependency:

- Slices 2.1 through 2.5

## Phase 3: Sister Import Repo Handoff Slices

These slices are outside this workspace. They are included here so the pipeline
work lands with a clean integration boundary.

### Slice 3.1: Contract dispatch in published-run inspection

Frozen-plan paths:

- `apps/imports/services/published_run/`

Expected work:

- dispatch on `publish_contract_version`
- validate v2 flat table locations
- require `publish_contract_version = 2`
- stop requiring FASTA artifacts
- fail fast on unsupported contract versions instead of carrying a legacy path

Pipeline dependency:

- Slice 1.1

### Slice 3.2: Importers consume flat v2 tables directly

Frozen-plan paths:

- `apps/imports/services/import_run/`

Expected work:

- read `matched_sequences.tsv`
- read `matched_proteins.tsv`
- read `repeat_call_codon_usage.tsv`
- read `repeat_context.tsv`
- stop walking batch directories
- stop reading `cds.fna` and `proteins.faa` for the default path

Pipeline dependency:

- Slices 2.2 through 2.5

### Slice 3.3: Hard-cut importer regression coverage

Expected work:

- add v2 import fixtures and regression tests
- compare imported repeat/codon/context rows against pipeline outputs from the new contract
- remove any assumptions that batch-scoped acquisition artifacts or FASTA payloads are part of the required import surface

Pipeline dependency:

- Slice 2.6

## Phase 4: Sister Browser/Model Handoff Slices

These are also outside this workspace and should be treated as downstream
consumers of the new contract.

### Slice 4.1: Make full sequence bodies optional in models

Expected work:

- allow sequence/protein body fields to be nullable or blank for v2 imports

Pipeline dependency:

- Slice 2.5

### Slice 4.2: Move detail pages to tract-plus-context rendering

Expected work:

- use `repeat_calls.tsv` plus `repeat_context.tsv`
- keep identifiers, lengths, tract AA sequence, codon sequence, and flanks as the core detail payload

Pipeline dependency:

- Slice 2.5

### Slice 4.3: Browser regression coverage

Expected work:

- verify detail pages remain useful without full stored sequence bodies
- verify zero-hit accession visibility still comes from accession/genome/status tables

## Recommended PR Cut Lines

If you want this in reviewable chunks, the cleanest cut lines are:

1. Slice 1.1 + Slice 1.2
2. Slice 2.1 + Slice 2.2 + Slice 2.3
3. Slice 2.4
4. Slice 2.5
5. Slice 2.6
6. Sister repo hard-cut slices

That sequencing keeps the early work mostly additive, lands the easy merge
reducers before the context export, and pushes the risky publish-surface switch
to a point where the new flat tables already exist.

## Highest-Risk Areas

- `lib/HomorepeatRuntimeArtifacts.groovy` and `src/homorepeat/runtime/run_manifest.py` duplicate manifest behavior and must stay aligned
- `main.nf` publish rewiring is easy to get wrong because placeholders and mode-aware outputs already exist
- repeat-context generation is the first slice that needs internal FASTA access while also removing FASTA from the default published contract
- workflow tests will need deliberate rewrites rather than small expectation tweaks once the default tree moves from `acquisition/batches/*` to `tables/`
- the sister importer and browser need to be ready for the hard cut before Slice 2.6 merges, because there is no planned dual-contract overlap
