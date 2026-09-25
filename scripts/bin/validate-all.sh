#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0")

Structural validation of the official collection.
Writes collected-data/audit/validation-report.md

Does not modify runs/.

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env
clarify_guard_integrity
clarify_log validate-all clarify_python -m lib.validate_rerun
