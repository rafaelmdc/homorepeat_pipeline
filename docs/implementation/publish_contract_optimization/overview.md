# Publish Contract Optimization Overview

## Purpose

This document reviews the current published-run contract and defines the target
direction for a smaller, more import-friendly replacement.

The goal is to keep the published output biologically meaningful and easy to
import, while removing repeated large artifacts that represent the workflow's
search space rather than the final repeat-analysis result.

This overview supersedes
`docs/implementation/protein_import_optimization/implementation_plan.md` as the
main contract-level guidance for sequence and protein publish artifacts. The
older note remains useful as a narrower import-performance predecessor.

## Problem Summary

The current raw published contract is broader than the downstream web/database
import actually needs.

Today the importer:

- scans `calls/repeat_calls.tsv` first to determine retained genome, sequence,
  and protein IDs
- then still walks broad batch-scoped `sequences.tsv` and `proteins.tsv`
  artifacts
- then reads subsets from `cds.fna` and `proteins.faa` only to store full
  sequence bodies in the database

This means the published contract exposes much of the analyzed search space,
not just the result set. Import time and storage cost are therefore inflated by
non-hit rows and full duplicated FASTA payloads.

The main waste is not whole-genome FASTA. The main waste is the default
publication of:

- full analyzed `proteins.tsv`
- full analyzed `sequences.tsv`
- `proteins.faa`
- `cds.fna`
- fragmented finalized codon-usage outputs that the importer must rediscover

## Current Published Output Shape

The current import path expects a raw publish layout rooted at `publish/`:

- `metadata/run_manifest.json`
- `status/accession_status.tsv`
- `status/accession_call_counts.tsv`
- `calls/repeat_calls.tsv`
- `calls/run_params.tsv`
- `calls/finalized/<method>/<repeat_residue>/<batch_id>/final_*_codon_usage.tsv`
- `acquisition/batches/<batch_id>/genomes.tsv`
- `acquisition/batches/<batch_id>/taxonomy.tsv`
- `acquisition/batches/<batch_id>/sequences.tsv`
- `acquisition/batches/<batch_id>/proteins.tsv`
- `acquisition/batches/<batch_id>/cds.fna`
- `acquisition/batches/<batch_id>/proteins.faa`
- `acquisition/batches/<batch_id>/download_manifest.tsv`
- `acquisition/batches/<batch_id>/normalization_warnings.tsv`
- `acquisition/batches/<batch_id>/acquisition_validation.json`

Conceptually, those outputs split into four categories:

| Category | Current role | Problem |
| --- | --- | --- |
| Repeat result tables | Actual downstream analytical payload | Correct core contract |
| Genome/taxon/status/provenance tables | Needed for traceability and operations | Should stay |
| Full analyzed sequence/protein inventories | Search-space artifacts | Too broad for default publish |
| Full FASTA payloads | Sequence-body duplication | Large and slow to import |

## What Must Be Preserved

The slimmed contract must still let downstream systems answer:

- which assembly, accession, genome, and taxon a repeat came from
- which sequence and protein the repeat belongs to
- which residue is repeated
- the repeat coordinates and length
- the detection method and parameterization
- the tract amino-acid sequence and codon sequence
- codon composition inside the tract or detection window
- compact flanking context
- run provenance, input provenance, and batch provenance
- accession-level status for both hit and zero-hit accessions

This does not require publishing the full analyzed proteome or CDS collection.
It requires stable identifiers, repeat-linked metadata, codon/context outputs,
and provenance.

## Design Principles

### 1. Default publish must be result-centric

The default contract should describe what was found, not the entire search space
used to find it.

### 2. Preserve provenance, not copied source payloads

Keep source accessions, source paths, checksums, timestamps, and warnings.
Do not keep repeated copied FASTA bodies in the default user-facing output.

### 3. Keep zero-hit accessions at the accession/genome layer

Genome/accession/status tables must still represent requested accessions even
when no repeat calls were found. Slimming applies to sequence/protein-level
artifacts, not accession-level provenance and status.

### 4. Sequence/protein tables should be hit-linked only

Default published `sequence` and `protein` tables should contain only rows
referenced by at least one repeat call.

### 5. Compact repeat context should replace full stored sequence bodies

Repeat detail pages and downstream analysis need tract-level context, not
entire translated proteins or CDS bodies for every retained search-space row.

### 6. The public contract must be explicitly versioned

The importer needs a clean dispatch point between the legacy raw contract and
the slimmer contract. Contract versioning belongs in the manifest, not in
path-shape guesswork.

## Keep / Remove / Replace Matrix

| Current artifact | Default v2 decision | Rationale |
| --- | --- | --- |
| `metadata/run_manifest.json` | Keep | Core provenance and contract dispatch |
| `metadata/launch_metadata.json` | Keep | Useful run provenance |
| `status/accession_status.tsv` | Keep | Required for zero-hit accessions and operational visibility |
| `status/accession_call_counts.tsv` | Keep | Useful accession-level summary and explorer input |
| `acquisition/batches/*/genomes.tsv` | Replace with flat `tables/genomes.tsv` | Keep all accession/genome rows, but flatten batch provenance into a column |
| `acquisition/batches/*/taxonomy.tsv` | Replace with flat `tables/taxonomy.tsv` | Keep taxonomy payload without batch-scoped directories |
| `acquisition/batches/*/sequences.tsv` | Replace with `tables/matched_sequences.tsv` | Publish only repeat-linked sequence rows |
| `acquisition/batches/*/proteins.tsv` | Replace with `tables/matched_proteins.tsv` | Publish only repeat-linked protein rows |
| `acquisition/batches/*/cds.fna` | Remove from default publish | Large duplicated payload; replace with compact context in tables |
| `acquisition/batches/*/proteins.faa` | Remove from default publish | Large duplicated payload; replace with compact context in tables |
| `calls/repeat_calls.tsv` | Keep | Canonical repeat-call table |
| `calls/run_params.tsv` | Keep | Required method/parameter provenance |
| `calls/finalized/**/final_*_codon_usage.tsv` | Replace with flat `tables/repeat_call_codon_usage.tsv` | Stop importer filesystem crawling and make codon usage canonical |
| `calls/finalized/**/final_*_calls.tsv` | Remove from default publish | Duplicates merged call table |
| `calls/finalized/**/final_*_run_params.tsv` | Remove from default publish | Duplicates merged run params |
| `calls/finalized/**/final_*_codon_warnings.tsv` | Demote to optional diagnostics | Useful for debugging, not core import contract |
| `download_manifest.tsv` | Keep | Source provenance and operator visibility |
| `normalization_warnings.tsv` | Keep | Biological and operational warnings |
| `acquisition_validation.json` | Optional summary | Useful as run QA, not a core row-import dependency |
| `publish/database/*` | Optional | Useful for operator workflows, not required for web import |
| `publish/reports/*` | Optional | Useful for reporting, not required for web import |

## Target Default Contract

The target stable contract is a flat, versioned publish layout:

```text
publish/
  metadata/
    run_manifest.json
    launch_metadata.json
    nextflow/
      report.html
      timeline.html
      dag.html
      trace.txt
  tables/
    genomes.tsv
    taxonomy.tsv
    matched_sequences.tsv
    matched_proteins.tsv
    repeat_calls.tsv
    repeat_call_codon_usage.tsv
    repeat_context.tsv
    run_params.tsv
    accession_status.tsv
    accession_call_counts.tsv
    download_manifest.tsv
    normalization_warnings.tsv
  summaries/
    status_summary.json
    acquisition_validation.json
  optional/
    diagnostics/
    database/
    reports/
```

### Table expectations

`genomes.tsv`

- one row per requested accession/genome
- keeps zero-hit accessions
- includes explicit `batch_id` instead of path-derived batch provenance

`matched_sequences.tsv`

- one row per sequence referenced by at least one repeat call
- uses the current sequence metadata schema
- adds explicit `batch_id`
- does not include full nucleotide sequence bodies

`matched_proteins.tsv`

- one row per protein referenced by at least one repeat call
- uses the current protein metadata schema
- adds explicit `batch_id`
- does not include full amino-acid sequence bodies

`repeat_calls.tsv`

- remains the canonical analytical table
- continues to carry tract-level fields such as `aa_sequence`,
  `codon_sequence`, coordinates, residue, purity, and method metadata

`repeat_call_codon_usage.tsv`

- one merged codon-usage table keyed by `call_id`
- replaces importer discovery of many finalized fragment files

`repeat_context.tsv`

- stores compact flanking context for the repeat call
- should include `call_id`, `protein_id`, `sequence_id`, left/right amino-acid
  flanks, left/right nucleotide flanks, and explicit window sizes

## Manifest And Versioning Direction

The manifest should gain a required `publish_contract_version` field.

Recommended behavior:

- contract v1: current raw import contract
- contract v2: flat slim contract described in this document

`acquisition_publish_mode` may remain as pipeline provenance, but importer
dispatch should be driven by `publish_contract_version`.

## Expected Benefits

The slimmer contract should improve:

- published-run size
- import wall-clock time
- importer I/O volume
- database storage footprint for non-essential full sequence bodies
- clarity of the user-facing output contract
- downstream feature work, because consumers no longer need to rediscover the
  matched subset from a larger search-space bundle

## Out Of Scope For The Default Contract

The default published contract should not promise:

- full analyzed proteome FASTA
- full analyzed CDS FASTA
- full analyzed protein inventories with no repeat calls
- full analyzed sequence inventories with no repeat calls
- per-method/per-batch duplicate result fragments when merged canonical tables
  already exist

If operators still need these for debugging, they may be emitted as optional
diagnostics outside the stable default contract.
