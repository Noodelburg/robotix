#!/usr/bin/env bash
#
# policy-check.sh
# ---------------
# Purpose:
#   Enforce a small set of high-value safety checks before a tool action runs.
# Inputs:
#   Hook metadata or positional fallbacks describing the tool name and tool input.
# Outputs:
#   Exit code 0 if allowed, non-zero plus a denial message if blocked.
# Lifecycle role:
#   This is the main pre-tool safety guard in the current scaffold.

# Fail fast on command errors, unset variables, and failed pipelines.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ALLOWLIST_FILE="$REPO_ROOT/toolchain/config/env-allowlist.txt"
SENSITIVE_PATHS_FILE="$REPO_ROOT/toolchain/config/sensitive-paths.txt"

# Prefer hook-supplied metadata, but allow manual testing with positional arguments.
TOOL_NAME="${COPILOT_TOOL_NAME:-${1:-}}"
TOOL_INPUT="${COPILOT_TOOL_INPUT:-${2:-}}"

# Centralize denial handling so failures are consistent and easy to diagnose.
deny() {
  echo "policy denied: $1" >&2
  exit 1
}

# If no tool name was supplied, there is nothing to evaluate.
if [[ -z "$TOOL_NAME" ]]; then
  exit 0
fi

case "$TOOL_NAME" in
  bash|shell|execute)
    # Deny obviously destructive or out-of-scope command fragments.
    for pattern in "rm -rf" "sudo" "terraform apply" "terraform destroy" "kubectl delete" "aws " "gcloud " "az "; do
      if [[ "$TOOL_INPUT" == *"$pattern"* ]]; then
        deny "command contains forbidden pattern: $pattern"
      fi
    done

    # If the command looks like curl, extract the first URL and require its host
    # to appear in the allowlist.
    if [[ "$TOOL_INPUT" == *"curl "* ]]; then
      url="$(printf '%s' "$TOOL_INPUT" | grep -Eo 'https?://[^"'"'"'[:space:]]+' | head -n1 || true)"
      if [[ -n "$url" ]]; then
        host="$(printf '%s' "$url" | sed -E 's#https?://([^/]+).*#\1#')"
        if ! grep -Fxq "$host" "$ALLOWLIST_FILE"; then
          deny "curl target host is not allowlisted: $host"
        fi
      fi
    fi
    ;;
  read)
    # Deny reads of sensitive path patterns such as .env or SSH key material.
    while IFS= read -r sensitive; do
      [[ -z "$sensitive" ]] && continue
      if [[ "$TOOL_INPUT" == *"$sensitive"* ]]; then
        deny "attempt to read sensitive path pattern: $sensitive"
      fi
    done < "$SENSITIVE_PATHS_FILE"
    ;;
esac
