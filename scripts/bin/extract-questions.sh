#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0")

DISABLED by default: re-extracting would overwrite frozen questions.csv.
Official questions are already in collected-data/questions.csv.

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env
echo "ERROR: extract-questions is disabled on the frozen collection (would rewrite questions.csv)." >&2
exit 2
