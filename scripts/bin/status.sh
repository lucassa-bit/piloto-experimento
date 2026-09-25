#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0")

Read-only status of the official collection (runs/, annotation, questions).

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env
clarify_python -m lib.status_report
