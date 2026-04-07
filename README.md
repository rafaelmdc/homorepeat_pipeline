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
docker compose build pipeline-acquisition pipeline-detection
bash scripts/run_phase4_pipeline.sh examples/accessions/smoke_human.txt
```
