# Containers

## Purpose

This directory holds the reproducible runtime layers for HomoRepeat.

The current baseline is container-first:
- Docker/Podman for local development and workstations
- Apptainer later for cluster execution

The runtime is split by process class where the toolchains are materially different.

Current images:
- acquisition
- detection

---

## Acquisition image

File:
- `containers/acquisition.Dockerfile`

What it contains:
- Python 3.12
- `taxon-weaver`
- NCBI `datasets`
- NCBI `dataformat`

What it does not contain:
- the taxonomy SQLite database
- downloaded NCBI package caches
- checked-out workflow scripts from the repo root

Those are runtime artifacts or repo-owned orchestration files and should stay outside the image.

---

## Detection image

File:
- `containers/detection.Dockerfile`

What it contains:
- Python 3.12

What it does not contain:
- `taxon-weaver`
- NCBI `datasets`
- checked-out workflow scripts from the repo root

This split is intentional.
Acquisition and detection have different external toolchains, and later Nextflow process labels should be able to pin different images without carrying unnecessary binaries into every task.

---

## Pinning policy

`taxon-weaver` is pinned to:
- ref: `v.0.1.1`
- commit: `aff9709a82ac09fa3f97a71cca809f8e8f98c213`

That matches the currently installed local package metadata used during implementation.

NCBI `datasets` and `dataformat` are installed from NCBI's official v2 Linux AMD64 download endpoints:
- https://www.ncbi.nlm.nih.gov/datasets/docs/v2/command-line-tools/download-and-install/

Important caveat:
- those NCBI binary URLs are rolling endpoints, not immutable release asset URLs
- the Dockerfile is a reproducible recipe for rebuilding the tool layer, but the final reproducible runtime for the pipeline should be the built image tag or digest that Nextflow later pins

So the practical model is:
1. build the image intentionally
2. record the resulting image tag or digest
3. pin that image in the future Nextflow config

---

## Build

Fast path from the repo root:

```bash
bash scripts/build_dev_containers.sh
```

That helper builds the image tags expected by the pipeline today:
- `homorepeat-acquisition:dev`
- `homorepeat-detection:dev`

Equivalent manual commands:

Build the acquisition image from the repo root:

```bash
docker build -f containers/acquisition.Dockerfile -t homorepeat-acquisition:dev .
```

If you need to override the `taxon-weaver` source ref:

```bash
docker build \
  -f containers/acquisition.Dockerfile \
  --build-arg TAXON_WEAVER_REF=v.0.1.1 \
  --build-arg TAXON_WEAVER_COMMIT=aff9709a82ac09fa3f97a71cca809f8e8f98c213 \
  -t homorepeat-acquisition:dev .
```

Build the detection image from the repo root:

```bash
docker build -f containers/detection.Dockerfile -t homorepeat-detection:dev .
```

## Smoke checks

Check the core tools inside the built image:

```bash
docker run --rm homorepeat-acquisition:dev python --version
docker run --rm homorepeat-acquisition:dev taxon-weaver --help
docker run --rm homorepeat-acquisition:dev datasets version
docker run --rm homorepeat-acquisition:dev dataformat --help
docker run --rm homorepeat-detection:dev python --version
```

---

## Runtime expectations

The acquisition scripts expect the taxonomy DB to be available by path.
The images include the installable `homorepeat` package, but they still expect run inputs and workflow scripts to come from the mounted repo.

Recommended mount pattern:

```bash
docker run --rm \
  -v "$PWD":/work \
  -v "$PWD/runtime/cache/taxonomy":/data/taxonomy \
  -w /work \
  homorepeat-acquisition:dev \
  python -m homorepeat.cli.resolve_taxa \
  --requested-taxa runs/run_001/internal/planning/requested_taxa.tsv \
  --taxonomy-db /data/taxonomy/ncbi_taxonomy.sqlite \
  --outdir runs/run_001/internal/planning
```

For larger runs, mount an external cache directory as well:

```bash
-v "$PWD/runtime/cache/ncbi":/data/ncbi-cache
```

To run the live acquisition smoke check inside the container:

```bash
docker run --rm \
  -v "$PWD":/work \
  -v "$PWD/runtime/cache/taxonomy":/data/taxonomy \
  -v "$PWD/runtime/cache/ncbi":/data/ncbi-cache \
  -w /work \
  -e TAXONOMY_DB_PATH=/data/taxonomy/ncbi_taxonomy.sqlite \
  -e NCBI_API_KEY="$NCBI_API_KEY" \
  homorepeat-acquisition:dev \
  bash scripts/smoke_live_acquisition.sh
```

To run threshold detection inside the detection image:

```bash
docker run --rm \
  -v "$PWD":/work \
  -w /work \
  homorepeat-detection:dev \
  python -m homorepeat.cli.detect_threshold \
  --proteins-tsv runs/run_001/publish/acquisition/batches/batch_0001/proteins.tsv \
  --proteins-fasta runs/run_001/publish/acquisition/batches/batch_0001/proteins.faa \
  --repeat-residue Q \
  --outdir runs/run_001/publish/detection/raw/threshold/Q
```

If the source run used `--acquisition_publish_mode merged`, the legacy flat paths under `publish/acquisition/` remain valid.

---

## Nextflow wiring

The repo now has a Nextflow pipeline layer and a `docker` profile:
- [nextflow.config](../nextflow.config)
- [docker.config](../conf/docker.config)

Current label-to-image mapping:
- `planning` -> acquisition image
- `acquisition_download` -> acquisition image
- `acquisition_normalize` -> acquisition image
- `acquisition_merge` -> acquisition image
- `detection` -> detection image
- `database` -> detection image
- `reporting` -> detection image

Important runtime detail:
- the images bake the installable `homorepeat` package into the image
- Nextflow mounts task work directories and required inputs at runtime, so the Docker profile does not need an extra repo checkout bind mount

Verified on April 8, 2026:
- `bash scripts/build_dev_containers.sh` succeeded
- the Nextflow `docker` profile completed a live smoke pipeline run on 5 real NCBI accessions
- the current verified live run root is `runs/smoke_contract_cleanup_live`

Why this layer exists now:
- lock the external toolchains
- keep acquisition and detection dependencies separate
- stop pipeline execution from depending on undocumented host-installed binaries
- make later cluster profiles a runtime concern rather than a workflow-graph refactor
