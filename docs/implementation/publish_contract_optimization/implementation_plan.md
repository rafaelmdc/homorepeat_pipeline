# Publish Contract Optimization Implementation Plan

## Summary

Introduce a versioned publish contract v2 that keeps accession-, genome-,
taxonomy-, run-, and repeat-level meaning intact while removing repeated
search-space artifacts from the default published output.

The implementation should optimize for:

- minimal published size
- minimal importer filtering work
- fast downstream import
- stable biological interpretation
- explicit backward compatibility during migration

The key rule is simple:

- keep all accession/genome/status/provenance rows
- keep only hit-linked sequence and protein rows
- keep compact repeat context instead of full published FASTA bodies

## Contract Decisions

The implementation should freeze these decisions:

- default sequence/protein publish scope is hit-linked only
- zero-hit accessions remain visible through genome and status tables
- full `cds.fna` and `proteins.faa` are not part of the default v2 contract
- `repeat_call_codon_usage.tsv` is the canonical codon-usage export
- `repeat_context.tsv` is the canonical compact context export
- `publish_contract_version` is required in `run_manifest.json`
- importer supports both v1 and v2 during migration

## Phase 1: Define The v2 Contract

### Manifest

Update the pipeline manifest writer so `metadata/run_manifest.json` includes:

- `publish_contract_version`
- `artifacts` entries that point to the v2 flat table layout

Keep existing provenance keys such as:

- `run_id`
- `status`
- `profile`
- `git_revision`
- `inputs`
- `paths`
- `params`
- `enabled_methods`
- `repeat_residues`

Importer contract dispatch should use `publish_contract_version` first.

### Required v2 tables

Define the v2 required artifact set as:

- `tables/genomes.tsv`
- `tables/taxonomy.tsv`
- `tables/matched_sequences.tsv`
- `tables/matched_proteins.tsv`
- `tables/repeat_calls.tsv`
- `tables/repeat_call_codon_usage.tsv`
- `tables/repeat_context.tsv`
- `tables/run_params.tsv`
- `tables/accession_status.tsv`
- `tables/accession_call_counts.tsv`
- `tables/download_manifest.tsv`
- `tables/normalization_warnings.tsv`
- `summaries/status_summary.json`

`summaries/acquisition_validation.json` may be treated as an optional summary,
not as a hard import dependency.

### Required row-shape rules

Freeze these table rules:

- `genomes.tsv`, `matched_sequences.tsv`, and `matched_proteins.tsv` include an
  explicit `batch_id` column
- `matched_sequences.tsv` and `matched_proteins.tsv` contain only rows
  referenced by at least one `repeat_calls.tsv` record
- `repeat_calls.tsv` remains the single canonical call table and continues to
  carry `aa_sequence` and `codon_sequence`
- `repeat_call_codon_usage.tsv` uses one row per `(call_id, amino_acid, codon)`
- `repeat_context.tsv` includes:
  - `call_id`
  - `protein_id`
  - `sequence_id`
  - `aa_left_flank`
  - `aa_right_flank`
  - `nt_left_flank`
  - `nt_right_flank`
  - `aa_context_window_size`
  - `nt_context_window_size`

## Phase 2: Pipeline Changes In `../homorepeat_pipeline`

### Publish surface

Change the default published output so it no longer exposes:

- batch-scoped `sequences.tsv`
- batch-scoped `proteins.tsv`
- `cds.fna`
- `proteins.faa`
- per-finalizer duplicate call tables
- per-finalizer duplicate run-parameter tables

The pipeline may still generate broad sequence/protein inventories internally
for acquisition, translation, and detection. They should remain internal
workflow artifacts rather than default `publish/` contract artifacts.

### Flat hit-linked tables

Add a finalization step that derives:

- `matched_sequences.tsv`
- `matched_proteins.tsv`

from the set of IDs present in `repeat_calls.tsv`.

Use the current sequence and protein metadata schemas as the base, but emit only
rows linked to repeat calls. Preserve provenance columns such as accession,
taxon, gene group, translation metadata, and external identifiers.

### Codon usage and context

Add one merged final output for codon usage:

- `tables/repeat_call_codon_usage.tsv`

Stop relying on `calls/finalized/<method>/<repeat_residue>/<batch_id>/...`
fragments as the public contract.

Add one merged final output for compact context:

- `tables/repeat_context.tsv`

Context generation should use the same retained call-linked records and should
not require default publication of full FASTA bodies.

### Genome/status/provenance retention

Keep these outputs complete across all requested accessions, including zero-hit
accessions:

- `genomes.tsv`
- `taxonomy.tsv`
- `accession_status.tsv`
- `accession_call_counts.tsv`
- `download_manifest.tsv`
- `normalization_warnings.tsv`
- `run_manifest.json`

### Contract docs and runtime artifact maps

Update the pipeline docs and manifest artifact maps so the v2 layout is the
documented default contract.

## Phase 3: Web Import Changes In This Repo

### Published-run inspection

Update `apps/imports/services/published_run/` so it:

- recognizes `publish_contract_version`
- supports v1 legacy raw artifacts during migration
- validates v2 flat table locations
- stops treating FASTA files as required artifacts for v2
- stops crawling finalized codon-usage directories for v2

### Streamed import preparation

Keep the existing retained-ID preparation pattern:

- scan `repeat_calls.tsv`
- determine retained genome, sequence, and protein IDs

For v2, this preparation becomes simpler because `matched_sequences.tsv` and
`matched_proteins.tsv` are already pre-filtered to the retained subset. The
importer should stop re-deriving that subset from broader batch artifacts.

### Entity import

Update `apps/imports/services/import_run/` so v2 imports:

- import `matched_sequences.tsv` directly
- import `matched_proteins.tsv` directly
- do not read `cds.fna`
- do not read `proteins.faa`
- import codon usage from `repeat_call_codon_usage.tsv`
- import compact repeat context from `repeat_context.tsv`

The importer should no longer require stored full nucleotide or amino-acid
sequence bodies for the default path.

### Backward compatibility

Keep v1 support temporarily:

- v1 continues using the current batch-scoped raw contract
- v2 uses the new flat tables contract

Do not silently guess the contract from directory shape. Dispatch from
`publish_contract_version`.

## Phase 4: Browser And Model Changes

### Detail-page behavior

Update sequence and protein detail pages so they no longer depend on full stored
sequence bodies.

Preferred detail-page payload:

- identifiers and parent linkage
- sequence/protein lengths
- repeat-call summaries
- tract amino-acid sequence
- tract codon sequence
- compact left/right amino-acid and nucleotide flanks

### Data model expectations

If the browser models currently persist full sequence bodies only to support
detail pages, change the default v2 import path so those bodies are not
required.

If retaining the existing fields is operationally simpler during migration, they
may remain nullable/blank and be left empty for v2 imports.

## Test Plan

### Pipeline contract tests

Add or update pipeline tests to verify:

- v2 `run_manifest.json` contains `publish_contract_version=2`
- v2 publish output contains only the flat required table set
- default v2 publish output does not contain `cds.fna` or `proteins.faa`
- `matched_sequences.tsv` and `matched_proteins.tsv` contain only IDs referenced
  by `repeat_calls.tsv`
- zero-hit accessions still appear in genome and status tables
- `repeat_call_codon_usage.tsv` is complete and schema-valid
- `repeat_context.tsv` is complete and schema-valid

### Web import tests

Add or update web tests to verify:

- v2 published runs import successfully without FASTA artifacts
- v2 import does not walk batch-scoped acquisition directories
- v2 import stores the same repeat calls and codon-usage rows as before
- zero-hit accessions remain visible after import
- detail pages still render useful biological context without full stored
  sequence bodies
- v1 published runs remain importable during the migration window

### Performance checks

Measure both a legacy run and a v2 run on the same biological input and compare:

- published output size
- number of published files
- import wall-clock time
- importer I/O volume
- database row counts for sequences, proteins, repeat calls, and codon usage

The expected v2 outcome is lower size, lower I/O, and faster import with no
loss of repeat-call semantics.

## Defaults And Assumptions

- The stable user-facing contract is the default `publish/` tree, not optional
  diagnostics.
- Full analyzed sequence/protein inventories may still exist as internal
  workflow artifacts, but they are not part of the default v2 publish contract.
- Biological interpretation depends on repeat-linked metadata, codon usage,
  context, and provenance, not on publishing full duplicated FASTA payloads.
- Optional diagnostics, reports, or database bundles may still be emitted, but
  they are out of the core import contract.
