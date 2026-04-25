# Documentation

This directory contains the maintained documentation for the current HomoRepeat pipeline. It is the source of truth for users and contributors. Planning notes under `docs/implementation/`, if present, are historical or forward-looking material and should not override these current-state docs.

## Start Here

- [Operations](./operations.md): install, build images, run the workflow, and inspect output.
- [Architecture](./architecture.md): how Nextflow, Python CLIs, reducers, and metadata fit together.
- [Methods and Scientific Notes](./methods.md): biological assumptions, detection methods, codon validation, and limitations.
- [Data Contracts](./contracts.md): v2 published files, identifiers, schemas, and manifest behavior.
- [Development Guide](./development.md): contributor workflow, testing strategy, and code organization.

## Supporting Guides

- [Containers](./containers.md): runtime image split and Docker profile details.
- [Scale Guide](./scale_guide.md): fan-out/fan-in model, resource defaults, and larger-run advice.
- [Benchmark Guide](./benchmark_guide.md): benchmark inputs and trace summarization.
- [Resume and Recovery](./save_state_guide.md): Nextflow `-resume`, metadata, and accession-level diagnostics.

## Current Public Contract

HomoRepeat now publishes contract version `2`.

Default public outputs are compact and table-oriented:

- `publish/calls/repeat_calls.tsv`
- `publish/calls/run_params.tsv`
- `publish/tables/*.tsv`
- `publish/summaries/*.json`
- `publish/metadata/*.json`
- `publish/metadata/nextflow/*`

The default contract does not publish broad batch acquisition directories, full CDS FASTA, full protein FASTA, per-finalizer call fragments, or duplicate status directories. Those remain internal execution artifacts.

## Current Workflow Scope

Implemented:

- assembly-accession input
- NCBI Datasets acquisition
- taxonomy-aware CDS normalization
- conservative translation and deterministic isoform retention
- `pure`, `threshold`, and optional `seed_extend` repeat detection
- validated codon slicing and merged codon-usage export
- compact repeat-context export
- optional SQLite and HTML/JSON reports in `merged` mode

Not implemented as first-class workflow features:

- taxon-name input workflow
- local FASTA/GFF manifest input workflow
- domain enrichment or annotation-heavy downstream biology
- web UI
