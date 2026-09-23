#!/usr/bin/env bash
set -euo pipefail

BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$(cd "${BIN}/.." && pwd)"
ROOT="$(cd "${SCRIPTS}/.." && pwd)"

export CLARIFY_ROOT="${ROOT}"
export PYTHONPATH="${SCRIPTS}"

echo "Scaffolding clarification run folders..."
echo "Root: ${ROOT}"
echo

python "${SCRIPTS}/clarification-gen/scaffold_runs.py" "$@"
