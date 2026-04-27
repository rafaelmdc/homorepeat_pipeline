# Containers

## Overview

The normal user profile is `-profile docker`. It uses published Docker Hub
images so a new user does not need to build containers before the first run.
Docker pulls the images automatically when they are missing locally.

| Profile | Images | Intended use |
| --- | --- | --- |
| `docker` | `rafaelmdc/homorepeat-acquisition:0.1.0`, `rafaelmdc/homorepeat-detection:0.1.0` | Normal runs |
| `docker_dev` | `homorepeat-acquisition:dev`, `homorepeat-detection:dev` | Local development after rebuilding images from this checkout |

The acquisition and detection images are separate because acquisition needs
NCBI and taxonomy tooling, while detection/reporting does not.

| Image role | Dockerfile | Used by labels | Main tools |
| --- | --- | --- | --- |
| acquisition | `containers/acquisition.Dockerfile` | `planning`, `taxonomy_build`, `acquisition_download`, `acquisition_normalize`, `acquisition_translate`, `acquisition_merge` | Python 3.12, `taxon-weaver`, NCBI `datasets`, NCBI `dataformat`, installed `homorepeat` package |
| detection | `containers/detection.Dockerfile` | `detection`, `database`, `reporting` | Python 3.12 and installed `homorepeat` package |

## Normal User Path

Run with:

```bash
nextflow run . \
  -profile docker \
  --accessions_file examples/accessions/smoke_human.txt
```

No local container build is required for this path.

Useful image parameters:

| Parameter | Default | Use |
| --- | --- | --- |
| `--dockerhub_namespace` | `rafaelmdc` | Docker Hub namespace for both images |
| `--container_tag` | `0.1.0` | Image tag for both images |
| `--acquisition_container` | derived from namespace and tag | Full override for the acquisition image |
| `--detection_container` | derived from namespace and tag | Full override for the detection image |

## Local Development Images

Build local images after changing code or Dockerfiles:

```bash
bash scripts/build_dev_containers.sh
```

That creates:

- `homorepeat-acquisition:dev`
- `homorepeat-detection:dev`

Run those local images with:

```bash
nextflow run . \
  -profile docker_dev \
  --accessions_file examples/accessions/smoke_human.txt
```

Equivalent manual builds:

```bash
docker build -f containers/acquisition.Dockerfile -t homorepeat-acquisition:dev .
docker build -f containers/detection.Dockerfile -t homorepeat-detection:dev .
```

## Publishing Release Images

Build images with the release tags:

```bash
bash scripts/build_dockerhub_containers.sh
```

Push them after `docker login`:

```bash
bash scripts/push_dockerhub_containers.sh
```

Override the namespace or tag with environment variables:

```bash
DOCKERHUB_NAMESPACE=my-org CONTAINER_TAG=0.1.1 \
  bash scripts/build_dockerhub_containers.sh

DOCKERHUB_NAMESPACE=my-org CONTAINER_TAG=0.1.1 \
  bash scripts/push_dockerhub_containers.sh
```

Before advertising a release externally, verify that the published images exist
for the namespace and tag used by the `docker` profile.

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

The `docker` and `docker_dev` profiles keep `process.executor = 'local'` and
bind containers by label in `conf/docker.config`.

Current label mapping:

- `planning` -> acquisition image
- `taxonomy_build` -> acquisition image
- `acquisition_download` -> acquisition image
- `acquisition_normalize` -> acquisition image
- `acquisition_translate` -> acquisition image
- `acquisition_merge` -> acquisition image
- `detection` -> detection image
- `database` -> detection image
- `reporting` -> detection image

Important detail:

- the images already contain the installable package
- Nextflow stages task inputs into work directories, so the Docker profiles do
  not need a manual repo bind mount for normal pipeline execution

## Smoke Checks

For published images:

```bash
docker run --rm rafaelmdc/homorepeat-acquisition:0.1.0 python --version
docker run --rm rafaelmdc/homorepeat-acquisition:0.1.0 taxon-weaver --help
docker run --rm rafaelmdc/homorepeat-acquisition:0.1.0 datasets version
docker run --rm rafaelmdc/homorepeat-acquisition:0.1.0 dataformat --help
docker run --rm rafaelmdc/homorepeat-detection:0.1.0 python --version
```

For local development images, replace the image names with
`homorepeat-acquisition:dev` and `homorepeat-detection:dev`.

## Manual `docker run` Notes

For ad hoc container debugging outside Nextflow, mount the repo and any required
caches explicitly.

Example acquisition-side command with the published image:

```bash
docker run --rm \
  -v "$PWD":/work \
  -v "$PWD/runtime/cache/taxonomy":/data/taxonomy \
  -w /work \
  rafaelmdc/homorepeat-acquisition:0.1.0 \
  python -m homorepeat.cli.plan_accession_batches \
  --accessions-file examples/accessions/smoke_human.txt \
  --outdir /tmp/homorepeat_planning
```

If you want reusable NCBI downloads during manual work, also mount a cache
directory such as:

```bash
-v "$PWD/runtime/cache/ncbi":/data/ncbi-cache
```

## Compose File

`compose.yaml` exists only to build the two local development images:

- `pipeline-acquisition`
- `pipeline-detection`

It is not a second workflow orchestrator. The workflow graph remains entirely in
Nextflow.
