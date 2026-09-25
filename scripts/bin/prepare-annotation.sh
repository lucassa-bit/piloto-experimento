#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0")

DISABLED by default: would recreate empty evaluator sheets and risk
wiping human annotation progress. Sheets already exist under
collected-data/annotation/.

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env
echo "ERROR: prepare-annotation is disabled — annotation sheets already exist." >&2
echo "See collected-data/annotation/README.md" >&2
exit 2
