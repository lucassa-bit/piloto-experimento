#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0") --run RUN_ID [--attempt N]

Explicit retry for one existing run under official runs/.
Does not delete other runs. Does not auto-retry from collect.

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env

if [[ -z "${CLARIFY_RUN_ID}" ]]; then
  echo "ERROR: --run RUN_ID is required" >&2
  exit 2
fi

clarify_guard_integrity
[[ "${CLARIFY_DRY_RUN}" -eq 1 ]] && { echo "[dry-run] retry ${CLARIFY_RUN_ID} attempt=${CLARIFY_ATTEMPT}"; exit 0; }

clarify_log "retry-${CLARIFY_RUN_ID}" \
  clarify_python "${CLARIFY_SCRIPTS}/clarification-gen/runner.py" \
    --run-id "${CLARIFY_RUN_ID}" \
    --attempt "${CLARIFY_ATTEMPT}" \
    --i-authorize-experimental-collection \
    --sandbox read-only
