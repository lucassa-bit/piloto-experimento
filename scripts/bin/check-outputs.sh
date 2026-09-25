#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0")

Technical check of official runs/ (does not delete or recreate runs).
Updates collected-data/outputs-check.csv for audit.

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env
clarify_guard_integrity
clarify_log check-outputs \
  clarify_python "${CLARIFY_SCRIPTS}/check-outputs/check_outputs.py" \
    --all-experimental \
    --out "${CLARIFY_REPO}/collected-data/audit/outputs-check.latest.csv"
