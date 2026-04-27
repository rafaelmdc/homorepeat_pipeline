# Quickstart

This is the shortest path to a first HomoRepeat run.

## 1. Check Prerequisites

From the repository root:

```bash
docker --version
nextflow -version
```

You need Docker, Nextflow `25.10.4`, and internet access to Docker Hub and
NCBI.

## 2. Check The Inputs

Run the built-in smoke accession through the preflight-only path:

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt \
  --dry_run_inputs true
```

This validates the accession file, repeat-residue settings, taxonomy DB policy,
and run mode without downloading NCBI data or running detection tasks. If the
default taxonomy database is missing, the dry run reports that it will be built
during the real run.

## 3. Run The Smoke Example

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt
```

On first use, Docker pulls the published images and the workflow builds the
default taxonomy cache if needed.

## 4. Open The Results

The run writes to:

```text
runs/<run_id>/publish/
```

Open these first:

```text
START_HERE.md
calls/repeat_calls.tsv
tables/accession_status.tsv
tables/accession_call_counts.tsv
metadata/nextflow/report.html
```

`repeat_calls.tsv` is the main biological result table. A successful accession
can still have zero matching repeat calls, so use the accession status tables to
separate no-call results from failed accessions.

## 5. Run Your Own Accessions

Create one accession per line:

```bash
mkdir -p inputs
printf '%s\n' GCF_000001405.40 GCF_000001635.27 > inputs/my_accessions.txt
```

Validate:

```bash
nextflow run . \
  -profile docker \
  --accessions_file inputs/my_accessions.txt \
  --repeat_residues Q,N \
  --dry_run_inputs true
```

Run:

```bash
nextflow run . \
  -profile docker \
  --accessions_file inputs/my_accessions.txt \
  --repeat_residues Q,N
```

For named, resumable production-style commands, see
[Operations](./operations.md).
