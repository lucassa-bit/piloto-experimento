#!/usr/bin/env bash
set -euo pipefail

BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "${BIN}/.." && pwd)"
ROOT="$(cd "${SCRIPTS}/.." && pwd)"

export CLARIFY_ROOT="${ROOT}"
export PYTHONPATH="${SCRIPTS}"

echo "Building classification base..."
echo "Root: ${ROOT}"
echo

python "${SCRIPTS}/clarification-processing/build_classification_base.py"

echo
echo "Finished."
echo "Check collected-data/classification_base.csv"
