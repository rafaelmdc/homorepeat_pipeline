# Containers

## Overview

The `docker` profile uses two runtime images so acquisition and downstream analysis do not carry the same external toolchain.

| Image | Dockerfile | Used by labels | Main tools |
| --- | --- | --- | --- |
| `homorepeat-acquisition:dev` | `containers/acquisition.Dockerfile` | `planning`, `acquisition_download`, `acquisition_normalize`, `acquisition_translate`, `acquisition_merge` | Python 3.12, `taxon-weaver`, NCBI `datasets`, NCBI `dataformat`, installed `homorepeat` package |
| `homorepeat-detection:dev` | `containers/detection.Dockerfile` | `detection`, `database`, `reporting` | Python 3.12 and installed `homorepeat` package |

This split matches the workflow:

- acquisition tasks need NCBI and taxonomy tooling
- detection/reporting tasks do not

## Build

Fast path:

```bash
bash scripts/build_dev_containers.sh
```

That script uses `docker compose build` when `compose.yaml` is available and otherwise falls back to direct `docker build` commands.

Equivalent manual builds:

```bash
docker build -f containers/acquisition.Dockerfile -t homorepeat-acquisition:dev .
docker build -f containers/detection.Dockerfile -t homorepeat-detection:dev .
```

## Tooling and Pins

The acquisition image currently:

- installs `taxon-weaver` from the pinned commit `aff9709a82ac09fa3f97a71cca809f8e8f98c213`
- downloads the current Linux AMD64 `datasets` and `dataformat` binaries from NCBI's v2 command-line distribution
- installs the local `homorepeat` package from this repo

The detection image:

- installs the local `homorepeat` package
- does not include `taxon-weaver`, `datasets`, or `dataformat`

What is intentionally not baked into either image:

- the taxonomy SQLite database
- NCBI download caches
- run-specific inputs and outputs

Those are runtime artifacts and should remain outside the image.

The acquisition image contains `taxon-weaver`, so it can build the taxonomy
database. Default runs build `runtime/cache/taxonomy/ncbi_taxonomy.sqlite`
automatically when it is missing. See
[Operations](./operations.md#taxonomy-database) for details and manual build
commands.

## How Nextflow Uses the Images

The `docker` profile keeps `process.executor = 'local'` and binds containers by label in `conf/docker.config`.

Current label mapping:

- `planning` -> acquisition image
- `acquisition_download` -> acquisition image
- `acquisition_normalize` -> acquisition image
- `acquisition_translate` -> acquisition image
- `acquisition_merge` -> acquisition image
- `detection` -> detection image
- `database` -> detection image
- `reporting` -> detection image

Important detail:

- the images already contain the installable package
- Nextflow stages task inputs into work directories, so the `docker` profile does not need a manual repo bind mount for normal pipeline execution

## Smoke Checks

Quick sanity checks after a build:

```bash
docker run --rm homorepeat-acquisition:dev python --version
docker run --rm homorepeat-acquisition:dev taxon-weaver --help
docker run --rm homorepeat-acquisition:dev datasets version
docker run --rm homorepeat-acquisition:dev dataformat --help
docker run --rm homorepeat-detection:dev python --version
```

## Manual `docker run` Notes

For ad hoc container debugging outside Nextflow, mount the repo and any required caches explicitly.

Example acquisition-side command:

```bash
docker run --rm \
  -v "$PWD":/work \
  -v "$PWD/runtime/cache/taxonomy":/data/taxonomy \
  -w /work \
  homorepeat-acquisition:dev \
  python -m homorepeat.cli.plan_accession_batches \
  --accessions-file examples/accessions/smoke_human.txt \
  --outdir /tmp/homorepeat_planning
```

If you want reusable NCBI downloads during manual work, also mount a cache directory such as:

```bash
-v "$PWD/runtime/cache/ncbi":/data/ncbi-cache
```

## Compose File

`compose.yaml` exists only to build the two runtime images:

- `pipeline-acquisition`
- `pipeline-detection`

It is not a second workflow orchestrator. The workflow graph remains entirely in Nextflow.
