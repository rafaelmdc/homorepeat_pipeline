# Pipeline Performance and Scalability Roadmap

## Purpose

This roadmap captures the redesign direction for the pipeline's next performance phase.

The immediate trigger was the chromosome-scale acquisition run on April 8, 2026:

- the run root grew to roughly `491G`
- `NORMALIZE_CDS_BATCH` tasks peaked at roughly `2.3-4.2 GB RSS`
- `TRANSLATE_CDS_BATCH` duplicated normalized batch contents, including multi-GB `cds.fna`
- acquisition used workflow-wide barriers that delayed downstream work and kept large intermediates alive longer than needed

This is not one isolated bug. The current pipeline shape is carrying too much data for too long, and it is doing that with contracts that are wider than the downstream stages actually need.

## Target outcome

After this redesign, the pipeline should:

- run reliably on a 32 GB workstation with the Docker profile
- use scratch-backed `workDir` storage instead of growing the repo-local run tree uncontrollably
- stop duplicating large batch artifacts between normalize, translate, and merge stages
- start downstream detection as soon as one translated batch is ready instead of waiting for all batches
- keep Nextflow orchestration file-based and immutable for large artifacts

## Design principles

### 1. Keep the hot path Nextflow-native

Large payloads should move between tasks as files, not as rows in a shared mutable database.

That includes:

- downloaded NCBI packages
- extracted package trees
- `gff`
- `cds.fna`
- `proteins.faa`

Nextflow is best at isolated tasks with immutable file inputs and outputs. The redesign should lean into that instead of fighting it.

### 2. Narrow every task contract

Each process should emit only what downstream consumers actually need.

Examples:

- download should not keep both extracted content and a redundant local zip unless caching was explicitly requested
- translate should not copy the full normalized batch just to add protein outputs
- detection should consume translated protein artifacts only
- codon finalization should read normalized sequence and CDS artifacts directly, not through copied translated batch directories

### 3. Stream large files instead of materializing them

The Python CLIs should treat large TSV and FASTA inputs as streams or chunked iterators whenever possible.

The main goal is to avoid patterns like:

- loading entire FASTA files into memory
- building large in-memory row lists before writing outputs
- loading all batches before merging

### 4. Prefer scratch for work, publish only stable outputs

The pipeline should keep bulky intermediate artifacts in `workDir` on fast scratch storage and publish only stable user-facing outputs.

Canonical published outputs remain under:

- `publish/acquisition/`
- `publish/calls/`
- `publish/database/`
- `publish/reports/`
- `publish/status/`
- `publish/metadata/`

### 5. Keep this phase focused on optimization

This phase is about reducing:

- RAM pressure
- disk growth
- redundant reads and writes
- unnecessary workflow retention and barriers

Database redesign is out of scope for now because it does not address the measured bottlenecks directly.

## Recommended architecture

### Acquisition path

### Download

`DOWNLOAD_NCBI_BATCH` should:

- write a package manifest and stage status
- extract the NCBI package into a batch-local directory
- delete the batch zip after extraction unless `--cache-dir` is set
- keep cache retention as an explicit operator choice, not the default

### Normalize

`NORMALIZE_CDS_BATCH` should emit:

- `genomes.tsv`
- `taxonomy.tsv`
- `sequences.tsv`
- `cds.fna`
- `download_manifest.tsv`
- `normalization_warnings.tsv`
- normalize stage status

It should stream parsing and writing instead of building large in-memory collections when not required by validation.

### Translate

`TRANSLATE_CDS_BATCH` should emit only translated outputs:

- `proteins.tsv`
- `proteins.faa`
- translation validation output
- translate stage status
- any translation-stage warnings that are still needed downstream

It should not copy the normalized batch directory.

### Merge

Merged acquisition artifacts should remain a terminal reduction step.

The merge stage should:

- append batch outputs incrementally
- avoid loading all FASTA or TSV payloads into memory at once
- build temporary combined views inside the task work directory if one process needs both normalized and translated artifacts

### Detection and finalization path

Detection should start batch-by-batch as soon as translation finishes for that batch.

The workflow should stop using a global `toList()` barrier in acquisition before detection can begin.

The preferred split is:

- detection reads translated proteins
- codon finalization reads normalized `sequences.tsv` and `cds.fna`
- final canonical call/report/database outputs remain reduction stages near the end of the workflow

### Resource model

The initial tuned defaults for workstation use should be conservative:

- `batch_size = 10`
- `acquisition_download.maxForks = 2`
- `acquisition_normalize.maxForks = 2`
- `acquisition_translate.maxForks = 2`
- `detection.maxForks = 4`

Each heavy label should also have explicit memory requests rather than relying only on `maxForks`.

Recommended starting budgets:

- download: `2 GB`
- normalize: `6 GB`
- translate: `4 GB`
- detection: `2 GB`

These values should be validated empirically and then adjusted from trace data, not guessed ad hoc per run.

## Delivery order

Recommended order of work:

1. add measurement guardrails and benchmark the chromosome-scale input set
2. land low-risk disk wins
3. split normalized and translated batch contracts
4. stream normalize and translate Python paths
5. remove workflow-wide acquisition barriers
6. tune defaults around measured resource use

## Success criteria

The redesign is successful when all of the following are true:

- the chromosome-scale run completes on a 32 GB machine without OOM
- work-dir growth is materially lower than the current `491G` run
- translated batches no longer contain copied normalized FASTA payloads
- first detection outputs appear while acquisition is still running
- `-resume` still works cleanly after interruption
- canonical published outputs stay stable for downstream consumers

## Non-goals

This phase does not require:

- replacing Nextflow with a service-style scheduler
- redesigning the database layer
- designing a fully cloud-native object-store architecture before local scaling is fixed
- preserving current internal batch contracts if they are the main source of duplication
