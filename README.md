# HomoRepeat

HomoRepeat finds single-amino-acid homorepeats in proteins from annotated NCBI
assemblies. You give it a list of assembly accessions, for example
`GCF_000001405.40`, and it downloads the annotations, translates coding
sequences, calls repeat tracts, checks codons where possible, and writes tidy
tables for downstream analysis.

The first sections below are written for biologists who want to run the
pipeline. Developer and implementation details are later in this README and in
[`docs/`](./docs/).

## What You Need

- Linux or macOS shell with Docker available.
- Nextflow `25.10.4`.
- Internet access to download NCBI assembly packages.
- Internet access to pull the published HomoRepeat Docker images on first use.
- One text file with one NCBI assembly accession per line.
- A local NCBI taxonomy SQLite database, which the pipeline creates
  automatically on the first default run if it is missing.

Important taxonomy database answer:

**The main Nextflow pipeline now auto-builds the default taxonomy database when
it is missing.** The default cache path is:

```text
runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

The database is reused across runs. If you pass an explicit `--taxonomy_db`,
that file must already exist; explicit paths are treated as user-managed inputs.

## One-Time Setup

Run these commands from the repository root.

### 1. Check Docker and Nextflow

```bash
docker --version
nextflow -version
```

The normal `-profile docker` run uses published images and Docker pulls them
automatically when they are missing:

- `rafaelmdc/homorepeat-acquisition:0.1.0`
- `rafaelmdc/homorepeat-detection:0.1.0`

You only need to build local `:dev` images if you are changing the code. See
the developer notes later in this README.

### 2. Run without manual taxonomy setup

No manual taxonomy command is needed for the standard path. On the first run,
the pipeline builds:

```text
runtime/cache/taxonomy/ncbi_taxonomy.sqlite
runtime/cache/taxonomy/taxdump.tar.gz
runtime/cache/taxonomy/ncbi_taxonomy_build.json
```

Manual build remains available for controlled or offline-style environments:

```bash
mkdir -p runtime/cache/taxonomy
docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "$PWD":/work \
  -w /work \
  rafaelmdc/homorepeat-acquisition:0.1.0 \
  taxon-weaver build-db \
    --download \
    --dump runtime/cache/taxonomy/taxdump.tar.gz \
    --db runtime/cache/taxonomy/ncbi_taxonomy.sqlite \
    --report-json runtime/cache/taxonomy/ncbi_taxonomy_build.json
```

Check that it exists:

```bash
ls -lh runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

Optional provenance check:

```bash
docker run --rm \
  -v "$PWD":/work \
  -w /work \
  rafaelmdc/homorepeat-acquisition:0.1.0 \
  taxon-weaver build-info \
    --db runtime/cache/taxonomy/ncbi_taxonomy.sqlite
```

## Quick Start

Validate the checked-in human smoke example without downloading data or running
detection tasks:

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt \
  --dry_run_inputs true
```

Run the checked-in human smoke example:

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt
```

Results will be under a timestamped folder in `runs/`.

For a named, resumable run:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/smoke_human/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  -params-file examples/params/smoke_default.json \
  --run_id smoke_human \
  --accessions_file examples/accessions/smoke_human.txt
```

Named-run results will be under:

```text
runs/smoke_human/publish/
```

If the run is interrupted and you want to continue the same run:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/smoke_human/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  -params-file examples/params/smoke_default.json \
  --run_id smoke_human \
  --accessions_file examples/accessions/smoke_human.txt \
  -resume
```

## Run Your Own Accessions

Create an accession list. Use assembly accessions, one per line. Lines starting
with `#` and blank lines are ignored.

```bash
mkdir -p inputs

printf '%s\n' \
  GCF_000001405.40 \
  GCF_000001635.27 \
  > inputs/my_accessions.txt
```

Run glutamine (`Q`) and asparagine (`N`) repeats with the default `pure` and
`threshold` methods:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/my_qn_run/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id my_qn_run \
  --accessions_file inputs/my_accessions.txt \
  --repeat_residues Q,N \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend false
```

To also produce SQLite and HTML report artifacts, add
`--acquisition_publish_mode merged`:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/my_qn_merged/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  --run_id my_qn_merged \
  --accessions_file inputs/my_accessions.txt \
  --repeat_residues Q,N \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend false \
  --acquisition_publish_mode merged
```

If you have an NCBI API key, pass it explicitly:

```bash
--ncbi_api_key "$NCBI_API_KEY"
```

## What To Look At First

Default outputs are written to `runs/<run_id>/publish/`.

Most useful files:

| File | What it means |
| --- | --- |
| `START_HERE.md` | Run-specific guide with the key settings and first files to inspect |
| `calls/repeat_calls.tsv` | One row per detected amino-acid repeat tract |
| `calls/run_params.tsv` | The method parameters used for each residue |
| `tables/matched_proteins.tsv` | Protein sequences that had at least one repeat call |
| `tables/matched_sequences.tsv` | CDS nucleotide sequences linked to repeat calls |
| `tables/repeat_call_codon_usage.tsv` | Codon counts for calls where codon validation succeeded |
| `tables/repeat_context.tsv` | Compact sequence context around each repeat |
| `tables/taxonomy.tsv` | Taxonomy rows used for grouping and joins |
| `tables/accession_status.tsv` | Per-accession status, including failed or no-call accessions |
| `summaries/status_summary.json` | Run-level success/failure summary |
| `metadata/nextflow/report.html` | Nextflow execution report |

In `--acquisition_publish_mode merged`, these are also produced:

- `database/homorepeat.sqlite`
- `database/sqlite_validation.json`
- `reports/*`

A successful accession can have zero repeat calls. Use
`tables/accession_status.tsv` and `tables/accession_call_counts.tsv` to
separate "the accession failed" from "the accession ran and no matching repeats
were found".

## Main Parameters

| Parameter | Default | Use |
| --- | --- | --- |
| `--accessions_file` | required | Text file with one assembly accession per line |
| `--dry_run_inputs` | `false` | Validate inputs and settings, then stop before downloading data or running detection |
| `--taxonomy_db` | `runtime/cache/taxonomy/ncbi_taxonomy.sqlite` | Taxonomy SQLite database to use; default path is auto-built if missing |
| `--taxonomy_auto_build` | `true` | Build the default taxonomy DB when missing and `--taxonomy_db` was not explicitly supplied |
| `--taxonomy_cache_dir` | `runtime/cache/taxonomy` | Cache directory for the auto-built taxonomy DB |
| `--run_id` | timestamped | Names `runs/<run_id>` |
| `--repeat_residues` | `Q` | Comma-separated one-letter amino-acid codes, for example `Q,N` |
| `--run_pure` | `true` | Detect uninterrupted repeat runs |
| `--run_threshold` | `true` | Detect repeat-rich windows with limited interruptions |
| `--run_seed_extend` | `false` | Detect longer interrupted repeat-rich tracts |
| `--batch_size` | `10` | Number of accessions per download/normalization batch |
| `--acquisition_publish_mode` | `raw` | `raw` writes compact tables; `merged` also builds SQLite/reports |
| `--ncbi_api_key` | unset | Optional NCBI API key for downloads |

For CPU, memory, and larger-run settings, see
[`docs/scale_guide.md`](./docs/scale_guide.md).

## Biological Scope

HomoRepeat reports amino-acid repeat tracts from translated annotated CDS
records. It does not infer new gene models, repair assemblies, annotate protein
domains, or decide whether a repeat is biologically meaningful. Those
interpretations should be done downstream using the published tables.

Built-in safeguards:

- accessions are tracked through status tables instead of silently disappearing
- translation is conservative and rejects ambiguous or frame-problem CDS records
- one protein isoform is retained per gene group in a deterministic way
- codon sequences are attached only when the nucleotide slice translates exactly
  to the called amino-acid repeat
- output tables use stable identifiers so calls, proteins, CDS records, genomes,
  taxonomy, SQLite, and reports can be joined reproducibly

See [`docs/methods.md`](./docs/methods.md) for biological assumptions and
algorithm details.

## Background: What The Jargon Means

- **Accession**: an NCBI identifier for an assembly, such as
  `GCF_000001405.40`.
- **CDS**: coding DNA sequence. The pipeline translates CDS records into
  proteins before detecting repeats.
- **Homorepeat**: a tract enriched for one amino acid, such as a polyglutamine
  (`Q`) repeat.
- **Taxonomy database**: a local SQLite file built from NCBI taxonomy. The
  pipeline uses it to attach lineages to accessions.
- **taxon-weaver**: the tool used to build and query that taxonomy database.
- **Nextflow**: the workflow runner. It decides which tasks run and resumes
  completed work with `-resume`.
- **Docker profile**: tells Nextflow to run each task inside the pinned runtime
  image instead of relying on tools installed on your host machine.
- **`runs/<run_id>/publish/`**: the human-facing result folder.
- **`runs/<run_id>/internal/`**: intermediate files and Nextflow work state.
  These are useful for debugging but are not the main analysis output.
- **TSV**: tab-separated table. These files open in R, Python, Excel, LibreOffice,
  and command-line tools.
- **SQLite**: a single-file database. HomoRepeat builds it only in
  `--acquisition_publish_mode merged`.

More background is in [`docs/background.md`](./docs/background.md).

## Code Structure

| Path | Role |
| --- | --- |
| [`main.nf`](./main.nf) | Top-level Nextflow workflow and output publication |
| [`workflows/`](./workflows) | Stage-level Nextflow subworkflows |
| [`modules/local/`](./modules/local) | Individual Nextflow process wrappers |
| [`src/homorepeat/cli/`](./src/homorepeat/cli) | Python commands called by Nextflow |
| [`src/homorepeat/acquisition/`](./src/homorepeat/acquisition) | NCBI package, GFF, translation, validation helpers |
| [`src/homorepeat/detection/`](./src/homorepeat/detection) | Repeat detection, codon slicing, repeat context |
| [`src/homorepeat/contracts/`](./src/homorepeat/contracts) | Shared table schemas and validators |
| [`src/homorepeat/runtime/`](./src/homorepeat/runtime) | Run manifest, status ledgers, publish reducers |
| [`src/homorepeat/db/`](./src/homorepeat/db) | SQLite import and validation |
| [`src/homorepeat/reporting/`](./src/homorepeat/reporting) | Summary and HTML report generation |
| [`tests/`](./tests) | Unit, CLI, and workflow regression tests |

## Development Checks

When changing code that runs inside Docker, rebuild local images and use the
development profile:

```bash
bash scripts/build_dev_containers.sh
nextflow run . -profile docker_dev --accessions_file examples/accessions/smoke_human.txt
```

```bash
nextflow config .
env PYTHONPATH=src python -m unittest
```

Focused publish-contract regression:

```bash
env PYTHONPATH=src python -m unittest \
  tests.unit.test_publish_contract_v2 \
  tests.unit.test_repeat_context \
  tests.cli.test_export_publish_tables \
  tests.cli.test_export_repeat_context \
  tests.cli.test_merge_codon_usage_tables \
  tests.cli.test_runtime_artifacts \
  tests.workflow.test_publish_modes \
  tests.workflow.test_workflow_output_failures
```

See [`docs/development.md`](./docs/development.md) for repo conventions and
test strategy.

## Documentation

- [Documentation Index](./docs/README.md)
- [Quickstart](./docs/quickstart.md)
- [Operations](./docs/operations.md)
- [Background and Glossary](./docs/background.md)
- [Methods and Scientific Notes](./docs/methods.md)
- [Data Contracts](./docs/contracts.md)
- [Containers](./docs/containers.md)
- [Accession Examples](./examples/accessions/README.md)
- [Output Examples](./examples/outputs/README.md)
- [Scale Guide](./docs/scale_guide.md)
- [Benchmark Guide](./docs/benchmark_guide.md)
- [Resume and Recovery](./docs/save_state_guide.md)
- [Development Guide](./docs/development.md)

## License

See [LICENSE](./LICENSE).
