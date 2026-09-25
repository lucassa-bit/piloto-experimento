#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0") [--dry-run]

Preflight against the official collection (tools, skills, PRR, integrity hashes).
Writes collected-data/audit/preflight-report.md

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env
clarify_guard_integrity
[[ "${CLARIFY_DRY_RUN}" -eq 1 ]] && { echo "[dry-run] would run preflight"; exit 0; }
clarify_log preflight clarify_python -m lib.preflight
