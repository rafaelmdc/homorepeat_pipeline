# Runtime

This directory is reserved for generated runtime state that should not live beside source code.

Current intended contents:
- `cache/taxonomy/`: reusable taxonomy databases and downloaded taxdump inputs
- `cache/ncbi/`: reusable NCBI download cache
- `cache/nextflow/`: persistent `NXF_HOME` data such as framework downloads

Published run artifacts belong under `runs/`, not here.
