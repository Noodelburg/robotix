#!/usr/bin/env bash
#
# run-worker.sh
# -------------
# Purpose:
#   Prepare the standard output files for a worker task.
# Inputs:
#   $1 = run ID
#   $2 = task file path
# Outputs:
#   A session log, execution report, and findings JSON file for that task.
# Lifecycle role:
#   This prepares the worker artifact structure before or instead of a live worker run.
# Note:
#   At the current MVP stage, this creates the structure a real worker execution
#   would later fill in.

# Fail fast on command errors, unset variables, and failed pipelines.
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <run-id> <task-file>" >&2
  exit 1
fi

# Resolve the run-scoped output paths derived from the task file name.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ID="$1"
TASK_FILE="$2"
RUN_DIR="$REPO_ROOT/toolchain/runs/$RUN_ID"
TASK_BASENAME="$(basename "$TASK_FILE" .task.md)"
REPORT_PATH="$RUN_DIR/reports/${TASK_BASENAME}.execution.md"
FINDINGS_PATH="$RUN_DIR/findings/${TASK_BASENAME}.findings.json"

# Create a simple session log so humans can trace what this prepared worker output belongs to.
cat > "$RUN_DIR/logs/${TASK_BASENAME}.session.md" <<EOF
# Worker session

- run_id: $RUN_ID
- task: $TASK_FILE
- status: prepared
- report_path: $REPORT_PATH
- findings_path: $FINDINGS_PATH
- next_step: execute this task with the appropriate custom agent
EOF

# Create the starter execution report that a future worker run would replace or extend.
cat > "$REPORT_PATH" <<EOF
# Execution report

- run_id: $RUN_ID
- task: $TASK_BASENAME
- status: pending execution
- source_task: $TASK_FILE
EOF

# Seed the findings file with an empty JSON array so JSON-aware tooling has a stable target.
cat > "$FINDINGS_PATH" <<'EOF'
[]
EOF

# Print the log path as a convenient pointer to the generated artifacts.
printf '%s\n' "$RUN_DIR/logs/${TASK_BASENAME}.session.md"
