# Architecture

## Overview

HomoRepeat is a Nextflow workflow backed by Python CLIs. Nextflow owns orchestration, task fan-out, container/profile selection, and public output routing through workflow outputs. Python owns biological transformations, repeat detection, contract validation, SQLite import, and reporting calculations.

Primary entrypoints:

- `main.nf`: top-level workflow and public workflow-output wiring
- `workflows/*.nf`: stage-level workflow composition
- `modules/local/**/*.nf`: process wrappers around Python CLIs
- `src/homorepeat/cli/*.py`: task entrypoints
- `src/homorepeat/**`: implementation and shared libraries
- `lib/HomorepeatRuntimeArtifacts.groovy`: metadata finalization at `workflow.onComplete`

## End-to-End Data Flow

1. Planning
   - `PLAN_ACCESSION_BATCHES` reads `--accessions_file`, ignores blank/comment lines, removes duplicates, resolves accessions where needed, and writes deterministic batch manifests under `runs/<run_id>/internal/planning/`.
2. Acquisition
   - `DOWNLOAD_NCBI_BATCH` downloads one NCBI annotation package per batch.
   - `NORMALIZE_CDS_BATCH` extracts internal `genomes.tsv`, `taxonomy.tsv`, `sequences.tsv`, and `cds.fna`.
   - `TRANSLATE_CDS_BATCH` translates retained CDS records into internal `proteins.tsv` and `proteins.faa`.
   - `MERGE_ACQUISITION_BATCHES` runs only in `--acquisition_publish_mode merged`; its merged artifacts feed SQLite/report generation, not the default v2 public contract.
3. Detection and finalization
   - `DETECT_PURE`, `DETECT_THRESHOLD`, and `DETECT_SEED_EXTEND` run independently for each `batch_id x repeat_residue`.
   - `FINALIZE_CALL_CODONS` validates nucleotide slices against normalized CDS and writes finalized call, warning, and codon-usage fragments.
4. Contract reducers
   - `MERGE_CALL_TABLES` emits canonical `repeat_calls.tsv` and `run_params.tsv` for publication as `calls/repeat_calls.tsv` and `calls/run_params.tsv`.
   - `MERGE_CODON_USAGE_TABLES` emits `repeat_call_codon_usage.tsv` for publication under `tables/`.
   - `EXPORT_REPEAT_CONTEXT` emits `repeat_context.tsv` for publication under `tables/`.
   - `BUILD_ACCESSION_STATUS` builds accession status ledgers internally.
   - `EXPORT_PUBLISH_TABLES` emits the remaining v2 `tables/` and `summaries/` artifacts.
5. Optional merged-mode reporting
   - `BUILD_SQLITE` imports canonical flat files into SQLite.
   - `EXPORT_SUMMARY_TABLES`, `PREPARE_REPORT_TABLES`, and `RENDER_ECHARTS_REPORT` build report artifacts.
6. Metadata finalization
   - `workflow.onComplete` publishes launch metadata, run manifest, and stable links to Nextflow diagnostics.

## Public Contract vs Internal Artifacts

The v2 public contract is compact and table-first. It publishes:

- `calls/repeat_calls.tsv`
- `calls/run_params.tsv`
- `tables/*.tsv`
- `summaries/*.json`
- `metadata/*`

The workflow still generates broad internal artifacts such as batch `sequences.tsv`, `proteins.tsv`, `cds.fna`, `proteins.faa`, and finalized method fragments. Those artifacts are used for downstream reducers but are not published by default.

This separation keeps the public contract stable and small while preserving the internal data needed for validation and reporting. Public artifact destinations are assigned only in the entry workflow `publish:` section and top-level `output {}` block; reusable process modules emit files and directories without owning public contract paths.

## Workflow Topology

| Layer | Files | Responsibility |
| --- | --- | --- |
| Configuration | `nextflow.config`, `conf/*.config` | Supported Nextflow version, profiles, defaults, resource labels |
| Entry point | `main.nf` | Global workflow graph, public workflow-output wiring, completion hook |
| Subworkflows | `workflows/*.nf` | Acquisition, detection, and database/report composition |
| Processes | `modules/local/**/*.nf` | One operational task per process |
| Python CLIs | `src/homorepeat/cli/*.py` | Stable task interfaces used by Nextflow and tests |
| Shared Python | `src/homorepeat/**` | Algorithms, I/O, contracts, runtime helpers, DB/report logic |
| Metadata library | `lib/HomorepeatRuntimeArtifacts.groovy` | Final run metadata and manifest artifact discovery |

## Execution Model

### Profiles

- `docker`: standard operator path, local executor with process containers.
- `local`: host execution for tests and development.

### Fan-out units

- Planning is a singleton.
- Acquisition fans out by `batch_id`.
- Detection and codon finalization fan out by `batch_id x method x repeat_residue`.
- Contract reducers are fan-in tasks.
- SQLite and report tasks are singleton merged-mode tasks.

### Publish modes

`--acquisition_publish_mode raw` is the default. It produces the v2 contract and skips SQLite/report generation.

`--acquisition_publish_mode merged` additionally builds:

- `publish/database/homorepeat.sqlite`
- `publish/database/sqlite_validation.json`
- `publish/reports/*`

The v2 `tables/` and `summaries/` outputs are published in both modes.

## Repository Layout

| Path | Contents |
| --- | --- |
| `main.nf` | Top-level workflow and workflow-output publication |
| `workflows/` | Stage-level subworkflows |
| `modules/local/` | Nextflow process wrappers |
| `src/homorepeat/acquisition/` | NCBI package inspection, normalization, translation helpers |
| `src/homorepeat/detection/` | Repeat methods, codon slicing, repeat-context extraction |
| `src/homorepeat/contracts/` | Shared table schemas and row validators |
| `src/homorepeat/runtime/` | Run manifests, accession status, publish reducers, benchmark helpers |
| `src/homorepeat/db/` | SQLite import and validation |
| `src/homorepeat/reporting/` | Summary and report generation |
| `src/homorepeat/io/` | TSV and FASTA helpers |
| `containers/` | Runtime image definitions |
| `conf/` | Nextflow base and profile config |
| `examples/` | Example accessions and parameter files |
| `tests/` | Unit, CLI, and workflow regression tests |

## Design Principles

- Flat files are the source of truth; SQLite and reports are derived artifacts.
- Public contract tables are explicit, validated, and versioned.
- Public artifacts are published through workflow outputs in `main.nf`; processes emit structured outputs for downstream composition.
- Internal broad FASTA artifacts are not part of the default public contract.
- Failed runs still try to publish metadata and Nextflow diagnostics.
- Tests mirror the architecture: pure unit tests for algorithms, CLI tests for task contracts, workflow tests for Nextflow wiring and output shape.
