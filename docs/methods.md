# Methods and Scientific Notes

## Scientific Scope

The pipeline detects single-residue amino-acid homorepeats in proteins derived
from annotated CDS records. The operative data path is:

assembly accession -> NCBI package -> normalized CDS -> translated proteins -> repeat calls -> optional codon slices -> summaries/SQLite

The main Nextflow workflow is accession-driven. Although the Python package
contains reusable helpers, the workflow does not currently expose taxon-name
driven acquisition or local FASTA/GFF manifests as first-class runtime inputs.

## Acquisition and Normalization

### Accession planning

`plan_accession_batches` reads a plain-text accession list, ignores blank lines and `#` comments, removes duplicates, and writes deterministic batches.

When accession resolution is enabled:

- `GCF_` accessions are kept as-is
- other accessions are resolved through NCBI Datasets metadata
- GenBank accessions can be redirected to a paired RefSeq accession when that is the best downloadable annotated target
- the resolution outcome is recorded in `accession_resolution.tsv`

### Package contents

The downloader requests annotation-focused NCBI package content:

- `cds`
- `gff3`
- `seq-report`

The current workflow does not use genomic FASTA as a required input for repeat detection.

### Sequence filtering and taxonomy

Normalization currently:

- keeps sequence-report rows from `Primary Assembly` and `non-nuclear`
- ignores alternate loci and patch units
- materializes explicit lineage rows into `taxonomy.tsv` using `taxon-weaver`
- treats a missing lineage as an error for that accession

The output taxonomy table is a run-level lookup table. It is designed for
transparent grouping and post-run joins, not for inferring taxonomy beyond what
is present in the source package and taxonomy database.

### CDS to metadata linkage

The normalizer prefers GFF-backed linkage over FASTA header heuristics. Resolution order is:

1. transcript-like GFF aliases
2. protein aliases
3. CDS aliases
4. a `cds-<gene_symbol>` fallback for rearrangement-dependent immune segment records
5. FASTA-header fallback with a warning

If two CDS rows collapse to the same normalized `sequence_id` but carry different biological content, the code expands the identifier using source-backed fields and records a warning instead of silently overwriting a row.

## Translation and Isoform Retention

Translation is intentionally conservative:

- only NCBI translation tables `1`, `2`, `5`, and `11` are supported
- ambiguous nucleotides are rejected
- non-triplet CDS lengths are rejected
- internal stop codons are rejected
- a terminal stop codon is stripped when it is the only stop
- `partial` CDS records are excluded before translation

If a CDS fails under its recorded translation table but succeeds under another supported table, the warning is surfaced as a likely translation-table mismatch rather than silently switching tables.

Protein retention is one-per-gene-group per genome:

- `gene_group` comes from the normalized sequence row
- the longest translated protein wins
- ties break lexicographically by `protein_id`

This keeps the isoform policy deterministic and easy to reproduce in tests.

## Detection Algorithms

All detection methods emit 1-based, inclusive amino-acid coordinates and the same call schema.

### Pure

Intent:

- find uninterrupted runs of the target residue

Implementation:

- scan the protein sequence once
- emit maximal contiguous runs of the target residue
- require `min_repeat_count` residues in the final tract

Default:

- `pure_min_repeat_count = 6`

### Threshold

Intent:

- find repeat-rich tracts that tolerate limited interruptions

Implementation:

- slide a fixed window across the protein
- mark windows with at least `min_target_count` target residues as positive
- merge overlapping or directly adjacent positive windows
- trim leading and trailing non-target residues from the merged interval

Defaults:

- `threshold_window_size = 8`
- `threshold_min_target_count = 6`

The emitted `window_definition` looks like `<residue><count>/<window>`, for example `Q6/8`.

### Seed-extend

Intent:

- find longer interrupted tracts with a stricter repeat-rich core

Implementation:

- find seed windows using a stricter density rule
- find extend windows using a looser rule
- merge connected seed/extend windows into components
- keep only components that contain at least one seed window
- trim non-target edges
- enforce a minimum final tract length

Defaults:

- `seed_window_size = 8`
- `seed_min_target_count = 6`
- `extend_window_size = 12`
- `extend_min_target_count = 8`
- `min_total_length = 10`

## Codon Finalization

After detection, the pipeline tries to map each amino-acid tract back onto the normalized CDS.

For a call to receive a `codon_sequence`, the finalizer must be able to:

- find the `sequence_id` in `sequences.tsv`
- find the matching CDS in `cds.fna`
- slice the nucleotide interval implied by the amino-acid coordinates
- translate that nucleotide slice under the sequence's translation table
- confirm that the translated peptide exactly matches the call `aa_sequence`

If any of those checks fail:

- the call row is still retained
- `codon_sequence` stays empty
- a warning row is written
- the codon failure does not invalidate the amino-acid call itself

The merged public codon table is `publish/tables/repeat_call_codon_usage.tsv`.
Rows are keyed to repeat-call identifiers and only represent calls where the
codon slice passed the exact translation check. Compact source context is
published separately in `publish/tables/repeat_context.tsv`.

## Public Tables and Reporting

The v2 public contract separates compact analysis tables from broad execution
artifacts. Default runs publish:

- `publish/calls/repeat_calls.tsv`
- `publish/calls/run_params.tsv`
- `publish/tables/genomes.tsv`
- `publish/tables/taxonomy.tsv`
- `publish/tables/matched_sequences.tsv`
- `publish/tables/matched_proteins.tsv`
- `publish/tables/repeat_call_codon_usage.tsv`
- `publish/tables/repeat_context.tsv`
- `publish/tables/download_manifest.tsv`
- `publish/tables/normalization_warnings.tsv`
- `publish/tables/accession_status.tsv`
- `publish/tables/accession_call_counts.tsv`
- `publish/summaries/status_summary.json`
- `publish/summaries/acquisition_validation.json`

The matched sequence and protein tables carry the retained nucleotide and
amino-acid sequence bodies directly, while broad public FASTA files remain
outside the default v2 contract.

The reporting layer is deliberately simple and residue-neutral. In
`--acquisition_publish_mode merged`, the workflow also builds SQLite and report
artifacts from the same normalized tables and repeat calls. The HTML layer is a
render artifact and does not recompute biological calls.

## Accuracy Boundaries

The workflow favors auditable failure over silent biological inference:

- accessions that cannot produce complete normalized records are represented in
  status tables instead of being silently ignored
- CDS rows with ambiguous sequence, partial records, frame problems, or internal
  stops are excluded from translated proteins
- codon slices are attached only when nucleotide translation exactly matches
  the amino-acid call
- broad intermediate FASTA and acquisition directories are internal by default;
  public outputs are compact tables with stable schemas

## Current Limitations

- The main workflow starts from assembly accessions only.
- Domain enrichment, annotation-heavy downstream biology, and bespoke residue-specific analytics are not part of the current workflow.
- SQLite and reports are available only in `merged` acquisition mode.
