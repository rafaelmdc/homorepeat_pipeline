# HomoRepeat Pipeline

This product root owns the Nextflow workflow, package-backed CLIs, runtime images, tests, examples, runtime caches, and published run artifacts.

Key paths:
- `main.nf`
- `nextflow.config`
- `conf/`
- `modules/`
- `workflows/`
- `scripts/`
- `src/homorepeat/`
- `tests/`
- `examples/`
- `runtime/`
- `runs/`

Typical entrypoints:

```bash
python3 -m pip install -e .
bash scripts/build_dev_containers.sh
bash scripts/run_phase4_pipeline.sh examples/accessions/smoke_human.txt
```

For Docker-backed runs:

```bash
HOMOREPEAT_PHASE4_PROFILE=docker \
bash scripts/run_phase4_pipeline.sh examples/accessions/smoke_human.txt
```

Published run artifacts live under `runs/<run_id>/publish/`, including:
- canonical acquisition outputs in `publish/acquisition/`
- canonical merged calls in `publish/calls/`
- accession status ledgers in `publish/status/`
- the stable run manifest in `publish/manifest/run_manifest.json`
