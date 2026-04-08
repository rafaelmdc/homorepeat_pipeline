# Remaining Memory Streaming Slices

## Purpose

This document breaks the remaining memory work into reviewable slices after the first optimization pass.

## Slice 1: Stream Detection Outputs

### Goal

Stop the detection CLIs from loading full protein datasets and buffering all call rows before writing.

### Scope

- `detect_pure.py`
- `detect_threshold.py`
- `detect_seed_extend.py`
- any small shared helpers needed to iterate protein TSV and FASTA together

### Changes

- iterate `proteins.tsv` and `proteins.faa` in lockstep
- validate `protein_id` alignment instead of building a full FASTA dict
- write call rows incrementally with TSV writers
- preserve deterministic output order from the canonical protein inputs

### Acceptance criteria

- detection outputs are still contract-compatible
- no detection CLI uses `dict(read_fasta(...))`
- no detection CLI accumulates all call rows before writing

### Validation

- current pure, threshold, and seed-extend CLI tests
- live or fixture-backed workflow check using one translated batch

## Slice 2: Stream Codon Finalization

### Goal

Reduce memory in the finalize path by removing the full CDS FASTA materialization and incrementalizing outputs.

### Scope

- `extract_repeat_codons.py`
- codon-finalization tests

### Changes

- replace full output-row accumulation with incremental writes
- replace full CDS FASTA dict loading with sequence-bounded processing
- keep only the lookup state required for one finalized call fragment

### Acceptance criteria

- codon-enriched calls, warnings, and codon-usage tables remain unchanged in content
- finalize no longer loads the full CDS FASTA into a dict
- finalize peak RSS drops relative to the current live trace

### Validation

- current codon extraction tests
- one workflow run exercising pure and threshold finalization

## Slice 3: Remove Detection End Barriers

### Goal

Stop collecting finalized outputs and status JSONs into one end-of-run list before downstream reporting starts.

### Scope

- `workflows/detection_from_acquisition.nf`
- downstream wiring that currently expects list-valued channels

### Changes

- keep finalized directories streaming
- reduce only inside the process that truly requires aggregate lists
- preserve canonical `publish/calls/`, `publish/status/`, and `publish/database/` outputs

### Acceptance criteria

- no unnecessary `toList()` barrier remains on the detection side
- downstream reporting still receives the artifacts it needs
- `-resume` behavior remains stable

### Validation

- workflow tests
- one canonical `nextflow run .` smoke with a live accession

## Slice 4: Stream Terminal Reducers

### Goal

Reduce end-of-run memory in canonical call merge, status build, reporting summaries, and SQLite import.

### Scope

- `merge_call_tables.py`
- `build_accession_status.py`
- `export_summary_tables.py`
- `build_sqlite.py`

### Changes

- append merged rows instead of building one full list
- use counters and keyed state instead of global row retention where possible
- import into SQLite incrementally instead of materializing every source table first

### Acceptance criteria

- terminal reducers stay contract-compatible
- end-of-run memory is bounded by targeted keyed state, not whole-table row lists
- the canonical outputs remain byte-for-byte stable where ordering is part of the contract

### Validation

- current reducer CLI tests
- one canonical workflow run
- one benchmark rerun with trace comparison

## Recommended implementation order

1. Slice 1
2. Slice 2
3. Slice 3
4. Slice 4
