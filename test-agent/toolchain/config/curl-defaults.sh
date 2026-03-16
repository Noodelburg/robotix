#!/usr/bin/env bash
#
# curl-defaults.sh
# ----------------
# Provide shared curl defaults so every wrapper script uses the same baseline
# timeout and retry behavior unless a caller explicitly overrides it.

set -euo pipefail

# The `: "${VAR:=default}"` pattern means "assign this default if the variable is
# not already set by the caller's environment."
: "${CURL_CONNECT_TIMEOUT:=10}"
: "${CURL_MAX_TIME:=30}"
: "${CURL_RETRY:=0}"

# Export the values so child processes can use them.
export CURL_CONNECT_TIMEOUT
export CURL_MAX_TIME
export CURL_RETRY
