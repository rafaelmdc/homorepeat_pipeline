# Development Guide

This guide is for contributors changing the pipeline, Python package, tests, or
public contracts.

## Local Setup

Use Python 3.12 and install the package in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

For workflow runs with the `docker` profile, build the runtime images:

```bash
bash scripts/build_dev_containers.sh
```

The workflow expects a taxonomy SQLite database at
`runtime/cache/taxonomy/ncbi_taxonomy.sqlite` unless `--taxonomy_db` is set.

## Repository Map

| Path | Responsibility |
| --- | --- |
| `main.nf` | Top-level Nextflow graph and workflow-output publication wiring |
| `workflows/` | Reusable Nextflow workflow fragments |
| `modules/local/` | Process definitions grouped by pipeline stage |
| `conf/` | Base, Docker, and local execution configuration |
| `src/homorepeat/cli/` | CLI entrypoints used by Nextflow processes |
| `src/homorepeat/acquisition/` | NCBI package parsing, normalization, translation, validation |
| `src/homorepeat/detection/` | Homorepeat detection algorithms and codon finalization |
| `src/homorepeat/contracts/` | Published schema and contract validation helpers |
| `src/homorepeat/runtime/` | Manifest and run metadata helpers |
| `src/homorepeat/db/` | SQLite build support |
| `src/homorepeat/reporting/` | Report table and HTML artifact generation |
| `tests/` | Unit, CLI, contract, and workflow-facing tests |

The pipeline should keep a clear boundary between internal execution artifacts
and the public `publish/` contract. Default v2 outputs are compact tables,
summaries, and metadata; broad FASTA/acquisition/status directories are not part
of the default public surface. Public artifact paths are owned by the entry
workflow's `publish:` section and top-level `output {}` block; process modules
emit structured outputs and remain reusable.

## Testing Strategy

Start with the narrowest relevant check:

```bash
env PYTHONPATH=src python -m unittest tests.unit.test_publish_contract_v2
```

Use wider checks before handing off larger changes:

```bash
env PYTHONPATH=src python -m unittest
```

For a Docker-backed smoke run:

```bash
NXF_HOME=runtime/cache/nextflow \
nextflow \
  -log runs/dev_smoke/internal/nextflow/nextflow.log \
  run . \
  -profile docker \
  -params-file examples/params/smoke_default.json \
  --run_id dev_smoke \
  --accessions_file examples/accessions/smoke_human.txt
```

For the larger live reference input, use
`examples/accessions/chr_accessions.txt` and record benchmark metadata with the
guide in [Benchmark Guide](./benchmark_guide.md).

## Contract Changes

Treat files under `publish/` as a public interface. When adding, removing, or
renaming a published artifact:

- update `src/homorepeat/contracts/` schema expectations
- update run-manifest artifact collection in `src/homorepeat/runtime/`
- update Nextflow workflow-output wiring in `main.nf`
- update contract tests and workflow tests
- update `README.md`, [Contracts](./contracts.md), and operational docs

Prefer additive contract changes. If a breaking change is required, increment
the publish contract version and document the compatibility impact.

## Adding a CLI or Process

Python CLIs should:

- validate required inputs early
- write deterministic TSV or JSON output
- fail fast with clear stderr messages
- avoid implicit network access unless the CLI is explicitly acquisition-facing
- keep schemas stable and covered by tests

Nextflow processes should:

- use labels from `conf/base.config` so resources and containers remain
  centrally controlled
- emit explicit structured files or directories for downstream workflows
- leave public contract routing to workflow outputs in `main.nf`
- keep internal scratch and broad intermediates under the run's internal state
- pass metadata through explicit files rather than parsing terminal logs

## Scientific Method Changes

Biological changes require tests that cover both accepted and rejected cases.
For example, translation changes should include ambiguous bases, non-triplet
CDS, terminal stops, internal stops, and supported translation tables.

Detection changes should preserve:

- 1-based inclusive amino-acid coordinates
- deterministic call identifiers
- residue-neutral behavior unless a method explicitly documents otherwise
- codon finalization only after exact nucleotide-slice translation validation

Document method changes in [Methods](./methods.md), including accuracy
boundaries and cases the pipeline intentionally rejects.

## Documentation Conventions

Keep the root `README.md` user-focused. Put deeper operational, architecture,
method, and development details under `docs/`.

Avoid documenting historical implementation plans as current behavior. If a page
describes the maintained public contract, it should match
`publish/metadata/run_manifest.json` and `docs/contracts.md`.

## Pre-Handoff Checklist

Before handing off non-trivial work:

- run the narrowest relevant tests
- run `git diff --check`
- inspect `git diff --stat`
- for workflow-output changes, run `tests.workflow.test_publish_modes` so the
  DAG regression guard checks anonymous-node count and removed publication
  scaffolding
- confirm docs do not mention removed public paths such as
  `publish/status/`, `publish/acquisition/`, or `publish/calls/finalized/`
  unless the text explicitly says they are not default v2 outputs
- note any tests or live workflow runs that were not executed
