#!/usr/bin/env bash
set -euo pipefail

BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "${BIN}/.." && pwd)"
ROOT="$(cd "${SCRIPTS}/.." && pwd)"

export CLARIFY_ROOT="${ROOT}"
export PYTHONPATH="${SCRIPTS}"

echo "Running full clarification pipeline..."
echo "Root: ${ROOT}"
echo
echo "Extra args (scaffold): ${*:-<none>}"
echo

echo "========== 1/5 scaffold-runs =========="
python "${SCRIPTS}/clarification-gen/scaffold_runs.py" "$@"

echo
echo "========== 2/5 run clarifications =========="
python "${SCRIPTS}/clarification-gen/runner.py"

echo
echo "========== 3/5 check-outputs =========="
python "${SCRIPTS}/check-outputs/check_outputs.py"

echo
echo "========== 4/5 extract-questions =========="
python "${SCRIPTS}/clarification-processing/extract_questions.py"

echo
echo "========== 5/5 build-classification-base =========="
python "${SCRIPTS}/clarification-processing/build_classification_base.py"

echo
echo "Pipeline finished."
echo "Check collected-data/ for execution-table.csv, outputs-check.csv,"
echo "questions_raw.csv and classification_base.csv"
