#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

clarify_help() {
  cat <<EOF
Usage: $(basename "$0")

DISABLED for the frozen official collection by default.
Materials already exist under materials/. This entrypoint refuses to
overwrite the frozen experiment layout.

EOF
  clarify_usage_common
}

clarify_parse_args "$@"
clarify_export_env
echo "ERROR: prepare-materials is disabled on the official collection (materials/ already frozen)." >&2
echo "Use the existing materials/ directory." >&2
exit 2
