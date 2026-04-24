# Data Contracts

## Scope

This document describes the current machine-facing inputs and published outputs of the main Nextflow workflow. It is intentionally tied to what the code emits today, not to the frozen planning material under `docs/implementation/`.

General rules:

- tabular artifacts are TSV with headers
- text artifacts are UTF-8
- column names are part of the contract
- empty values are encoded as empty strings unless noted otherwise
- all three detection methods share the same repeat-call schema

## Workflow Inputs

### `--accessions_file`

Plain-text file, one assembly accession per line.

Behavior:

- blank lines are ignored
- lines starting with `#` are ignored
- duplicate accession lines are removed while preserving order
- the planner may resolve non-`GCF_` accessions to a different downloadable accession

### `--taxonomy_db`

Path to an existing `taxon-weaver` SQLite database. This is a runtime dependency, not a row-based biological input.

### `-params-file`

Optional JSON file for parameter overrides. The resolved parameter payload is recorded in `publish/metadata/run_manifest.json`.

## Canonical Identifiers

The workflow uses source-backed text IDs rather than opaque short hashes.

- `genome_id`
  - shape: `assembly_accession`
  - example: `GCF_000001405.40`
- `taxon_id`
  - shape: NCBI taxid as text
- `sequence_id`
  - shape: `assembly_accession::primary_sequence_key`
  - notes: `primary_sequence_key` usually comes from transcript/CDS identity; it expands when source-backed disambiguation is required
- `protein_id`
  - shape: `sequence_id::protein`
- `call_id`
  - shape: `method::protein_id::repeat_residue::start-end`

These IDs are the stable join keys across TSVs, FASTA headers, and SQLite tables.

## Planning Artifacts

Planning artifacts are written under `runs/<run_id>/internal/planning/`.

### `accession_batches.tsv`

Row unit: one selected accession assigned to one operational batch.

Columns:

- `batch_id`
- `assembly_accession`

### `accession_resolution.tsv`

Row unit: one requested accession.

Columns:

- `requested_accession`
- `resolved_accession`
- `resolution_reason`
- `source_database`
- `current_accession`
- `paired_accession`
- `annotation_status`

### `selected_accessions.txt`

Plain-text list of the resolved accessions that will actually be batched and downloaded.

## Published Acquisition Artifacts

### Publish locations

- `raw` mode publishes batch-scoped acquisition artifacts under `publish/acquisition/batches/<batch_id>/`
- `merged` mode publishes flat acquisition artifacts under `publish/acquisition/`

The file schemas are the same in both modes. Only the directory layout changes.

### `genomes.tsv`

Row unit: one downloaded assembly/genome.

Columns:

- `genome_id`
- `source`
- `accession`
- `genome_name`
- `assembly_type`
- `taxon_id`
- `assembly_level`
- `species_name`
- `notes`

### `taxonomy.tsv`

Row unit: one taxonomic node from the lineage materialized for the selected assemblies.

Columns:

- `taxon_id`
- `taxon_name`
- `parent_taxon_id`
- `rank`
- `source`

### `sequences.tsv`

Row unit: one normalized CDS retained as a translation source.

Columns:

- `sequence_id`
- `genome_id`
- `sequence_name`
- `sequence_length`
- `gene_symbol`
- `transcript_id`
- `isoform_id`
- `assembly_accession`
- `taxon_id`
- `source_record_id`
- `protein_external_id`
- `translation_table`
- `gene_group`
- `linkage_status`
- `partial_status`

### `proteins.tsv`

Row unit: one retained translated protein.

Columns:

- `protein_id`
- `sequence_id`
- `genome_id`
- `protein_name`
- `protein_length`
- `gene_symbol`
- `translation_method`
- `translation_status`
- `assembly_accession`
- `taxon_id`
- `gene_group`
- `protein_external_id`

### `cds.fna`

FASTA file keyed by `sequence_id`.

### `proteins.faa`

FASTA file keyed by `protein_id`.

### `download_manifest.tsv`

Row unit: one requested accession in one batch.

Columns:

- `batch_id`
- `assembly_accession`
- `download_status`
- `package_mode`
- `download_path`
- `rehydrated_path`
- `checksum`
- `file_size_bytes`
- `download_started_at`
- `download_finished_at`
- `notes`

`download_path` and `rehydrated_path` are provenance fields. They are intentionally not repeated in the canonical biological tables.

### `normalization_warnings.tsv`

Row unit: one warning raised during normalization, translation, or accession-level acquisition validation.

Columns:

- `warning_code`
- `warning_scope`
- `warning_message`
- `batch_id`
- `genome_id`
- `sequence_id`
- `protein_id`
- `assembly_accession`
- `source_file`
- `source_record_id`

### `acquisition_validation.json`

Machine-readable validation summary for either one batch (`raw` mode) or the merged acquisition bundle (`merged` mode).

Top-level fields:

- `status`
- `scope`
- `batch_id` when batch-scoped
- `counts`
- `checks`
- `failed_accessions`
- `warning_summary`
- `notes`

## Detection and Finalization Artifacts

### Batch-local finalized directories

Per-method finalized outputs are published under:

- `publish/calls/finalized/<method>/<repeat_residue>/<batch_id>/`

Each batch directory contains:

- `final_<method>_<repeat_residue>_<batch_id>_calls.tsv`
- `final_<method>_<repeat_residue>_<batch_id>_run_params.tsv`
- `final_<method>_<repeat_residue>_<batch_id>_codon_warnings.tsv`
- `final_<method>_<repeat_residue>_<batch_id>_codon_usage.tsv`

### `repeat_calls.tsv`

Canonical merged call table published at `publish/calls/repeat_calls.tsv`.

Row unit: one detected homorepeat tract.

Columns:

- `call_id`
- `method`
- `genome_id`
- `taxon_id`
- `sequence_id`
- `protein_id`
- `start`
- `end`
- `length`
- `repeat_residue`
- `repeat_count`
- `non_repeat_count`
- `purity`
- `aa_sequence`
- `codon_sequence`
- `codon_metric_name`
- `codon_metric_value`
- `window_definition`
- `template_name`
- `merge_rule`
- `score`

Notes:

- coordinates are 1-based and inclusive in amino-acid space
- `repeat_count + non_repeat_count = length`
- `codon_sequence` is empty when the codon slice cannot be validated
- `codon_metric_name`, `codon_metric_value`, `template_name`, and `score` are currently emitted as empty strings
- `method` is one of `pure`, `threshold`, or `seed_extend`

### `run_params.tsv`

Canonical merged method-parameter table published at `publish/calls/run_params.tsv`.

Row unit: one parameter for one `method x repeat_residue`.

Columns:

- `method`
- `repeat_residue`
- `param_name`
- `param_value`

Rows are unique on `method + repeat_residue + param_name`.

## Status and Metadata Artifacts

### `accession_status.tsv`

Published at `publish/status/accession_status.tsv`.

Row unit: one requested accession.

Columns:

- `assembly_accession`
- `batch_id`
- `download_status`
- `normalize_status`
- `translate_status`
- `detect_status`
- `finalize_status`
- `terminal_status`
- `failure_stage`
- `failure_reason`
- `n_genomes`
- `n_proteins`
- `n_repeat_calls`
- `notes`

Current `terminal_status` values:

- `completed`
- `completed_no_calls`
- `failed`
- `skipped_upstream_failed`

### `accession_call_counts.tsv`

Published at `publish/status/accession_call_counts.tsv`.

Row unit: one accession x method x repeat residue.

Columns:

- `assembly_accession`
- `batch_id`
- `method`
- `repeat_residue`
- `detect_status`
- `finalize_status`
- `n_repeat_calls`

### `status_summary.json`

Published at `publish/status/status_summary.json`.

Top-level fields:

- `status`
- `counts`
- `terminal_status_counts`

`status` is currently `success` or `partial`.

### `launch_metadata.json`

Published at `publish/metadata/launch_metadata.json`.

Contains launch-time paths and execution context, including:

- run identity and timestamps
- profile
- acquisition publish mode
- input paths
- run/work/publish paths
- Nextflow run name and resume flag

### `run_manifest.json`

Published at `publish/metadata/run_manifest.json`.

Contains the current machine-readable run summary, including:

- run identity and timestamps
- acquisition publish mode
- git revision
- input paths relative to the repo when possible
- `params.params_file_values`
- `params.effective_values`
- detected methods and repeat residues
- published artifact paths

### `publish/metadata/nextflow/*`

Stable published links to the Nextflow diagnostics when available:

- `report.html`
- `timeline.html`
- `dag.html`
- `trace.txt`

## SQLite Artifact

When `--acquisition_publish_mode merged`, the workflow also publishes:

- `publish/database/homorepeat.sqlite`
- `publish/database/sqlite_validation.json`

The SQLite schema contains:

- `taxonomy`
- `genomes`
- `sequences`
- `proteins`
- `run_params`
- `repeat_calls`

`sqlite_validation.json` records:

- `status`
- `scope`
- `counts`
- `expected_counts`
- `checks`
