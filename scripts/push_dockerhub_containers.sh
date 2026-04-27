#!/usr/bin/env bash
set -euo pipefail

DOCKERHUB_NAMESPACE="${DOCKERHUB_NAMESPACE:-rafaelmdc}"
CONTAINER_TAG="${CONTAINER_TAG:-0.1.0}"

ACQUISITION_IMAGE="${DOCKERHUB_NAMESPACE}/homorepeat-acquisition:${CONTAINER_TAG}"
DETECTION_IMAGE="${DOCKERHUB_NAMESPACE}/homorepeat-detection:${CONTAINER_TAG}"

docker push "$ACQUISITION_IMAGE"
docker push "$DETECTION_IMAGE"

printf 'Pushed Docker Hub images:\n'
printf '  %s\n' "$ACQUISITION_IMAGE"
printf '  %s\n' "$DETECTION_IMAGE"
