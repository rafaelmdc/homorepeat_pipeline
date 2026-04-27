# HomoRepeat

HomoRepeat finds single-amino-acid repeat tracts in proteins from annotated
NCBI assemblies. You give it NCBI assembly accessions such as
`GCF_000001405.40`; it downloads the annotation packages, translates CDS
records, calls amino-acid repeats, checks codons where possible, and writes
plain tables for downstream analysis.

## Quick Start

You need Docker, Java 17+, and a recent stable Nextflow release.
The pipeline is tested with Nextflow 25.10.4. Use that version or a newer stable release if possible.
Run commands from the repository root.

First validate the checked-in smoke input without downloading NCBI annotation packages:

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt \
  --dry_run_inputs true
```

Success looks like:

```text
HomoRepeat input dry run passed.
Usable accessions: 1
Repeat residues: Q
```

Then run the smoke example:

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt
```

The first real run may take longer because Docker pulls the published images
and the workflow builds the default taxonomy cache if it is missing. You do not
need to build local Docker images or create the taxonomy database manually for
the normal path.

When the run finishes, open:

```text
runs/<run_id>/publish/START_HERE.md
```

That file points to the main result tables for that run.

## Run Your Own Accessions

Create a plain text file containing one NCBI assembly accession per line.

Example: `inputs/my_accessions.txt`

```text
GCF_000001405.40
GCF_000001635.27
```

Validate it:

```bash
nextflow run . \
  -profile docker \
  --accessions_file inputs/my_accessions.txt \
  --repeat_residues Q,A \
  --dry_run_inputs true
```

Run it:

```bash
nextflow run . \
  -profile docker \
  --accessions_file inputs/my_accessions.txt \
  --repeat_residues Q,A
```

For a named run that is easier to resume and inspect:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/my_qn_run/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id my_qn_run \
  --accessions_file inputs/my_accessions.txt \
  --repeat_residues Q,A
```

Resume an interrupted named run by re-running the same command with `-resume`.

## What To Open First

Default outputs are written under:

```text
runs/<run_id>/publish/
```

Start here:

| File | Use |
| --- | --- |
| `START_HERE.md` | Run-specific guide to settings and outputs |
| `calls/repeat_calls.tsv` | Main repeat-call table |
| `tables/accession_status.tsv` | Per-accession completed, failed, or no-call status |
| `tables/accession_call_counts.tsv` | Number of calls per accession, method, and residue |
| `tables/repeat_context.tsv` | Amino-acid and nucleotide context around each repeat |
| `tables/repeat_call_codon_usage.tsv` | Codon counts for calls with validated codon slices |
| `metadata/nextflow/report.html` | Runtime report for debugging |

A successful accession can produce zero repeat calls. Check
`tables/accession_status.tsv` and `tables/accession_call_counts.tsv` before
treating an empty or small `repeat_calls.tsv` as a failure.

## How It Works

At a high level, the workflow does this:

```text
assembly accessions
  -> NCBI annotation packages
  -> normalized CDS records
  -> translated proteins
  -> repeat calls
  -> codon checks
  -> published tables
```

The default search looks for glutamine (`Q`) repeats with the `pure` and
`threshold` methods. Use `--repeat_residues Q,N` or another comma-separated
list to search additional amino acids. Use `--run_seed_extend true` to enable
the third repeat-detection method.

The normal Docker profile uses published runtime images:

- `rafaelmdc/homorepeat-acquisition:0.1.0`
- `rafaelmdc/homorepeat-detection:0.1.0`

The default taxonomy database is cached at:

```text
runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

If it is missing and you did not pass `--taxonomy_db`, the workflow builds it
automatically and reuses it on later runs. If you pass an explicit
`--taxonomy_db /path/to/db.sqlite`, that file must already exist.

## Common Options

| Goal | Option |
| --- | --- |
| Validate inputs only | `--dry_run_inputs true` |
| Name the result folder | `--run_id my_run_name` |
| Search multiple residues | `--repeat_residues Q,N` |
| Enable seed-and-extend calls | `--run_seed_extend true` |
| Build SQLite and report artifacts | `--acquisition_publish_mode merged` |
| Use an NCBI API key | `--ncbi_api_key "$NCBI_API_KEY"` |
| Resume interrupted work | Add `-resume` to the same command |

## Where To Read Next

- [Quickstart](./docs/quickstart.md): shortest guided first run.
- [Operations](./docs/operations.md): fuller runbook, troubleshooting, resume,
  and output layout.
- [Accession Examples](./examples/accessions/README.md): choosing and
  validating assembly accession files.
- [Output Examples](./examples/outputs/README.md): tiny example output snippets.
- [Methods and Scientific Notes](./docs/methods.md): biological assumptions and
  detection methods.
- [Data Contracts](./docs/contracts.md): schemas for published files.
- [Containers](./docs/containers.md): Docker images and local development
  image workflow.
- [Development Guide](./docs/development.md): contributor setup and tests.

## Development

Only build local `:dev` Docker images when changing code or Dockerfiles:

```bash
bash scripts/build_dev_containers.sh
nextflow run . -profile docker_dev --accessions_file examples/accessions/smoke_human.txt
```

Basic checks:

```bash
nextflow config .
env PYTHONPATH=src python -m unittest
```

## License

See [LICENSE](./LICENSE).
