#!/usr/bin/env bash
set -euo pipefail

BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "${BIN}/.." && pwd)"
ROOT="$(cd "${SCRIPTS}/.." && pwd)"

export CLARIFY_ROOT="${ROOT}"
export PYTHONPATH="${SCRIPTS}"

echo "Running all SpecKit clarify executions..."
echo "Root: ${ROOT}"
echo

python "${SCRIPTS}/clarification-gen/runner.py"
python "${SCRIPTS}/check-outputs/check_outputs.py"

echo
echo "Finished."
echo "Check collected-data/execution-table.csv"
