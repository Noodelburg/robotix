#!/usr/bin/env bash
#
# execute-payload-pack.sh
# -----------------------
# Purpose:
#   Execute a request script from a payload pack and capture headers, body, and
#   normalized metadata in a consistent evidence directory layout.
# Inputs:
#   $1 = run ID
#   $2 = finding ID
#   $3 = request script path
# Outputs:
#   headers.txt, body.txt, and meta.json in the run's evidence directory.
# Lifecycle role:
#   This is the standard evidence-capture wrapper for active payload execution.

# Fail fast on command errors, unset variables, and failed pipelines.
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "usage: $0 <run-id> <finding-id> <request-script>" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Load shared curl timeout and retry defaults so every request behaves consistently.
source "$REPO_ROOT/toolchain/config/curl-defaults.sh"

RUN_ID="$1"
FINDING_ID="$2"
REQUEST_SCRIPT="$3"
REQUEST_NAME="$(basename "$REQUEST_SCRIPT" .sh)"
OUT_DIR="$REPO_ROOT/toolchain/runs/$RUN_ID/evidence/$FINDING_ID/$REQUEST_NAME"

# Create a request-specific evidence folder such as evidence/FND-001/request-01/.
mkdir -p "$OUT_DIR"

# Capture the start time separately so it can be injected into normalized metadata later.
START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TMP_META="$OUT_DIR/meta.raw.json"

# The request script is expected to wrap curl. We provide the standard capture
# flags so every payload run writes evidence in the same shape.
bash "$REQUEST_SCRIPT" \
  --connect-timeout "$CURL_CONNECT_TIMEOUT" \
  --max-time "$CURL_MAX_TIME" \
  --retry "$CURL_RETRY" \
  -D "$OUT_DIR/headers.txt" \
  -o "$OUT_DIR/body.txt" \
  -w '{"http_code":%{http_code},"time_total":%{time_total},"size_download":%{size_download},"url_effective":"%{url_effective}"}' \
  > "$TMP_META"

# Normalize curl's metadata output into pretty JSON and include the captured start timestamp.
python3 - "$START_TS" "$TMP_META" "$OUT_DIR/meta.json" <<'PY'
import json
import pathlib
import sys

started_at, raw_path, out_path = sys.argv[1:4]
raw = pathlib.Path(raw_path).read_text(encoding="utf-8").strip()
payload = json.loads(raw or "{}")
payload["started_at"] = started_at
pathlib.Path(out_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

# Discard the temporary raw metadata once the normalized version exists.
rm -f "$TMP_META"

# Print the evidence directory path so callers can locate the captured files quickly.
printf '%s\n' "$OUT_DIR"
