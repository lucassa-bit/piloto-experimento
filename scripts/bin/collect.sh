#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0")

DISABLED for the frozen official collection.
Use retry-run.sh for an explicit single-run attempt only.

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env
echo "ERROR: collect is disabled — official runs/ must not be re-collected wholesale." >&2
echo "Use: ./scripts/bin/retry-run.sh --run <RUN_ID> --attempt N" >&2
exit 2
