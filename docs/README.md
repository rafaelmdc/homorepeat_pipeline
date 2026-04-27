# Documentation

This directory contains the maintained documentation for the current HomoRepeat
pipeline. Start with the biologist-facing run instructions, then use the
background and contract docs when you need details.

Planning notes under `docs/implementation/`, if present, are historical or
forward-looking material and should not override these current-state docs.

## Start Here

- [Project README](../README.md): fastest path from setup to first run.
- [Operations](./operations.md): copy-paste setup, taxonomy database creation, runs, outputs, and troubleshooting.
- [Background and Glossary](./background.md): plain-language explanations of biological and informatics terms.
- [Methods and Scientific Notes](./methods.md): biological assumptions, detection methods, codon validation, and limitations.
- [Data Contracts](./contracts.md): published files, identifiers, schemas, and manifest behavior.

## Supporting Guides

- [Architecture](./architecture.md): how Nextflow, Python CLIs, reducers, and metadata fit together.
- [Containers](./containers.md): runtime image split and Docker profile details.
- [Scale Guide](./scale_guide.md): fan-out/fan-in model, resource defaults, and larger-run advice.
- [Benchmark Guide](./benchmark_guide.md): benchmark inputs and trace summarization.
- [Resume and Recovery](./save_state_guide.md): Nextflow `-resume`, metadata, and accession-level diagnostics.
- [Development Guide](./development.md): contributor workflow, testing strategy, and code organization.

## Taxonomy Database Behavior

When `--taxonomy_db` is omitted, the main pipeline uses the default path:

```text
runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

If that file is missing, the workflow builds it automatically and reuses it on
later runs. To use a database you already built, pass:

```bash
--taxonomy_db /path/to/ncbi_taxonomy.sqlite
```

Explicit `--taxonomy_db` paths must already exist. See
[Operations](./operations.md#taxonomy-database) for details.

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
