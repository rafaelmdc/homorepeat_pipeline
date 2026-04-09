# Contracts

## Purpose

This document defines the stable file and schema contracts used across the HomoRepeat workflow.

A contract is a promise:
- what a step receives
- what a step emits
- which columns are required
- which IDs must remain stable

If implementation changes but the contract remains valid, downstream steps should continue to work.

---

## General rules

### 1. Tabular intermediates use TSV
Unless otherwise stated, structured intermediate outputs should be TSV files with headers.

### 2. UTF-8 everywhere
All text outputs must be UTF-8 encoded.

### 3. One row = one biological unit
Each table must define its row unit clearly.

### 4. Stable column names
Column names are part of the contract and should not change casually.

### 5. Missing values
Missing values must be encoded consistently as empty fields unless a documented sentinel is required.

### 6. Method outputs must be schema-compatible
Pure, threshold, and seed-extend outputs must share the same call schema.

---

## Canonical identifiers

The current canonical identifiers are:

- `genome_id`
- `taxon_id`
- `sequence_id`
- `protein_id`
- `call_id`

Rules:
- canonical IDs are source-derived text identifiers, not truncated hash IDs
- canonical IDs must remain stable across reruns when the same accession and source annotations produce the same retained records
- downstream tables should prefer internal IDs over fragile filename parsing
- external identifiers may be preserved in separate columns

Current shapes:
- `genome_id = assembly_accession`
- `taxon_id = NCBI taxid as text`
- `sequence_id = assembly_accession::primary_sequence_key`
- `protein_id = sequence_id::protein`
- `call_id = method::protein_id::repeat_residue::start-end`

Notes:
- `primary_sequence_key` is usually the resolved transcript identifier and falls back to source-backed CDS identity when transcript-level identity is not available
- when transcript-level identity is ambiguous within one accession, the normalized `sequence_id` expands to include source-backed disambiguation fields instead of collapsing records into a short hash collision
- external identifiers such as `transcript_id`, `protein_external_id`, and `source_record_id` are preserved as explicit columns rather than encoded into opaque reversible IDs

---

## Acquisition contract

Workflow driver note:
- the current Nextflow pipeline starts from a plain-text accession list, one assembly accession per line
- downstream acquisition normalization still emits the flat canonical artifacts documented below
- taxonomy DB location is treated as a runtime dependency, not a biological input record

### Input: `acquisition_targets.tsv`

One row per acquisition target to normalize into the workflow contracts.

Required columns:
- `source`
- `genome_name`
- `taxon_id`

Source-specific required columns:
- for `source=ncbi_datasets`: `accession`
- for `source=local`: at least one of `cds_fasta` or `protein_fasta`

Optional columns:
- `accession`
- `assembly_type`
- `assembly_level`
- `species_name`
- `taxon_name`
- `parent_taxon_id`
- `annotation_gff`
- `cds_fasta`
- `protein_fasta`
- `notes`

Rules:
- `source` must currently be one of: `ncbi_datasets`, `local`
- rows in `acquisition_targets.tsv` are intent records, not downstream biological entities
- local-mode paths must be readable from the execution environment
- local mode should prefer `cds_fasta` plus `annotation_gff` when translation-driven normalization is desired
- NCBI download/archive provenance lives in `download_manifest.tsv`, not repeated inside `genomes.tsv`
- stable published acquisition artifact locations are declared in `publish/metadata/run_manifest.json`
- `merged` runs publish the legacy flat acquisition bundle under `publish/acquisition/`
- `raw` runs publish acquisition artifacts under `publish/acquisition/batches/<batch_id>/`

### Output: `genomes.tsv`

One row per genome or assembly-level unit.

Required columns:
- `genome_id`
- `source`
- `accession`
- `genome_name`
- `assembly_type`
- `taxon_id`
- `assembly_level`
- `species_name`
- `notes`

Rules:
- `genome_id` is the real assembly accession used as the canonical relational key
- all columns above are part of the stable emitted schema, even if a specific value is empty

---

## Taxonomy contract

### Output: `taxonomy.tsv`

One row per taxonomic unit.

Required columns:
- `taxon_id`
- `taxon_name`
- `parent_taxon_id`
- `rank`
- `source`

Optional columns:
- none

---

## Sequence contract

### Output: `sequences.tsv`

One row per retained CDS or other nucleotide sequence used as a translation source.

Required columns:
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

Rules:
- all columns above are part of the canonical schema; some biologically optional values may still be emitted as empty strings
- `sequence_id` is source-derived and should be human-auditable from the accession plus CDS identity
- row-level sequence tables must not repeat canonical FASTA paths; merged runs use `publish/acquisition/cds.fna`, while raw runs resolve the batch-scoped CDS FASTA through `publish/metadata/run_manifest.json` and `publish/acquisition/batches/<batch_id>/`

---

## Protein contract

### Output: `proteins.tsv`

One row per locally translated or explicitly provided protein.

Required columns:
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

Rules:
- all columns above are part of the canonical schema; some biologically optional values may still be emitted as empty strings
- `protein_id` is derived from `sequence_id` and is not an independent opaque hash
- row-level protein tables must not repeat canonical FASTA paths; merged runs use `publish/acquisition/proteins.faa`, while raw runs resolve the batch-scoped protein FASTA through `publish/metadata/run_manifest.json` and `publish/acquisition/batches/<batch_id>/`

---

## Detection call contract

### Outputs
- `pure_calls.tsv`
- `seed_extend_calls.tsv`
- `threshold_calls.tsv`
- `repeat_calls.tsv`

Each row represents one detected homorepeat region.

Required columns:
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

### Rules
- all columns above are part of the canonical merged call schema; values such as `codon_sequence`, `codon_metric_name`, `codon_metric_value`, `template_name`, `merge_rule`, and `score` may be empty when a method or stage does not populate them
- `method` must be one of: `pure`, `threshold`, `seed_extend`
- `repeat_calls.tsv` is the canonical merged export for downstream database and app ingestion
- `start` and `end` use the same coordinate system across all methods
- `repeat_residue` is the targeted amino-acid residue for the call
- `length` is the total tract length, including non-target residues if the method definition allows them
- `purity` is a numeric fraction from 0 to 1
- `aa_sequence` must reflect the called tract sequence exactly
- `call_id` is source-derived from `method`, `protein_id`, `repeat_residue`, and amino-acid coordinates
- for `pure`, `aa_sequence` is expected to be a contiguous run of `repeat_residue`
- for `threshold`, `window_definition` should record the qualifying sliding-window rule, such as `Q6/8`
- for `seed_extend`, `window_definition` should record both seed and extend rules, such as `seed:Q6/8|extend:Q8/12`
- row-level repeat-call tables must not repeat source FASTA paths; call provenance flows through stable biological identifiers plus the published acquisition artifacts

---

## Finalized detection output contract

Method-specific finalized outputs publish under:

- `publish/calls/finalized/<method>/<repeat_residue>/<batch_id>/`

Expected finalized artifacts:
- `final_<method>_<repeat_residue>_calls.tsv`
- `final_<method>_<repeat_residue>_run_params.tsv`
- `final_<method>_<repeat_residue>_codon_warnings.tsv`
- `final_<method>_<repeat_residue>_codon_usage.tsv`

Rules:
- `publish/calls/` remains the canonical merged interface for downstream database and reporting stages
- finalized method outputs are method-specific and may exist for multiple residues in the same run
- finalized method outputs are grouped by `batch_id` inside each method and residue bucket
- finalized call tables must still satisfy the shared detection call contract

---

## Codon usage contract

### Output: `codon_usage.tsv`

One row per finalized call, amino acid, and codon.

Required columns:
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
- `codon_fraction` is computed within each `call_id` plus `amino_acid` group
- `codon_fraction` values within one `call_id` plus `amino_acid` group must sum to `1`
- codon usage is derived only from validated `codon_sequence` values
- `codon_metric_name` and `codon_metric_value` remain reserved compatibility fields on the main call row and may remain empty

---

## Method-specific parameter record contract

### Output: `run_params.tsv`

One row per method, repeat residue, and configuration parameter.

Required columns:
- `method`
- `repeat_residue`
- `param_name`
- `param_value`

Purpose:
- preserve method settings used in a given run
- support traceability
- make database builds auditable

Rules:
- `repeat_residue` is the amino-acid target for the parameter block
- `repeat_residue` must be a single uppercase amino-acid symbol
- `run_params.tsv` must not encode `repeat_residue` as a `param_name`; residue scoping lives in the dedicated column
- `(method, repeat_residue, param_name)` must be unique in the canonical merged output
- finalized `final_<method>_<repeat_residue>_run_params.tsv` files must contain only rows whose `repeat_residue` matches the path component

---

## Status artifact contracts

### Output: `publish/status/accession_status.tsv`

One row per requested assembly accession.

Required columns:
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

Rules:
- `n_repeat_calls` is the aggregate count across all enabled methods and repeat residues for that accession
- `terminal_status` is the accession-level summary state for the whole run
- `finalize_status=skipped` is valid when detection completed successfully but emitted no calls for that accession across the enabled methods and residues

### Output: `publish/status/accession_call_counts.tsv`

One row per requested assembly accession, observed method, and observed repeat residue.

Required columns:
- `assembly_accession`
- `batch_id`
- `method`
- `repeat_residue`
- `detect_status`
- `finalize_status`
- `n_repeat_calls`

Rules:
- rows are emitted for method plus repeat-residue combinations observed in the run-level detection status inputs or finalized call fragments
- `n_repeat_calls` is scoped to one accession plus method plus repeat-residue combination
- `finalize_status=skipped` is valid when the detect stage succeeded for that accession plus method plus repeat-residue combination but emitted no calls, so no finalize task was launched
- this table is a companion detail artifact; `accession_status.tsv` remains the accession-level operational ledger

### Output: `publish/status/status_summary.json`

Run-level accession-status summary.

Required top-level keys:
- `status`
- `counts`
- `terminal_status_counts`

Required `counts` keys:
- `n_requested_accessions`
- `n_completed`
- `n_completed_no_calls`
- `n_failed`
- `n_skipped_upstream_failed`

Rules:
- `status` is `success` when no accession finished as `failed` or `skipped_upstream_failed`
- `status` is `partial` when at least one accession finished as `failed` or `skipped_upstream_failed`
- `terminal_status_counts` is a frequency map keyed by `terminal_status` values observed in `accession_status.tsv`

---

## Run manifest contract

### Output: `publish/metadata/run_manifest.json`

Required top-level keys:
- `run_id`
- `status`
- `started_at_utc`
- `finished_at_utc`
- `profile`
- `acquisition_publish_mode`
- `git_revision`
- `inputs`
- `paths`
- `params`
- `enabled_methods`
- `repeat_residues`
- `artifacts`

Rules:
- `acquisition_publish_mode` must be one of: `raw`, `merged`
- `params.detection` is derived from the canonical published `calls/run_params.tsv` when present
- `params.detection` is shaped as `method -> repeat_residue -> param_name -> param_value`
- `enabled_methods` is the sorted list of methods present in `params.detection`
- in `raw` mode, `artifacts.acquisition.batches_root`, when present, points to `publish/acquisition/batches`
- in `merged` mode, `artifacts.acquisition.*` points to the flat acquisition bundle under `publish/acquisition/`
- `artifacts.calls.finalized_root`, when present, points to `publish/calls/finalized`
- `artifacts.metadata.launch_metadata_json`, when present, points to `publish/metadata/launch_metadata.json`
- `artifacts.metadata.nextflow_report_html`, `artifacts.metadata.nextflow_timeline_html`, and `artifacts.metadata.nextflow_dag_html`, when present, point to `publish/metadata/nextflow/`
- `artifacts.metadata.trace_txt`, when present, points to `publish/metadata/nextflow/trace.txt`
- files under `publish/metadata/nextflow/` may be published as relative symlinks into `runs/<run_id>/internal/nextflow/`
- `repeat_residues` is the sorted set of `repeat_residue` column values present in the published run params
- `artifacts.status.accession_call_counts_tsv`, when present, points to `publish/status/accession_call_counts.tsv`
- artifact paths are stored relative to the run root when possible; absolute paths are allowed when the publish root lives outside `runs/<run_id>/`
- `params.params_file_values` may be empty when no params file was provided or when the supplied file is not JSON
- `params.effective_values` records the effective runtime parameter subset captured at manifest write time and may therefore differ from `params.params_file_values` when CLI overrides were used

### Output: `publish/metadata/launch_metadata.json`

Launch-time operator metadata captured from the workflow runtime.

Required top-level keys:
- `run_id`
- `status`
- `started_at_utc`
- `finished_at_utc`
- `profile`
- `acquisition_publish_mode`
- `launch_dir`
- `project_dir`
- `inputs`
- `paths`
- `nextflow`

Required `inputs` keys:
- `accessions_file`
- `taxonomy_db`
- `params_file`

Required `paths` keys:
- `run_root`
- `publish_root`
- `work_dir`
- `nextflow_log`
- `trace_txt`

Required `nextflow` keys:
- `run_name`
- `success`
- `resume_used`

Rules:
- `acquisition_publish_mode` must be one of: `raw`, `merged`
- `paths.trace_txt` points to the live trace file under `runs/<run_id>/internal/nextflow/trace.txt`
- `launch_metadata.json` is an operator-facing runtime record; `run_manifest.json` remains the authoritative published artifact index

---

## Acquisition side-artifact contracts

### Output: `download_manifest.tsv`

One row per requested assembly accession download attempt.

Required columns:
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

Rules:
- this artifact is published once per batch in `raw` mode and as one merged table in `merged` mode
- `download_status` records the batch-local download outcome for one accession
- `package_mode` records how the NCBI package was fetched for that accession

### Output: `normalization_warnings.tsv`

One row per structured acquisition or normalization warning.

Required columns:
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

Rules:
- this artifact is published once per batch in `raw` mode and as one merged table in `merged` mode
- blank identifier fields are allowed when a warning applies at a broader scope than genome, sequence, or protein
- `warning_code` is the stable machine-readable category
- `warning_message` is an operator-facing explanation and may evolve without changing the warning category

### Output: `acquisition_validation.json`

Stable acquisition validation summary for one batch or one merged acquisition bundle.

Required top-level keys:
- `status`
- `scope`
- `counts`
- `checks`
- `failed_accessions`
- `warning_summary`
- `notes`

Optional top-level keys:
- `batch_id`

Required `counts` keys:
- `n_selected_assemblies`
- `n_downloaded_packages`
- `n_genomes`
- `n_sequences`
- `n_proteins`
- `n_warning_rows`

Rules:
- `status` is `pass` when all `checks` are true and there are no warning rows or failed accessions
- `status` is `warn` when all `checks` are true but warning rows or failed accessions are present
- `status` is `fail` when any `checks` entry is false
- `scope` identifies whether the payload summarizes one batch or the merged acquisition output
- `batch_id` is present only for batch-scoped payloads

---

## Website planning note

The pipeline release does not implement a cross-run merged browser layer.

Any future website or database import logic that collapses rows across runs is outside
the current runtime contract and must be documented separately from these published
artifact contracts.

---

## Summary table contract

### Output: `summary_by_taxon.tsv`

One row per taxon and method.

Required columns:
- `method`
- `repeat_residue`
- `taxon_id`
- `taxon_name`
- `n_genomes`
- `n_proteins`
- `n_calls`
- `mean_length`
- `mean_purity`

Optional columns:
- `codon_metric_name`
- `mean_codon_metric`
- `median_length`
- `max_length`
- `mean_start_fraction`

---

## Regression input contract

### Output: `regression_input.tsv`

One row per grouped observation used in downstream regression.

Required columns:
- `method`
- `repeat_residue`
- `group_label`
- `repeat_length`
- `n_observations`

Optional columns:
- `codon_metric_name`
- `mean_codon_metric`
- `filtered_max_length`
- `transformed_codon_metric`

---

## Reporting contract

### Outputs
- `summary_by_taxon.tsv`
- `regression_input.tsv`
- `echarts_report.html`
- `echarts_options.json`
- `echarts.min.js`

Rules:
- all report outputs must be derivable from finalized tables or SQLite, not raw detection code
- `echarts_options.json` must be a valid JSON object keyed by chart name
- `echarts_report.html` must be reproducible from the JSON payload and analysis-ready tables
- `echarts_report.html` must render the required chart blocks present in `echarts_options.json`
- `echarts.min.js` must be shipped locally with the report bundle so the HTML report works without a CDN

---

## SQLite table contract

The initial v1 database schema owns the following tables:
- `genomes`
- `taxonomy`
- `sequences`
- `proteins`
- `repeat_calls`
- `run_params`

Rules:
- `repeat_calls` is the unified import target for `pure_calls.tsv`, `threshold_calls.tsv`, and `seed_extend_calls.tsv`
- flat files remain the canonical exchange artifacts even after import
- table and index definitions live under `src/homorepeat/resources/sql/sqlite/`

---

## SQLite ownership rules

### Database build philosophy
SQLite is not the source of truth during active computation.

The source of truth is:
- standardized flat outputs
- schema definition files
- parameter records

SQLite is the integrated build artifact.

### Import rules
- raw method outputs are imported only after validation
- indexes should be created after bulk import
- imports should run in transactions
- row count checks should be performed after import

---

## Validation rules

Every pipeline run should validate at least:

### Detection-level checks
- required columns exist
- no invalid method names
- `start <= end`
- `length > 0`
- `0 <= purity <= 1`

### Relational checks
- every `protein_id` in calls exists in proteins
- every `sequence_id` in proteins exists in sequences
- every `genome_id` exists in genomes

### Summary checks
- grouped counts are non-negative
- no impossible means
- method-level totals reconcile with source call tables

---

## File naming conventions

Preferred names:
- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- `proteins.tsv`
- `pure_calls.tsv`
- `seed_extend_calls.tsv`
- `threshold_calls.tsv`
- `run_params.tsv`
- `summary_by_taxon.tsv`
- `regression_input.tsv`
- `homorepeat.sqlite`

Avoid embedding critical metadata only in filenames.

---

## Contract evolution policy

Contracts may evolve, but changes must be explicit.

If a contract changes:
- update this file
- update tests
- update downstream scripts
- document the versioned change in the changelog or roadmap

Do not silently change column names or semantics.
