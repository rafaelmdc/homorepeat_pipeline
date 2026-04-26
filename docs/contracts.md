# Data Contracts

## Scope

This document describes the current machine-facing inputs and default published outputs of the main Nextflow workflow. The default publish contract is version `2`.

General rules:

- tabular artifacts are UTF-8 TSV with headers
- JSON artifacts are UTF-8 JSON
- empty values are encoded as empty strings unless noted otherwise
- column order is part of the public contract
- all repeat-detection methods share the same `repeat_calls.tsv` schema

## Workflow Inputs

### `--accessions_file`

Plain-text file with one assembly accession per line.

Behavior:

- blank lines are ignored
- lines beginning with `#` are ignored
- duplicate accession lines are removed while preserving order
- the planner may resolve non-RefSeq accessions to a downloadable annotated accession

### `--taxonomy_db`

Path to an existing `taxon-weaver` SQLite database. This is required for taxonomy lineage materialization.

### `-params-file`

Optional JSON parameter file. Parsed values and effective values are recorded in `publish/metadata/run_manifest.json`.

## Canonical Identifiers

| Identifier | Shape | Notes |
| --- | --- | --- |
| `genome_id` | assembly accession | Example: `GCF_000001405.40` |
| `taxon_id` | NCBI taxid as text | Materialized via `taxon-weaver` |
| `sequence_id` | `assembly_accession::primary_sequence_key` | Stable normalized CDS key |
| `protein_id` | `sequence_id::protein` | Local translation product identifier |
| `call_id` | `method::protein_id::repeat_residue::start-end` | Stable repeat-call key |

These IDs are the join keys across calls, tables, context, SQLite, and report artifacts.

## Internal Planning Artifacts

Planning artifacts are written under `runs/<run_id>/internal/planning/`.

### `accession_batches.tsv`

Columns:

- `batch_id`
- `assembly_accession`

### `accession_resolution.tsv`

Columns:

- `requested_accession`
- `resolved_accession`
- `resolution_reason`
- `source_database`
- `current_accession`
- `paired_accession`
- `annotation_status`

### `selected_accessions.txt`

Resolved accessions that will be downloaded.

## Default Published Layout

Default public outputs live under `runs/<run_id>/publish/`:

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

The default v2 contract does not publish:

- `publish/acquisition/`
- `publish/status/`
- `publish/calls/finalized/`
- `cds.fna`
- `proteins.faa`

Those broad artifacts remain internal execution products.

## Calls

### `calls/repeat_calls.tsv`

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

Rules:

- coordinates are 1-based and inclusive in amino-acid space
- `repeat_count + non_repeat_count = length`
- `aa_sequence` length equals `length`
- `method` is `pure`, `threshold`, or `seed_extend`
- `codon_sequence` is empty when codon validation fails

### `calls/run_params.tsv`

Row unit: one parameter for one `method x repeat_residue`.

Columns:

- `method`
- `repeat_residue`
- `param_name`
- `param_value`

Rows are unique on `method + repeat_residue + param_name`.

## V2 Tables

### `tables/genomes.tsv`

Row unit: one downloaded assembly/genome.

Columns:

- `batch_id`
- `genome_id`
- `source`
- `accession`
- `genome_name`
- `assembly_type`
- `taxon_id`
- `assembly_level`
- `species_name`
- `notes`

### `tables/taxonomy.tsv`

Row unit: one taxonomic node from materialized lineages.

Columns:

- `taxon_id`
- `taxon_name`
- `parent_taxon_id`
- `rank`
- `source`

### `tables/matched_sequences.tsv`

Row unit: one normalized CDS sequence referenced by at least one repeat call.

Columns:

- `batch_id`
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

### `tables/matched_proteins.tsv`

Row unit: one translated protein referenced by at least one repeat call.

Columns:

- `batch_id`
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

### `tables/repeat_call_codon_usage.tsv`

Row unit: one `(call_id, amino_acid, codon)` observation summary.

Columns:

- `call_id`
- `method`
- `repeat_residue`
- `sequence_id`
- `protein_id`
- `amino_acid`
- `codon`
- `codon_count`
- `codon_fraction`

Rules:

- `codon` is DNA alphabet and length 3
- `codon_count >= 1`
- `0 <= codon_fraction <= 1`
- rows are emitted only for calls with validated `codon_sequence`

### `tables/repeat_context.tsv`

Row unit: one repeat call.

Columns:

- `call_id`
- `protein_id`
- `sequence_id`
- `aa_left_flank`
- `aa_right_flank`
- `nt_left_flank`
- `nt_right_flank`
- `aa_context_window_size`
- `nt_context_window_size`

Defaults:

- amino-acid flank window: `20`
- nucleotide flank window: `60`

Flanks are clipped at sequence boundaries. This table replaces public full-FASTA publication for repeat detail context.

### `tables/download_manifest.tsv`

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

### `tables/normalization_warnings.tsv`

Row unit: one acquisition, normalization, translation, or validation warning.

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

### `tables/accession_status.tsv`

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

### `tables/accession_call_counts.tsv`

Row unit: one accession x method x repeat residue.

Columns:

- `assembly_accession`
- `batch_id`
- `method`
- `repeat_residue`
- `detect_status`
- `finalize_status`
- `n_repeat_calls`

## Summaries

### `summaries/status_summary.json`

Top-level fields:

- `status`
- `counts`
- `terminal_status_counts`

### `summaries/acquisition_validation.json`

Top-level fields:

- `status`
- `scope`
- `batch_id`
- `counts`
- `checks`
- `failed_accessions`
- `warning_summary`
- `notes`

## Metadata

### `metadata/launch_metadata.json`

Contains:

- run identity and timestamps
- profile
- publish contract version
- acquisition publish mode
- input paths
- run/work/publish paths
- Nextflow run name and resume flag

### `metadata/run_manifest.json`

Contains:

- run identity and timestamps
- `publish_contract_version`
- acquisition publish mode
- git revision
- input paths
- effective params and params-file values
- detected methods and repeat residues
- discovered published artifact paths

`run_manifest.json` is the authoritative machine-readable index of a run.

### `metadata/nextflow/*`

Stable links/copies for Nextflow diagnostics when available:

- `report.html`
- `timeline.html`
- `dag.html`
- `trace.txt`

## Optional Merged-Mode Artifacts

When `--acquisition_publish_mode merged`, the workflow additionally publishes:

- `database/homorepeat.sqlite`
- `database/sqlite_validation.json`
- `reports/summary_by_taxon.tsv`
- `reports/regression_input.tsv`
- `reports/echarts_options.json`
- `reports/echarts_report.html`
- `reports/echarts.min.js`

The SQLite schema contains:

- `taxonomy`
- `genomes`
- `sequences`
- `proteins`
- `run_params`
- `repeat_calls`

SQLite and reports are derived artifacts. The public flat files remain the primary contract.
