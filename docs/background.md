# Background and Glossary

This page explains the terms used in the HomoRepeat docs. It is background
reading; you do not need to understand every implementation detail to run the
pipeline.

## What HomoRepeat Does

HomoRepeat starts from NCBI assembly accessions and asks:

> Which translated proteins contain amino-acid tracts enriched for a selected
> residue, such as glutamine (`Q`) or asparagine (`N`)?

The pipeline path is:

```text
assembly accession
  -> NCBI annotation package
  -> normalized CDS records
  -> translated proteins
  -> repeat calls
  -> codon checks where possible
  -> published tables
```

It does not infer new genes or decide whether a repeat has biological function.
It reports auditable tables for downstream interpretation.

## Biological Terms

### Assembly accession

An NCBI identifier for a genome assembly, for example `GCF_000001405.40`.
HomoRepeat expects an accession list with one assembly accession per line.

`GCF_` accessions are RefSeq assemblies. `GCA_` accessions are GenBank
assemblies. During planning, the pipeline may resolve a GenBank accession to a
paired downloadable RefSeq accession when that is the best annotated target.

### CDS

CDS means coding DNA sequence. The pipeline uses annotated CDS records from
NCBI packages, translates them into amino-acid sequences, and searches those
proteins for repeats.

### Protein isoform

An annotated gene can have more than one protein product. HomoRepeat keeps one
translated protein per gene group per genome. The longest protein is retained;
ties are broken deterministically by protein ID.

### Homorepeat

A homorepeat is a region dominated by one repeated amino acid. A strict example
is `QQQQQQ`. Interrupted repeat-rich regions can also be detected by the
`threshold` and `seed_extend` methods.

### Repeat residue

The one-letter amino-acid code being searched. Examples:

- `Q` for glutamine
- `N` for asparagine
- `A` for alanine

Multiple residues are passed as comma-separated values:

```bash
--repeat_residues Q,N
```

### Codon validation

After a repeat is found in protein coordinates, HomoRepeat tries to map the
amino-acid tract back to the CDS nucleotides. A codon sequence is attached only
when the nucleotide slice translates exactly to the called amino-acid sequence.

If codon validation fails, the amino-acid repeat call is still kept and the
codon fields stay empty.

## Taxonomy Terms

### NCBI taxonomy

NCBI taxonomy is the species and lineage system used by NCBI. HomoRepeat uses
it to add taxon IDs, taxon names, ranks, and parent-child lineage rows to the
published `taxonomy.tsv` table.

### Taxonomy database

In this project, the taxonomy database is a local SQLite file built from the
NCBI taxonomy dump. The default path is:

```text
runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

The default run creates this file automatically if it is missing. If you pass
an explicit `--taxonomy_db`, that file must already exist.

### taxon-weaver

`taxon-weaver` is the command-line tool used to build and query the taxonomy
database. The acquisition Docker image includes a pinned version of
`taxon-weaver`.

The manual setup command, for controlled environments, is:

```bash
mkdir -p runtime/cache/taxonomy

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$PWD":/work \
  -w /work \
  homorepeat-acquisition:dev \
  taxon-weaver build-db \
    --download \
    --dump runtime/cache/taxonomy/taxdump.tar.gz \
    --db runtime/cache/taxonomy/ncbi_taxonomy.sqlite \
    --report-json runtime/cache/taxonomy/ncbi_taxonomy_build.json
```

## Workflow Terms

### Nextflow

Nextflow is the workflow engine. It runs the pipeline stages, tracks completed
work, and supports resuming with `-resume`.

HomoRepeat's main command is:

```bash
nextflow run .
```

### Profile

A Nextflow profile selects runtime settings. The usual profile is:

```bash
-profile docker
```

That tells Nextflow to run tasks in the project Docker images.

### Docker image

A Docker image is a packaged software environment. HomoRepeat uses two:

- `homorepeat-acquisition:dev` for NCBI downloads, taxonomy lookup, and
  translation-related setup
- `homorepeat-detection:dev` for repeat detection, SQLite, and reporting

This keeps runs reproducible and avoids relying on many host-installed tools.

### `NXF_HOME`

`NXF_HOME` is where Nextflow stores its own framework cache. The docs set it to
a project-local path:

```bash
NXF_HOME=runtime/cache/nextflow
```

This keeps Nextflow state in `runtime/cache/nextflow` instead of a user-global
location.

### Run ID

`--run_id` names a run. Results go under:

```text
runs/<run_id>/publish/
```

Use a stable `--run_id` when you want to resume the same run.

### Work directory

The work directory contains staged task inputs, temporary files, and task-level
outputs used by Nextflow. By default it is:

```text
runs/<run_id>/internal/nextflow/work
```

For large runs, put `--work_dir` on fast local scratch if available.

### Publish directory

The publish directory is the main result folder:

```text
runs/<run_id>/publish/
```

This is the folder to inspect, archive, or import into downstream tools.

### Resume

`-resume` tells Nextflow to reuse completed tasks from the previous run cache.
Use it after an interrupted run with the same command and same run root.

## File Terms

### TSV

TSV means tab-separated values. It is a plain-text table format. HomoRepeat uses
TSV for the main analysis outputs because it is easy to open in R, Python,
Excel, LibreOffice, and command-line tools.

### JSON

JSON is a structured text format used here for run summaries, manifests, and
validation reports.

### SQLite

SQLite is a database stored in one file. HomoRepeat can build
`publish/database/homorepeat.sqlite`, but only when the run uses:

```bash
--acquisition_publish_mode merged
```

The default `raw` mode writes the main TSV/JSON contract and skips SQLite/report
building.

## Output Terms

### `repeat_calls.tsv`

The main table. Each row is one detected repeat tract.

### `matched_proteins.tsv`

Protein sequences that are referenced by at least one repeat call.

### `matched_sequences.tsv`

CDS nucleotide sequences that are referenced by at least one repeat call.

### `repeat_call_codon_usage.tsv`

Codon counts for repeat calls where codon validation succeeded.

### `repeat_context.tsv`

Compact sequence context around each repeat call.

### `accession_status.tsv`

Per-accession status. Use this to distinguish a failed accession from an
accession that ran successfully and produced no repeat calls.

### `run_manifest.json`

Machine-readable record of the effective parameters, enabled methods, publish
mode, taxonomy database path, and top-level artifacts.
