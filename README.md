# HomoRepeat

HomoRepeat is a Nextflow pipeline for accession-driven homorepeat analysis. It downloads annotated assemblies, normalizes CDS records, translates proteins, detects single-residue amino-acid homorepeats, validates codon slices where possible, and publishes a compact v2 tabular contract for downstream import.

The workflow orchestration is Nextflow. The scientific and contract logic is Python under [`src/homorepeat/`](./src/homorepeat/).

## What This Repo Provides

- Accession-list workflow entrypoint through `nextflow run .`
- Docker and local execution profiles
- NCBI Datasets acquisition with `taxon-weaver` lineage materialization
- Three detection methods: `pure`, `threshold`, and optional `seed_extend`
- Canonical v2 publish contract under `runs/<run_id>/publish/tables/`
- Optional SQLite and report artifacts in `--acquisition_publish_mode merged`
- Unit, CLI, and workflow regression tests

Not included: web UI, local FASTA/GFF manifest workflow entrypoint, domain enrichment, or broad arbitrary Nextflow-version support.

## Requirements

- Nextflow `25.10.4`
- Docker for the `docker` profile
- Runtime images built from this repo
- Taxonomy SQLite database at `runtime/cache/taxonomy/ncbi_taxonomy.sqlite`, unless `--taxonomy_db` is supplied

Build runtime images:

```bash
bash scripts/build_dev_containers.sh
```

## Quick Start

Run a small checked-in example:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id smoke_human \
  --accessions_file examples/accessions/smoke_human.txt
```

Run the chromosome-scale example list:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id chr_v2 \
  --accessions_file examples/accessions/chr_accessions.txt \
  -resume
```

The canonical operator interface is `nextflow run .`; there is no repo-specific wrapper.

## Pipeline Stages

1. `PLAN_ACCESSION_BATCHES` reads accession input and writes deterministic batches.
2. `DOWNLOAD_NCBI_BATCH` downloads NCBI annotation packages.
3. `NORMALIZE_CDS_BATCH` creates canonical genome, taxonomy, sequence, and CDS artifacts internally.
4. `TRANSLATE_CDS_BATCH` translates retained CDS records and keeps one protein isoform per gene group.
5. Detection runs `pure`, `threshold`, and optionally `seed_extend` for each `batch_id x repeat_residue`.
6. `FINALIZE_CALL_CODONS` validates codon slices and writes codon-usage fragments.
7. Reporting reducers publish canonical calls, v2 flat tables, summaries, and repeat context.
8. In `merged` mode, SQLite and HTML/JSON report artifacts are also built.

## Default Published Outputs

Default publication uses publish contract v2. The public tree is compact and import-oriented:

```text
runs/<run_id>/publish/
  calls/
    repeat_calls.tsv
    run_params.tsv
  tables/
    genomes.tsv
    taxonomy.tsv
    matched_sequences.tsv
    matched_proteins.tsv
    repeat_call_codon_usage.tsv
    repeat_context.tsv
    download_manifest.tsv
    normalization_warnings.tsv
    accession_status.tsv
    accession_call_counts.tsv
  summaries/
    status_summary.json
    acquisition_validation.json
  metadata/
    launch_metadata.json
    run_manifest.json
    nextflow/
```

The default v2 contract does not publish `acquisition/`, `status/`, `calls/finalized/`, `cds.fna`, or `proteins.faa`. Those broad artifacts are internal execution products. Compact repeat context and matched sequence/protein tables replace public FASTA publication; the matched tables include the retained nucleotide and amino-acid sequence bodies.

In `--acquisition_publish_mode merged`, the workflow additionally publishes:

- `publish/database/homorepeat.sqlite`
- `publish/database/sqlite_validation.json`
- `publish/reports/*`

The v2 contract remains the public import surface in both modes.

## Common Parameters

| Parameter | Default | Purpose |
| --- | --- | --- |
| `--accessions_file` | required | One assembly accession per line |
| `--taxonomy_db` | `runtime/cache/taxonomy/ncbi_taxonomy.sqlite` | `taxon-weaver` SQLite database |
| `--run_id` | timestamped | Names `runs/<run_id>` |
| `--run_root` | `runs/<run_id>` | Run root |
| `--work_dir` | `runs/<run_id>/internal/nextflow/work` | Nextflow work directory |
| `--repeat_residues` | `Q` | Comma-separated residue codes |
| `--run_pure` | `true` | Contiguous-run detection |
| `--run_threshold` | `true` | Sliding-window density detection |
| `--run_seed_extend` | `false` | Seed-and-extend detection |
| `--batch_size` | `10` | Planner batch size |
| `--acquisition_publish_mode` | `raw` | `merged` also builds SQLite/reports |

For CPU, memory, and concurrency controls such as `-qs` and
`-process.withLabel:<label>.maxForks`, see [Scale Guide](./docs/scale_guide.md).

Example with method overrides:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow run . \
  -profile docker \
  --run_id qn_all_methods \
  --accessions_file examples/accessions/my_accessions.txt \
  --repeat_residues Q,N \
  --run_pure true \
  --run_threshold true \
  --run_seed_extend true
```

Params files are supported with `-params-file`; see [`examples/params/`](./examples/params/).

## Code Structure

| Path | Role |
| --- | --- |
| [`main.nf`](./main.nf) | Top-level workflow, output publication, completion hook |
| [`workflows/`](./workflows) | Stage-level Nextflow subworkflows |
| [`modules/local/`](./modules/local) | Individual Nextflow process wrappers |
| [`src/homorepeat/cli/`](./src/homorepeat/cli) | Python CLIs called by Nextflow |
| [`src/homorepeat/acquisition/`](./src/homorepeat/acquisition) | NCBI package, GFF, translation, validation helpers |
| [`src/homorepeat/detection/`](./src/homorepeat/detection) | Repeat detection, codon slicing, repeat context |
| [`src/homorepeat/contracts/`](./src/homorepeat/contracts) | Shared table schemas and validators |
| [`src/homorepeat/runtime/`](./src/homorepeat/runtime) | Run manifest, status ledgers, publish reducers |
| [`src/homorepeat/db/`](./src/homorepeat/db) | SQLite import and validation |
| [`src/homorepeat/reporting/`](./src/homorepeat/reporting) | Summary and HTML report generation |
| [`tests/`](./tests) | Unit, CLI, and workflow regression tests |

## Scientific Accuracy Boundaries

HomoRepeat reports amino-acid repeat tracts from translated annotated CDS records. It does not infer gene models, repair assemblies, or perform domain-level biological interpretation.

Accuracy controls implemented in code:

- source-backed stable identifiers for genomes, sequences, proteins, and calls
- conservative translation with supported NCBI translation tables
- deterministic isoform retention
- shared repeat-call schema across methods
- codon slices only accepted when nucleotide translation exactly matches the call peptide
- compact flanking context exported for downstream review without publishing full FASTA bodies

See [Methods and Scientific Notes](./docs/methods.md) for algorithm details and limitations.

## Development

Useful checks:

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

See [Development Guide](./docs/development.md) for repo conventions and test strategy.

## Documentation

- [Documentation Index](./docs/README.md)
- [Operations](./docs/operations.md)
- [Architecture](./docs/architecture.md)
- [Methods and Scientific Notes](./docs/methods.md)
- [Data Contracts](./docs/contracts.md)
- [Development Guide](./docs/development.md)
- [Containers](./docs/containers.md)
- [Scale Guide](./docs/scale_guide.md)
- [Benchmark Guide](./docs/benchmark_guide.md)
- [Resume and Recovery](./docs/save_state_guide.md)

## License

See [LICENSE](./LICENSE).
