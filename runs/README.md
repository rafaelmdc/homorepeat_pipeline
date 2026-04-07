# Runs

Published workflow runs live here.

Expected layout:
- `runs/<run_id>/internal/`: execution state, planning artifacts, batch-local files, and Nextflow internals
- `runs/<run_id>/publish/`: stable downstream artifacts for SQLite, Postgres loaders, and the future Django app
- `runs/latest`: symlink to the most recent successful wrapper-managed run
