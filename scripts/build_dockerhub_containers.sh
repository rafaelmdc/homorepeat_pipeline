#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIPELINE_ROOT="$APP_DIR"

DOCKERHUB_NAMESPACE="${DOCKERHUB_NAMESPACE:-rafaelmdc}"
CONTAINER_TAG="${CONTAINER_TAG:-0.1.0}"

ACQUISITION_IMAGE="${DOCKERHUB_NAMESPACE}/homorepeat-acquisition:${CONTAINER_TAG}"
DETECTION_IMAGE="${DOCKERHUB_NAMESPACE}/homorepeat-detection:${CONTAINER_TAG}"

cd "$PIPELINE_ROOT"

docker build -f containers/acquisition.Dockerfile -t "$ACQUISITION_IMAGE" .
docker build -f containers/detection.Dockerfile -t "$DETECTION_IMAGE" .

printf 'Built Docker Hub images:\n'
printf '  %s\n' "$ACQUISITION_IMAGE"
printf '  %s\n' "$DETECTION_IMAGE"
