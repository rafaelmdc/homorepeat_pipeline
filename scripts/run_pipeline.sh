#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIPELINE_ROOT="$APP_DIR"
RUN_STAMP="$(date -u +%Y-%m-%d_%H-%M-%SZ)"
RUN_ID="${HOMOREPEAT_RUN_ID:-pipeline_${RUN_STAMP}}"
RUN_ROOT="${HOMOREPEAT_RUN_ROOT:-$PIPELINE_ROOT/runs/$RUN_ID}"
OUTPUT_DIR="${HOMOREPEAT_OUTPUT_DIR:-$RUN_ROOT/publish}"
PROFILE="${HOMOREPEAT_PROFILE:-local}"
NEXTFLOW_BIN="${NEXTFLOW_BIN:-nextflow}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PARAMS_FILE="${HOMOREPEAT_PARAMS_FILE:-}"
DEFAULT_TAXONOMY_DB="$PIPELINE_ROOT/runtime/cache/taxonomy/ncbi_taxonomy.sqlite"
DEFAULT_NXF_HOME="$PIPELINE_ROOT/runtime/cache/nextflow"

fail() {
  echo "$*" >&2
  exit 2
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found on PATH: $1"
}

require_python_package() {
  "$PYTHON_BIN" -c "import homorepeat" >/dev/null 2>&1 || fail "homorepeat is not installed for $PYTHON_BIN; run: $PYTHON_BIN -m pip install -e \"$PIPELINE_ROOT\""
}

if [[ $# -lt 1 ]] && [[ -z "${HOMOREPEAT_ACCESSIONS_FILE:-}" ]]; then
  echo "usage: $0 <accessions_file> [additional nextflow args...]" >&2
  echo "or set HOMOREPEAT_ACCESSIONS_FILE in the environment" >&2
  exit 2
fi

ACCESSIONS_FILE="${HOMOREPEAT_ACCESSIONS_FILE:-${1:-}}"
if [[ $# -gt 0 ]] && [[ -z "${HOMOREPEAT_ACCESSIONS_FILE:-}" ]]; then
  shift
fi

if [[ "$ACCESSIONS_FILE" != /* ]]; then
  ACCESSIONS_FILE="${PIPELINE_ROOT}/${ACCESSIONS_FILE}"
fi

if [[ -n "$PARAMS_FILE" ]] && [[ "$PARAMS_FILE" != /* ]]; then
  PARAMS_FILE="${PIPELINE_ROOT}/${PARAMS_FILE}"
fi

TAXONOMY_DB="${HOMOREPEAT_TAXONOMY_DB:-$DEFAULT_TAXONOMY_DB}"
if [[ "$TAXONOMY_DB" != /* ]]; then
  TAXONOMY_DB="${PIPELINE_ROOT}/${TAXONOMY_DB}"
fi

if [[ ! -f "$ACCESSIONS_FILE" ]]; then
  echo "accessions file not found: $ACCESSIONS_FILE" >&2
  exit 2
fi

if [[ -n "$PARAMS_FILE" ]] && [[ ! -f "$PARAMS_FILE" ]]; then
  echo "params file not found: $PARAMS_FILE" >&2
  exit 2
fi

if [[ ! -f "$TAXONOMY_DB" ]]; then
  echo "taxonomy DB not found: $TAXONOMY_DB" >&2
  echo "set HOMOREPEAT_TAXONOMY_DB to override it" >&2
  exit 2
fi

require_command "$NEXTFLOW_BIN"
require_command "$PYTHON_BIN"
require_python_package

export NXF_HOME="${HOMOREPEAT_NXF_HOME:-$DEFAULT_NXF_HOME}"

mkdir -p "$NXF_HOME" "$RUN_ROOT/internal/nextflow" "$RUN_ROOT/publish/manifest"
LOG_FILE="${RUN_ROOT}/internal/nextflow/nextflow.log"
STARTED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' "$STARTED_AT_UTC" > "$RUN_ROOT/run_started_at_utc.txt"

{
  printf 'RUN_ID=%q\n' "$RUN_ID"
  printf 'RUN_ROOT=%q\n' "$RUN_ROOT"
  printf 'OUTPUT_DIR=%q\n' "$OUTPUT_DIR"
  printf 'APP_DIR=%q\n' "$APP_DIR"
  printf 'PIPELINE_ROOT=%q\n' "$PIPELINE_ROOT"
  printf 'PROFILE=%q\n' "$PROFILE"
  printf 'ACCESSIONS_FILE=%q\n' "$ACCESSIONS_FILE"
  printf 'TAXONOMY_DB=%q\n' "$TAXONOMY_DB"
  printf 'PARAMS_FILE=%q\n' "$PARAMS_FILE"
  printf 'PYTHON_BIN=%q\n' "$PYTHON_BIN"
  printf 'NXF_HOME=%q\n' "$NXF_HOME"
} > "$RUN_ROOT/run_context.env"

NEXTFLOW_ARGS=(
  -log "$LOG_FILE"
  run "$APP_DIR"
  -profile "$PROFILE"
  --accessions_file "$ACCESSIONS_FILE"
  --taxonomy_db "$TAXONOMY_DB"
  --run_root "$RUN_ROOT"
  --output_dir "$OUTPUT_DIR"
)

if [[ -n "$PARAMS_FILE" ]]; then
  NEXTFLOW_ARGS+=(-params-file "$PARAMS_FILE")
fi

if [[ $# -gt 0 ]]; then
  NEXTFLOW_ARGS+=("$@")
fi

{
  printf '%q ' "$NEXTFLOW_BIN"
  printf '%q ' "${NEXTFLOW_ARGS[@]}"
  printf '\n'
} > "$RUN_ROOT/internal/nextflow/nextflow_command.sh"
chmod +x "$RUN_ROOT/internal/nextflow/nextflow_command.sh"

if "$NEXTFLOW_BIN" "${NEXTFLOW_ARGS[@]}"; then
  STATUS=0
else
  STATUS=$?
fi
FINISHED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

STATUS_TEXT="failed"
if [[ $STATUS -eq 0 ]]; then
  STATUS_TEXT="success"
fi

MANIFEST_ARGS=(
  -m homorepeat.cli.write_run_manifest
  --pipeline-root "$PIPELINE_ROOT"
  --run-id "$RUN_ID"
  --run-root "$RUN_ROOT"
  --publish-root "$OUTPUT_DIR"
  --profile "$PROFILE"
  --accessions-file "$ACCESSIONS_FILE"
  --taxonomy-db "$TAXONOMY_DB"
  --nextflow-command "$RUN_ROOT/internal/nextflow/nextflow_command.sh"
  --started-at-utc "$STARTED_AT_UTC"
  --finished-at-utc "$FINISHED_AT_UTC"
  --status "$STATUS_TEXT"
  --outpath "$OUTPUT_DIR/manifest/run_manifest.json"
)
if [[ -n "$PARAMS_FILE" ]]; then
  MANIFEST_ARGS+=(--params-file "$PARAMS_FILE")
fi

"$PYTHON_BIN" "${MANIFEST_ARGS[@]}"

if [[ $STATUS -eq 0 ]]; then
  ln -sfn "$RUN_ID" "$PIPELINE_ROOT/runs/latest"
fi

exit $STATUS
