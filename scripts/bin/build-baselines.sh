#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0")

DISABLED for the frozen official collection (baselines/ already present).
Refuses to regenerate baselines over the scientific collection.

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env
echo "ERROR: build-baselines is disabled on the official collection (baselines/ frozen)." >&2
exit 2
