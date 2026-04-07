#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIPELINE_ROOT="$APP_DIR"

cd "$PIPELINE_ROOT"

if docker compose version >/dev/null 2>&1 && [[ -f compose.yaml ]]; then
  docker compose build pipeline-acquisition pipeline-detection
else
  docker build -f containers/acquisition.Dockerfile -t homorepeat-acquisition:dev .
  docker build -f containers/detection.Dockerfile -t homorepeat-detection:dev .
fi
