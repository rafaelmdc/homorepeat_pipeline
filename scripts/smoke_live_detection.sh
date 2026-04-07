#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIPELINE_ROOT="$APP_DIR"
RUN_STARTED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DEFAULT_RUN_STAMP="$(date -u +%Y-%m-%d_%H-%M-%SZ)"
RUN_ID="${HOMOREPEAT_DETECTION_SMOKE_RUN_ID:-live_detection_smoke_${DEFAULT_RUN_STAMP}}"
RUN_ROOT="${HOMOREPEAT_DETECTION_SMOKE_RUN_ROOT:-$PIPELINE_ROOT/runs/$RUN_ID}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
SMOKE_REPEAT_RESIDUE="${HOMOREPEAT_SMOKE_REPEAT_RESIDUE:-Q}"

find_latest_live_smoke_root() {
  local candidate
  candidate="$(find "$PIPELINE_ROOT/runs" -maxdepth 1 -mindepth 1 -type d -name 'live_smoke_*' | sort | tail -n1 || true)"
  printf '%s' "$candidate"
}

SOURCE_RUN_ROOT="${HOMOREPEAT_SMOKE_SOURCE_RUN_ROOT:-$(find_latest_live_smoke_root)}"
SOURCE_ACQUISITION_DIR="${HOMOREPEAT_SMOKE_SOURCE_ACQUISITION_DIR:-}"
if [[ -z "$SOURCE_ACQUISITION_DIR" ]]; then
  [[ -n "$SOURCE_RUN_ROOT" ]] || {
    echo "smoke failure: no source acquisition run was provided and no live_smoke_* run was found under $PIPELINE_ROOT/runs" >&2
    exit 1
  }
  SOURCE_ACQUISITION_DIR="$SOURCE_RUN_ROOT/publish/acquisition"
fi

fail() {
  echo "smoke failure: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found on PATH: $1"
}

require_python_package() {
  "$PYTHON_BIN" -c "import homorepeat" >/dev/null 2>&1 || fail "homorepeat is not installed for $PYTHON_BIN; run: $PYTHON_BIN -m pip install -e \"$PIPELINE_ROOT\""
}

assert_nonempty_file() {
  local path="$1"
  [[ -s "$path" ]] || fail "expected non-empty file: $path"
}

assert_tsv_has_data_rows() {
  local path="$1"
  [[ -s "$path" ]] || fail "expected TSV file: $path"
  local lines
  lines="$(wc -l < "$path")"
  [[ "$lines" -ge 2 ]] || fail "expected at least one data row in $path"
}

run_py() {
  "$PYTHON_BIN" "$@"
}

require_command "$PYTHON_BIN"
require_python_package

[[ -d "$SOURCE_ACQUISITION_DIR" ]] || fail "source acquisition directory does not exist: $SOURCE_ACQUISITION_DIR"
assert_tsv_has_data_rows "$SOURCE_ACQUISITION_DIR/proteins.tsv"
assert_nonempty_file "$SOURCE_ACQUISITION_DIR/proteins.faa"
assert_tsv_has_data_rows "$SOURCE_ACQUISITION_DIR/sequences.tsv"
assert_nonempty_file "$SOURCE_ACQUISITION_DIR/cds.fna"

mkdir -p "$RUN_ROOT"
mkdir -p "$RUN_ROOT/internal/logs"
printf '%s\n' "$RUN_STARTED_AT_UTC" > "$RUN_ROOT/run_started_at_utc.txt"
printf '%s\n' "$SOURCE_ACQUISITION_DIR" > "$RUN_ROOT/source_acquisition_dir.txt"

THRESHOLD_DIR="$RUN_ROOT/publish/detection/raw/threshold/$SMOKE_REPEAT_RESIDUE"
THRESHOLD_FINAL_DIR="$RUN_ROOT/publish/detection/finalized/threshold/$SMOKE_REPEAT_RESIDUE"

mkdir -p "$THRESHOLD_DIR" "$THRESHOLD_FINAL_DIR"

echo "smoke: running threshold detection"
run_py -m homorepeat.cli.detect_threshold \
  --proteins-tsv "$SOURCE_ACQUISITION_DIR/proteins.tsv" \
  --proteins-fasta "$SOURCE_ACQUISITION_DIR/proteins.faa" \
  --repeat-residue "$SMOKE_REPEAT_RESIDUE" \
  --outdir "$THRESHOLD_DIR"

assert_tsv_has_data_rows "$THRESHOLD_DIR/threshold_calls.tsv"
assert_tsv_has_data_rows "$THRESHOLD_DIR/run_params.tsv"

run_py - <<'PY' "$THRESHOLD_DIR/threshold_calls.tsv" "$THRESHOLD_DIR/run_params.tsv"
import csv, sys
from homorepeat.contracts.repeat_features import validate_call_row

calls_path, params_path = sys.argv[1], sys.argv[2]
with open(calls_path, encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle, delimiter="\t"))
if not rows:
    raise SystemExit("threshold smoke output is empty")
for row in rows:
    validate_call_row(row)
    if row["method"] != "threshold":
        raise SystemExit("threshold smoke found a non-threshold method row")
    if not row["window_definition"]:
        raise SystemExit("threshold smoke found an empty window_definition")
with open(params_path, encoding="utf-8", newline="") as handle:
    params = {(row["param_name"], row["param_value"]) for row in csv.DictReader(handle, delimiter="\t")}
for item in [("window_size", "8"), ("min_target_count", "6")]:
    if item not in params:
        raise SystemExit(f"threshold smoke missing run param: {item}")
PY

echo "smoke: extracting codons for threshold calls"
run_py -m homorepeat.cli.extract_repeat_codons \
  --calls-tsv "$THRESHOLD_DIR/threshold_calls.tsv" \
  --sequences-tsv "$SOURCE_ACQUISITION_DIR/sequences.tsv" \
  --cds-fasta "$SOURCE_ACQUISITION_DIR/cds.fna" \
  --outdir "$THRESHOLD_FINAL_DIR"

assert_tsv_has_data_rows "$THRESHOLD_FINAL_DIR/threshold_calls.tsv"
assert_nonempty_file "$THRESHOLD_FINAL_DIR/threshold_calls_codon_warnings.tsv"
assert_tsv_has_data_rows "$THRESHOLD_FINAL_DIR/threshold_calls_codon_usage.tsv"

run_py - <<'PY' "$THRESHOLD_FINAL_DIR/threshold_calls.tsv" "$THRESHOLD_FINAL_DIR/threshold_calls_codon_usage.tsv"
import csv, sys
calls_path, codon_usage_path = sys.argv[1], sys.argv[2]
with open(calls_path, encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle, delimiter="\t"))
if not rows:
    raise SystemExit("threshold codon smoke output is empty")
success_count = 0
for row in rows:
    if row.get("codon_metric_name") or row.get("codon_metric_value"):
        raise SystemExit("threshold codon smoke found unexpected codon metric values")
    codon_sequence = row.get("codon_sequence", "")
    if codon_sequence:
        success_count += 1
        if len(codon_sequence) != int(row["length"]) * 3:
            raise SystemExit("threshold codon smoke found a length mismatch")
if success_count < 1:
    raise SystemExit("threshold codon smoke did not produce any successful codon rows")
with open(codon_usage_path, encoding="utf-8", newline="") as handle:
    usage_rows = list(csv.DictReader(handle, delimiter="\t"))
if not usage_rows:
    raise SystemExit("threshold codon smoke did not produce codon usage rows")
PY

echo "smoke: completed successfully"
echo "smoke: run root -> $RUN_ROOT"
