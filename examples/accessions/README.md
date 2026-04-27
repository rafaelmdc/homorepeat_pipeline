# Accession Examples

HomoRepeat starts from NCBI assembly accessions. Put one accession per line in a
plain text file.

Valid input lines look like:

```text
GCF_000001405.40
GCF_000001635.27
```

Rules:

- blank lines are ignored
- lines starting with `#` are ignored
- duplicate accessions are removed while preserving order
- RefSeq `GCF_` accessions are the simplest choice for first runs
- GenBank `GCA_` accessions may be resolved to a paired downloadable RefSeq
  accession when NCBI reports one

Checked-in examples:

| File | Purpose |
| --- | --- |
| `smoke_human.txt` | One small smoke-test input using the human reference accession |
| `my_accessions.txt` | A tiny two-accession example for documentation commands |
| `chr_accessions.txt` | A larger example list for broader exploratory runs |

Before a full run, validate the file without downloading data:

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt \
  --dry_run_inputs true
```

Choose accessions from NCBI Assembly or Datasets. Prefer current annotated
assemblies, because the pipeline needs downloadable annotation packages with CDS
records.
