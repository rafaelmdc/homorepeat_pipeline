#!/usr/bin/env bash
# Count blank Mermaid nodes in a Nextflow-generated dag.html.
# A blank node is any v<N>["  "] (square) or v<N>(( )) (circle) node with only
# whitespace as its label — these are the DAG fingerprint of anonymous channel
# placeholders and un-emitted process outputs.
#
# Usage:
#   scripts/count_dag_noise.sh [dag.html]
#   scripts/count_dag_noise.sh             # uses the most recent run under runs/
#
# Exit codes:
#   0 — ran successfully (even if blank nodes were found)
#   1 — no dag.html found

set -euo pipefail

DAG_FILE="${1:-}"

if [[ -z "$DAG_FILE" ]]; then
  LATEST_RUN=$(find runs -maxdepth 1 -mindepth 1 -type d | sort | tail -1)
  if [[ -z "$LATEST_RUN" ]]; then
    echo "error: no runs/ directory found and no dag.html argument given" >&2
    exit 1
  fi
  DAG_FILE="$LATEST_RUN/internal/nextflow/dag.html"
fi

if [[ ! -f "$DAG_FILE" ]]; then
  echo "error: dag.html not found: $DAG_FILE" >&2
  exit 1
fi

echo "DAG file: $DAG_FILE"
echo

BLANK_LINES=$(grep -oP 'v[0-9]+\[" "\]|v[0-9]+\(\( \)\)' "$DAG_FILE" 2>/dev/null || true)
COUNT=$(echo "$BLANK_LINES" | grep -c . 2>/dev/null || echo 0)

if [[ -z "$BLANK_LINES" ]]; then
  COUNT=0
fi

echo "Blank node count: $COUNT"
echo

if [[ "$COUNT" -gt 0 ]]; then
  echo "Blank nodes found:"
  echo "$BLANK_LINES"
else
  echo "No blank nodes — DAG is clean."
fi
