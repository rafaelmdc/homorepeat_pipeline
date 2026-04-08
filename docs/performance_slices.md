# Pipeline Performance Implementation Slices

## Purpose

This document breaks the performance roadmap into reviewable slices. Each slice should be small enough to validate in isolation and should leave the pipeline in a runnable state.

## Slice 1: Establish Baselines and Guardrails

### Goal

Make performance changes measurable before changing workflow shape.

### Scope

- trace and run-metadata review
- one repeatable benchmark input set
- docs and test hooks for resource expectations

### Changes

- record the chromosome-scale accession set as the reference benchmark
- document current bottlenecks:
  - `491G` work tree growth
  - normalize peak RSS around `2.3-4.2 GB`
  - translated batch duplication
- add a lightweight benchmark checklist for future runs:
  - peak RSS by process
  - total work-dir size
  - time to first translated batch
  - time to first detection output

### Acceptance criteria

- the team has one shared benchmark input and one shared measurement checklist
- future refactors can be compared against the same baseline

## Slice 2: Land Low-Risk Disk Wins

### Goal

Remove the largest obvious duplication without changing the detection logic.

### Scope

- download stage
- translate stage
- scale docs

### Changes

- delete uncached zip archives after extraction
- keep archives only when `--cache-dir` is explicitly configured
- stop copying `normalized_batch` into `translated_batch`
- make translate emit only protein outputs and translation metadata

### Acceptance criteria

- translated batches no longer contain copied `cds.fna`
- batch-local raw outputs do not keep both extracted package content and a redundant local zip by default
- published canonical outputs stay unchanged

### Validation

- targeted acquisition CLI tests
- one real or fixture-backed batch run
- disk usage comparison before and after

## Slice 3: Split Batch Contracts Cleanly

### Goal

Untangle normalized and translated artifacts so each stage reads only what it needs.

### Scope

- acquisition workflow
- merge stage
- status-building stage
- detection/finalization wiring

### Changes

- carry normalized and translated artifacts as separate workflow products
- wire detection to translated protein artifacts only
- wire codon finalization to normalized `sequences.tsv` and `cds.fna`
- assemble temporary combined batch views only inside tasks that require both sides

### Acceptance criteria

- no persistent copied batch directories are required for downstream stages
- merge and status generation still produce the same user-facing outputs
- workflow contracts are narrower and easier to reason about

### Validation

- acquisition CLI tests
- detection workflow test
- accession status test

## Slice 4: Stream Normalize

### Goal

Reduce memory pressure in the largest acquisition stage.

### Scope

- FASTA and TSV IO helpers
- normalize CLI

### Changes

- add iterator-style FASTA and TSV readers
- add append-friendly writers where needed
- rewrite normalize to stream CDS records and row writes instead of accumulating full output payloads in memory
- preserve validation behavior using counters and targeted checks instead of full-file materialization

### Acceptance criteria

- normalize peak RSS drops materially on the benchmark set
- normalize still emits the same canonical outputs and stage statuses
- duplicate-sequence and linkage edge cases remain covered

### Validation

- current normalize CLI tests
- duplicate/variant CDS regression tests
- benchmark rerun focused on normalize trace rows

## Slice 5: Stream Translate and Merge

### Goal

Remove the second major memory and I/O hotspot after normalize.

### Scope

- translate CLI
- acquisition merge CLI
- IO helpers shared with these stages

### Changes

- stop using whole-file materialization patterns for normalized FASTA lookup where avoidable
- process translation in a streamed or chunked manner
- append merged TSV and FASTA outputs batch-by-batch
- keep validation and warning behavior stable

### Acceptance criteria

- translate no longer needs the copied normalized batch layout
- merge no longer loads all batches into memory at once
- benchmark runs show lower peak memory in translate and merge

### Validation

- current translation CLI tests
- current acquisition merge tests
- benchmark rerun focused on translate and merge trace rows

## Slice 6: Remove Workflow-Wide Barriers

### Goal

Allow downstream work to start earlier and release pressure on intermediate retention.

### Scope

- acquisition workflow
- detection workflow
- any reduction steps that currently depend on `toList()` barriers

### Changes

- remove the acquisition-side `toList()` barrier before detection
- keep final merged outputs as terminal reductions only where they are truly required
- let translated batches feed detection as soon as each batch is ready

### Acceptance criteria

- first detection tasks start before acquisition finishes globally
- the pipeline still resumes correctly after interruption
- canonical outputs remain stable

### Validation

- workflow tests
- real benchmark run with trace inspection
- `-resume` regression on an interrupted run

## Slice 7: Retune Defaults and Scratch Usage

### Goal

Make safe resource defaults part of the shipped pipeline rather than operator folklore.

### Scope

- `conf/base.config`
- profile docs
- operations guidance

### Changes

- add separate `acquisition_translate` resource controls
- lower the default `batch_size` from `25` to `10`
- set conservative `maxForks` and explicit memory requests for heavy labels
- document scratch-backed `workDir` as the default operational recommendation

### Acceptance criteria

- the default profile is safer on a 32 GB workstation
- docs explain how to place `workDir` on fast local scratch
- resource tuning is based on measured behavior, not guesswork

### Validation

- config parse test
- benchmark run under the default docker profile

## Recommended PR grouping

If this work is split across multiple PRs, use this order:

1. Slice 1
2. Slice 2
3. Slice 3
4. Slice 4
5. Slice 5
6. Slices 6 and 7 together
