# Architecture

## Overview

HomoRepeat is a Nextflow pipeline with a Python package behind each scientific step.

- Workflow entrypoint: `main.nf`
- Workflow orchestration: `workflows/*.nf` and `modules/local/*.nf`
- Scientific and contract logic: `src/homorepeat/**`
- Runtime metadata finalization: `lib/HomorepeatRuntimeArtifacts.groovy`

The split is deliberate:

- Nextflow decides what runs, how work fans out, which profile is active, and what gets published.
- Python CLIs own biological normalization, repeat detection, contract validation, SQLite import, and reporting calculations.

## End-to-End Flow

1. Planning
   - `PLAN_ACCESSION_BATCHES` reads `--accessions_file`, removes blank/comment lines and duplicates, optionally resolves requested accessions to downloadable accessions, and writes deterministic batches.
2. Acquisition
   - `DOWNLOAD_NCBI_BATCH` downloads one NCBI package per batch.
   - `NORMALIZE_CDS_BATCH` extracts canonical `genomes.tsv`, `taxonomy.tsv`, `sequences.tsv`, and `cds.fna`.
   - `TRANSLATE_CDS_BATCH` translates retained CDS records into `proteins.tsv` and `proteins.faa`.
   - `MERGE_ACQUISITION_BATCHES` runs only when `--acquisition_publish_mode merged`.
3. Detection and finalization
   - `DETECT_PURE`, `DETECT_THRESHOLD`, and `DETECT_SEED_EXTEND` run independently for each `batch_id x repeat_residue`.
   - `FINALIZE_CALL_CODONS` enriches each call table with validated codon slices and writes per-call codon warning/usage files.
4. Consolidation
   - `MERGE_CALL_TABLES` builds canonical `publish/calls/repeat_calls.tsv` and `publish/calls/run_params.tsv`.
   - `BUILD_ACCESSION_STATUS` derives accession-level status ledgers from stage outputs and call tables.
5. Merged-only downstream reporting
   - `BUILD_SQLITE` imports canonical flat files into SQLite.
   - `EXPORT_SUMMARY_TABLES`, `PREPARE_REPORT_TABLES`, and `RENDER_ECHARTS_REPORT` build the reporting bundle.

## Workflow Topology

| Layer | Files | Responsibility |
| --- | --- | --- |
| Entry point | `main.nf`, `nextflow.config` | Global workflow wiring, params, publish rules, and completion hooks |
| Subworkflows | `workflows/*.nf` | Stage-level composition: acquisition, detection, database/reporting |
| Processes | `modules/local/**/*.nf` | One process per operational task and its CLI invocation |
| Python CLIs | `src/homorepeat/cli/*.py` | Stable command-line entrypoints for each task |
| Shared library | `src/homorepeat/**` | Detection algorithms, acquisition helpers, TSV/FASTA I/O, contracts, runtime metadata, reporting, SQLite helpers |
| Runtime metadata | `lib/HomorepeatRuntimeArtifacts.groovy` | Publishes launch metadata, run manifest, and Nextflow diagnostics |

## Execution Model

### Profiles

- `local`: Nextflow runs tasks on the host with the configured Python and CLI tools.
- `docker`: the same workflow graph runs locally, but process labels map to the pinned acquisition and detection images.

### Fan-out units

- Planning is single-task.
- Acquisition fans out by `batch_id`.
- Detection fans out by `batch_id x repeat_residue x method`.
- SQLite/reporting are merged singletons and only run in `merged` mode.

### Publish modes

- `raw` is the default.
  - Acquisition artifacts stay batch-scoped under `publish/acquisition/batches/<batch_id>/`.
  - Canonical merged call tables and status ledgers are still published.
  - SQLite and reporting outputs are skipped.
- `merged`
  - Acquisition artifacts are merged into flat files under `publish/acquisition/`.
  - SQLite and reporting outputs are produced in addition to the canonical call/status artifacts.

`publish/metadata/run_manifest.json` is the authoritative machine-readable description of which mode a run used and which artifacts were published.

## Repository Layout

| Path | What lives there |
| --- | --- |
| `main.nf` | Top-level workflow graph and publish/output wiring |
| `workflows/` | Stage-level Nextflow subworkflows |
| `modules/local/` | Individual Nextflow processes |
| `src/homorepeat/acquisition/` | NCBI download, package inspection, GFF linkage, translation helpers |
| `src/homorepeat/detection/` | Repeat detection and codon slicing logic |
| `src/homorepeat/contracts/` | Shared call/run-parameter invariants |
| `src/homorepeat/runtime/` | Run manifests, stage status, accession ledgers, benchmark helpers |
| `src/homorepeat/db/` | SQLite import and validation |
| `src/homorepeat/reporting/` | Summary aggregation and HTML report rendering |
| `containers/` | Runtime image definitions |
| `conf/` | Shared and profile-specific Nextflow config |
| `examples/` | Example accession lists and params files |
| `tests/` | Unit, CLI, and workflow regression tests |

## Implementation Notes

- The main workflow never writes detection results directly to SQLite. Flat files remain the source of truth, and database/report artifacts are downstream build products.
- Canonical merged call tables are always produced, even when acquisition outputs remain batch-scoped in `raw` mode.
- The metadata bundle is finalized in `workflow.onComplete`, so failed runs still publish `launch_metadata.json`, `run_manifest.json`, and the Nextflow diagnostics when those files exist.
- Placeholder outputs are injected only to satisfy Nextflow output wiring and are removed before the published run is finalized.
