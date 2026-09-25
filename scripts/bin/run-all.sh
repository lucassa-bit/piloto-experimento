#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0") [--dry-run]

Audit pipeline on the official collection (does NOT rebuild runs/):

  1. preflight
  2. check-outputs
  3. validate-all
  4. status

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env
clarify_guard_integrity

STEPS=(preflight check-outputs validate-all)

if [[ "${CLARIFY_DRY_RUN}" -eq 1 ]]; then
  echo "DRY RUN — audit pipeline on official repo: ${CLARIFY_REPO}"
  for s in "${STEPS[@]}"; do
    echo "  - ${s}"
  done
  echo "  - status"
  exit 0
fi

echo "Official collection audit"
echo "  repo: ${CLARIFY_REPO}"

for step in "${STEPS[@]}"; do
  echo ""
  echo "========== ${step} =========="
  if ! bash "${CLARIFY_BIN}/${step}.sh"; then
    echo "FAILED at step: ${step}" >&2
    exit 1
  fi
  echo "OK: ${step}"
done

echo ""
bash "${CLARIFY_BIN}/status.sh"
echo ""
echo "Audit report: ${CLARIFY_REPO}/collected-data/audit/validation-report.md"
