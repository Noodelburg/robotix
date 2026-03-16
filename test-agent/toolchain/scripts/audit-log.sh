#!/usr/bin/env bash
#
# audit-log.sh
# ------------
# Purpose:
#   Append a structured audit record after a tool action completes.
# Inputs:
#   Hook-provided environment variables such as RUN_ID, COPILOT_RUN_ID, and tool metadata.
# Outputs:
#   A JSON line appended to toolchain/runs/<run-id>/logs/audit.jsonl.
# Lifecycle role:
#   This supports traceability after tool executions.

# Fail fast on command errors, unset variables, and failed pipelines.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Accept either RUN_ID or COPILOT_RUN_ID so the script works in slightly
# different hook environments.
RUN_ID="${RUN_ID:-${COPILOT_RUN_ID:-}}"

# If there is no run ID, there is nowhere safe to write a run-scoped audit file.
if [[ -z "$RUN_ID" ]]; then
  exit 0
fi

OUT_DIR="$REPO_ROOT/toolchain/runs/$RUN_ID/logs"
mkdir -p "$OUT_DIR"

# Use inline Python to create valid JSON reliably instead of hand-escaping values in shell.
python3 - <<'PY' >> "$OUT_DIR/audit.jsonl"
import json
import os
from datetime import datetime, timezone

record = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "worker_name": os.getenv("COPILOT_AGENT_NAME", ""),
    "run_id": os.getenv("RUN_ID") or os.getenv("COPILOT_RUN_ID", ""),
    "tool_name": os.getenv("COPILOT_TOOL_NAME", ""),
    "result_type": os.getenv("COPILOT_TOOL_RESULT", ""),
    "task_id": os.getenv("TASK_ID", ""),
    "target": os.getenv("TARGET_HOSTNAME", ""),
    "artifact_path": os.getenv("ARTIFACT_PATH", ""),
}
print(json.dumps(record, sort_keys=True))
PY
