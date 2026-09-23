#!/usr/bin/env bash
set -euo pipefail

BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "${BIN}/.." && pwd)"
ROOT="$(cd "${SCRIPTS}/.." && pwd)"

export CLARIFY_ROOT="${ROOT}"
export PYTHONPATH="${SCRIPTS}"

echo "Extracting questions..."
echo "Root: ${ROOT}"
echo

python "${SCRIPTS}/clarification-processing/extract_questions.py"

echo
echo "Finished."
echo "Check collected-data/questions.csv"
