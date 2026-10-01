#!/usr/bin/env bash
# Execute the pilot analysis notebook reproducibly.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export ANALYSIS_SEED="${ANALYSIS_SEED:-20260930}"

NOTEBOOK="analysis/notebooks/pilot-analysis.ipynb"
OUT_DIR="analysis/outputs/notebook-run"
mkdir -p "$OUT_DIR"

if [[ ! -f "$NOTEBOOK" ]]; then
  echo "Notebook not found: $NOTEBOOK" >&2
  exit 1
fi

echo "==> Running analysis pipeline (Python)"
python -m analysis.src.pipeline
status=$?
if [[ $status -ne 0 ]]; then
  echo "Pipeline stopped (validation or runtime error). Notebook execute skipped." >&2
  exit "$status"
fi

echo "==> Executing notebook with nbconvert"
python -m jupyter nbconvert \
  --to notebook \
  --execute \
  --ExecutePreprocessor.timeout=600 \
  --output-dir "$OUT_DIR" \
  --output pilot-analysis-executed.ipynb \
  "$NOTEBOOK"

echo "Done. Outputs under analysis/outputs/"
