# Documentation

This directory holds the maintained documentation for the current HomoRepeat pipeline.

The repo has two documentation layers:

- Current-state docs in this directory.
- Frozen implementation plans in [`docs/implementation/`](./implementation/).

Use the current-state docs when you want to understand or operate the repository as it exists today. Treat `docs/implementation/` as planning material for upcoming work, not as the source of truth for the current workflow.

## Start Here

- [Operations](./operations.md): install, build, run, and inspect pipeline outputs.
- [Architecture](./architecture.md): workflow structure, code layout, and data flow.
- [Methods and Scientific Notes](./methods.md): acquisition, translation, repeat detection, and reporting logic.
- [Data Contracts](./contracts.md): published files, canonical identifiers, and table schemas.

## Supporting Guides

- [Containers](./containers.md): runtime images and Docker profile details.
- [Scale Guide](./scale_guide.md): concurrency model, resource defaults, and large-run advice.
- [Benchmark Guide](./benchmark_guide.md): benchmark inputs, the summary CLI, and comparison workflow.
- [Save State Guide](./save_state_guide.md): `-resume`, accession-level ledgers, and rerun strategy.

## Current Scope

The current pipeline:

- starts from a plain-text assembly accession list
- downloads annotation-focused NCBI packages
- normalizes CDS records and taxonomy into canonical TSV/FASTA artifacts
- translates CDS conservatively and retains one protein isoform per gene group
- runs `pure`, `threshold`, and optional `seed_extend` homorepeat detection
- attaches codon slices when they can be validated against the normalized CDS
- always publishes canonical merged call tables under `publish/calls/`
- optionally builds SQLite and report artifacts when `--acquisition_publish_mode merged`

Not currently implemented in the main Nextflow workflow:

- taxon-name driven acquisition
- local FASTA/GFF manifest input as a first-class workflow entrypoint
- annotation/domain enrichment downstream of repeat calling
