#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0")

Re-check technical integrity of official runs/ without modifying frozen
collected-data/audit/outputs-check.csv (writes a temporary file only).

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env
clarify_guard_integrity
tmpdir=$(mktemp -d)
clarify_log check-outputs \
  clarify_python "${CLARIFY_SCRIPTS}/check-outputs/check_outputs.py" \
    --all-experimental \
    --out "${tmpdir}/outputs-check.csv"
rm -rf "${tmpdir}"
