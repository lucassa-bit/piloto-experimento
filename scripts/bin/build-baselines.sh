#!/usr/bin/env bash
set -euo pipefail

BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "${BIN}/.." && pwd)"
ROOT="$(cd "${SCRIPTS}/.." && pwd)"

export CLARIFY_ROOT="${ROOT}"
export PYTHONPATH="${SCRIPTS}"

echo "Generating baselines with \$speckit-specify (user-story.md only)..."
echo "Staging: baselines/<US>/generation/feature"
echo "Canonical: baselines/<US>/spec.md"
echo "Root: ${ROOT}"
echo

python "${SCRIPTS}/baseline-gen/runner.py" "$@"

echo
echo "Finished."
echo "Check baselines/<US>/spec.md and collected-data/baseline-generation.csv"
