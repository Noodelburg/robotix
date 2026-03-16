#!/usr/bin/env bash
#
# run-validator.sh
# ----------------
# Purpose:
#   Prepare a starter validation artifact for a task.
# Inputs:
#   $1 = run ID
#   $2 = task slug
# Outputs:
#   A validation Markdown file under toolchain/runs/<run-id>/validation/.
# Lifecycle role:
#   This reserves the place where validator output should live for a task.
# Note:
#   Like run-worker.sh, this is currently scaffold behavior rather than a direct
#   live agent invocation.

# Fail fast on command errors, unset variables, and failed pipelines.
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <run-id> <task-slug>" >&2
  exit 1
fi

# Resolve the run-specific validation output path.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ID="$1"
TASK_SLUG="$2"
RUN_DIR="$REPO_ROOT/toolchain/runs/$RUN_ID"

# Seed a validation document that a real validator run can later replace or update.
cat > "$RUN_DIR/validation/${TASK_SLUG}.validation.md" <<EOF
# Validation result

- run_id: $RUN_ID
- task: $TASK_SLUG
- status: needs-review
- notes: replace with validator output from the worker-validator agent
EOF

printf '%s\n' "$RUN_DIR/validation/${TASK_SLUG}.validation.md"
