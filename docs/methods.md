# Methods

## Purpose

This document records the v1 operational decisions that sit between the high-level roadmap and the implementation.

It answers the questions that were still underspecified in the original docs:
- how data enters the workflow
- how local and NCBI-backed acquisition coexist
- how one isoform per gene is selected
- what the retained v1 detection methods mean operationally
- how codon extraction, SQLite import, summaries, and ECharts reporting are bounded

These rules are the implementation target unless a later contract change is made explicitly.

---

## Scientific scope for v1

The first rebuild targets general homorepeat detection rather than a single residue only.

The workflow must support:
- acquisition of CDS and annotation data, with proteins derived locally when needed
- one retained isoform per gene
- two peer detection strategies: `pure` and `threshold`
- configurable repeat residue targets
- codon-aware feature extraction when CDS is available
- SQLite assembly from flat files
- summary tables and ECharts-based reporting from finalized outputs

The first rebuild does not require:
- annotation/domain enrichment
- browser-facing applications
- direct database mutation during earlier pipeline stages
- bespoke downstream reporting for every residue in the first release
- any residue-specific downstream analysis in the first release

---

## Comparability Policy

The rebuild is expected to remain comparable to the earlier project in terms of:
- acquisition of user-selected taxonomic sequence data and metadata
- taxonomy-aware homorepeat analysis
- the retained v1 detection strategies
- SQLite as a final integrated artifact
- residue-neutral summary and reporting outputs in the first release

The rebuild is not required to preserve:
- legacy code layout
- undocumented tie-breaking behavior
- exact row ordering of historical outputs
- any old heuristic that is not explicitly documented in the new specification

When the rebuilt project differs from the old one, the preferred interpretation order is:
1. documented new contracts
2. documented method definitions
3. scientific plausibility
4. legacy behavior only where it was already explicit and defensible

---

## Acquisition strategy

### Supported input modes

Two acquisition modes are supported in the same manifest contract:

1. `ncbi_datasets`
2. `local`

`ncbi_datasets` is the production path for rebuilding the original project from scratch.
`local` exists for tests, smoke datasets, and offline development.

### NCBI-backed acquisition

The current production acquisition path uses the NCBI `datasets` CLI for assembly/package retrieval and `taxon-weaver` as the canonical local taxonomy layer.

Current behavior:
- enumerate candidate assemblies from NCBI metadata before downloading sequence packages
- select `RefSeq` current annotated assemblies only
- prefer `reference genome`, allow `representative genome`, and still accept annotated uncategorized RefSeq rows
- download annotation-focused package contents: CDS, GFF3, and metadata reports
- avoid raw genomic FASTA in v1
- translate retained CDS records locally into canonical protein FASTA for detection
- retain the raw package on disk for reproducibility
- normalize package contents into the canonical TSVs and normalized FASTA files

The implementation should tolerate either a hydrated local package or an already-downloaded package directory.

Current implementation details and ignore rules live in:
- [operations.md](./operations.md)

### Local acquisition

Local mode is planned to accept CDS FASTA and optional annotation GFF paths directly from the manifest.
Protein FASTA may still be accepted as a smoke-test bypass, but it is not the preferred scientific path.

This mode must:
- preserve the same downstream contracts as NCBI-backed acquisition
- write normalized FASTA files with internal IDs as headers
- remain deterministic for tests

### Taxonomy handling

Taxonomy metadata is planned to be normalized into `taxonomy.tsv`.

For v1:
- `taxon_id` is the stable reporting identifier
- `taxon-weaver` lineage inspection is materialized into explicit taxonomy rows
- each ancestor taxon is stored once with `taxon_id`, `taxon_name`, `parent_taxon_id`, and `rank`
- missing hierarchy information is allowed, but `taxon_id` must still exist

Operationally:
- build a local NCBI taxonomy SQLite database with `taxon-weaver`
- use `taxon-weaver` resolution for user-supplied taxon names
- use `taxon-weaver` lineage inspection for taxids returned by NCBI assembly metadata
- keep deterministic resolution authoritative and treat fuzzy suggestions as review-only

### Contamination checking

The original project performed contamination lineage checks during acquisition.

For the rebuild:
- contamination screening is not a blocker for v1 execution
- the acquisition layer records notes and source metadata
- explicit contamination validation can be added later as a separate single-purpose step

Settled v1 policy:
- contamination remains note-only and does not act as a hard validation gate

---

## Sequence preparation

### Normalized FASTA outputs

Acquisition is planned to write normalized FASTA files so downstream scripts do not rely on source-specific headers.

Rules:
- CDS FASTA headers become `sequence_id`
- translated protein FASTA headers become `protein_id`
- normalized rows point to those normalized FASTA paths

### CDS normalization and translation

Default normalization authority:
1. `genomic.gff` feature relationships and attributes
2. structured package metadata and assembly reports
3. CDS FASTA header metadata only as a documented fallback

The preferred linkage order is:
1. GFF transcript-like aliases
2. GFF protein aliases
3. GFF CDS ID aliases
4. GFF gene-segment alias `cds-<gene_symbol>` for rearrangement-dependent immune segment CDS rows lacking transcript and protein IDs
5. CDS FASTA header fallback with warning

The workflow must not default to pairing records by normalized file order.
If a confident biological linkage cannot be established from the sources above, the record is emitted with a linkage warning rather than silently guessed.

Default molecule filter:
- normalize only sequence-report rows in `Primary Assembly` and `non-nuclear`
- ignore alternate loci and patch units in the canonical v1 path

Derived-protein policy:
- normalized CDS records are translated locally and become the canonical protein input for detection
- translation should follow the retained CDS record and documented translation rules, not an external protein FASTA by default
- if a CDS record cannot be translated confidently, it is excluded from protein-based detection and emitted as a warning state rather than patched heuristically
- immune receptor segment rows that link successfully but remain `partial` are kept in normalized CDS outputs and excluded from retained protein outputs

### Isoform selection

The workflow is planned to keep one isoform per gene per genome.

v1 selection rule:
- group by `gene_symbol` when present
- otherwise group by a stable fallback key derived from transcript or sequence identity
- keep the longest protein sequence in each group
- break ties lexicographically by protein identifier

This rule is deterministic and easy to validate, even if it does not recover all historical choices.

---

## Detection methods

All methods are planned to emit the shared call contract.

Coordinates are 1-based and inclusive in amino-acid space.
All methods must trim leading and trailing non-target residues from the final called tract.

Each run is expected to define:
- a target `repeat_residue` for single-residue homorepeats

### Pure method

Intent:
- capture canonical contiguous homorepeat tracts for the chosen repeat residue

Default rule:
- detect maximal contiguous target-residue runs only
- default `min_repeat_count = 6`

Reported features:
- `repeat_count`
- `non_repeat_count`
- `purity = repeat_count / length`

### Threshold method

Intent:
- capture biologically plausible but slightly impure tracts for the chosen repeat residue using a density rule

Default rule:
- sliding window size `8`
- default target-residue count `6` within the window
- every qualifying sliding window is threshold-positive
- merge overlapping or directly adjacent qualifying windows into one reported tract

The default window definition is expected to be recorded in residue-aware form such as `<residue>6/8`.

### Similarity method status

Similarity-based detection is not part of the current v1 implementation scope.

Current policy:
- only `pure` and `threshold` are implemented and supported
- no similarity-method output is part of the current workflow contracts
- if similarity-based detection is reintroduced later, it should return through a new explicit contract change rather than through hidden partial support

---

## Codon extraction and repeat features

Codon extraction is planned to be attempted only when a CDS sequence can be linked to the detected protein.

Rules:
- derive codon coordinates directly from amino-acid coordinates
- use the normalized CDS sequence as the nucleotide source of truth
- detection should run on proteins derived from validated CDS records by default
- accepted CDS translation requires conservative validation before a protein is emitted:
  - translation table from annotation when available, otherwise table `1`
  - coding length divisible by `3` after terminal-stop handling
  - no internal stop codons
  - no unsupported ambiguity that would yield unresolved amino acids
- if codon slicing or downstream translation checks fail for a retained record, leave `codon_sequence` empty and emit a warning rather than guessing
- keep residue-specific codon metric fields empty in the first residue-neutral release unless a later contract explicitly enables them

The first release remains residue-neutral even when codon sequence evidence is available.
Codon extraction may still be retained as groundwork for later residue-specific analysis tracks.

Reported feature semantics:
- `length` counts the full amino-acid tract after trimming termini
- `repeat_count` counts only residues matching `repeat_residue`
- `non_repeat_count = length - repeat_count`
- `purity` is a decimal fraction in `[0, 1]`

---

## Database assembly

SQLite is planned to be assembled only after metadata and call files validate.

v1 rules:
- create schema from `assets/sql/schema.sql`
- import flat files inside transactions
- import method outputs into a unified `repeat_calls` table
- create indexes after bulk import
- validate row counts and foreign-key reachability after import

SQLite remains a build artifact, not a workspace.

---

## Summary exports

### `summary_by_taxon.tsv`

Grouped by:
- `method`
- `repeat_residue`
- `taxon_id`
- `taxon_name`

Metrics:
- unique genomes
- unique proteins
- call counts
- tract length summary statistics
- purity summary statistics
- mean start fraction when protein length is known

### `regression_input.tsv`

Grouped by:
- `method`
- `repeat_residue`
- `group_label`
- `repeat_length`

For v1:
- regression grouping should default directly to taxon in v1
- the `group_label` field should mirror `taxon_name` or another explicit taxon label derived directly from the selected taxon grouping
- curated higher-level macro-groups can be added later as an optional reporting layer

---

## ECharts reporting

The reporting layer is downstream only.

v1 reporting outputs:
- a grouped bar chart summarizing calls by taxon and method
- a length-distribution view by taxon, method, and repeat residue
- a residue-composition or residue-frequency view across taxa and methods
- a single reproducible HTML report backed by serialized ECharts options

Rules:
- report generation depends only on finalized tables or SQLite
- chart configuration is emitted as JSON for inspection and reuse
- the HTML report may load a pinned ECharts runtime from CDN in v1

---

## Known v1 boundaries

- NCBI-backed acquisition depends on the `datasets` CLI being installed in the execution environment
- similarity-based detection is deferred from the current v1 implementation baseline
- annotation and domain context are deferred
- contamination checks are documented but not enforced as a hard failure path
- the first ECharts rebuild is expected to cover core comparative outputs before supplementary figure families
- residue-agnostic detection and reporting should exist in v1
- residue-specific downstream analyses may roll out only after the first residue-neutral release
- the first repeat-length distribution view should use a histogram or other explicit binned layout rather than a donut-style chart
