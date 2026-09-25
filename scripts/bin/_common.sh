#!/usr/bin/env bash
# Shared helpers for scripts/bin — operate on the official repo by default.
# NEVER wipe runs/, baselines/, or materials/ of the official collection.
# shellcheck disable=SC2034

set -euo pipefail

_clarify_bin_dir() {
  local src="${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}"
  cd "$(dirname "${src}")" && pwd
}

CLARIFY_BIN="$(_clarify_bin_dir)"
CLARIFY_SCRIPTS="$(cd "${CLARIFY_BIN}/.." && pwd)"
CLARIFY_REPO="$(cd "${CLARIFY_SCRIPTS}/.." && pwd)"

CLARIFY_WORKSPACE="${CLARIFY_REPO}"
CLARIFY_DRY_RUN=0
CLARIFY_FORCE=0
CLARIFY_RUN_ID=""
CLARIFY_ATTEMPT=1
CLARIFY_EXTRA_ARGS=()

clarify_usage_common() {
  cat <<EOF
Options:
  --dry-run    Show planned actions without destructive / Codex writes where supported
  --force      Explicit overwrite where a step documents it (never deletes runs/)
  --help       Show this help

Default root: repository (official runs/, collected-data/).
Scripts never remove official runs/ contents.
EOF
}

clarify_parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --workspace)
        echo "ERROR: --workspace was removed. Use the official repository layout (runs/)." >&2
        exit 2
        ;;
      --clean)
        echo "ERROR: --clean was removed. Scripts must not wipe runs/ or rebuild the collection." >&2
        exit 2
        ;;
      --dry-run)
        CLARIFY_DRY_RUN=1
        shift
        ;;
      --force)
        CLARIFY_FORCE=1
        shift
        ;;
      --run)
        [[ $# -ge 2 ]] || { echo "Missing value for --run" >&2; exit 2; }
        CLARIFY_RUN_ID="$2"
        shift 2
        ;;
      --attempt)
        [[ $# -ge 2 ]] || { echo "Missing value for --attempt" >&2; exit 2; }
        CLARIFY_ATTEMPT="$2"
        shift 2
        ;;
      --help|-h)
        if declare -F clarify_help >/dev/null; then
          clarify_help
        else
          echo "Usage: $0 [--dry-run] [--force]"
          clarify_usage_common
        fi
        exit 0
        ;;
      --)
        shift
        CLARIFY_EXTRA_ARGS+=("$@")
        break
        ;;
      *)
        CLARIFY_EXTRA_ARGS+=("$1")
        shift
        ;;
    esac
  done

  CLARIFY_WORKSPACE="${CLARIFY_REPO}"
}

clarify_export_env() {
  export CLARIFY_REPO
  export CLARIFY_WORKSPACE="${CLARIFY_REPO}"
  export CLARIFY_ROOT="${CLARIFY_REPO}"
  export PYTHONUNBUFFERED=1
  export PYTHONPATH="${CLARIFY_SCRIPTS}:${CLARIFY_SCRIPTS}/clarification-processing:${CLARIFY_SCRIPTS}/check-outputs:${CLARIFY_SCRIPTS}/baseline-gen:${CLARIFY_REPO}${PYTHONPATH:+:${PYTHONPATH}}"
}

clarify_log() {
  local step="$1"
  shift
  local log_dir="${CLARIFY_REPO}/collected-data/audit/logs"
  mkdir -p "${log_dir}"
  local log="${log_dir}/${step}.log"
  echo ">>> ${step}: $*" | tee -a "${log_dir}/pipeline.log"
  "$@" 2>&1 | tee -a "${log}" | tee -a "${log_dir}/pipeline.log"
  return "${PIPESTATUS[0]}"
}

clarify_python() {
  python3 "$@"
}

clarify_guard_integrity() {
  clarify_python - <<'PY'
from lib.preflight import verify_collection_integrity
ok, msgs = verify_collection_integrity()
changed = [m for m in msgs if m.startswith(("CHANGED", "MISSING"))]
if not ok:
    print("COLLECTION INTEGRITY FAILED:", *changed, sep="\n  ")
    raise SystemExit(1)
print("Collection integrity: OK")
PY
}
