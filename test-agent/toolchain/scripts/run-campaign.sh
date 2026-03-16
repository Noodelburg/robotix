#!/usr/bin/env bash
#
# run-campaign.sh
# ---------------
# Purpose:
#   Run the current MVP bootstrap flow end to end.
# Inputs:
#   Optional explicit run ID as the first argument.
# Outputs:
#   A new run with starter tasks, starter worker artifacts, and a starter final report.
# Lifecycle role:
#   This is the highest-level convenience wrapper in the current scaffold.
# Flow:
#   1. create a run
#   2. bootstrap isolated Copilot config
#   3. prepare read-only tasks
#   4. prepare starter worker artifacts
#   5. seed a starter final report

# Fail fast on command errors, unset variables, and failed pipelines.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Create the run first so every later artifact has a destination directory.
RUN_ID="$("$REPO_ROOT/toolchain/scripts/create-run.sh" "${1:-}")"

# Prepare repo-local Copilot state and create the read-only starter tasks.
"$REPO_ROOT/toolchain/scripts/bootstrap-copilot-home.sh" >/dev/null
"$REPO_ROOT/toolchain/scripts/run-orchestrator.sh" "$RUN_ID" "read-only-plan" >/dev/null

# Prepare worker outputs for the two read-only tasks created above.
"$REPO_ROOT/toolchain/scripts/run-worker.sh" "$RUN_ID" "$REPO_ROOT/toolchain/runs/$RUN_ID/tasks/WK-001-surface-map.task.md" >/dev/null
"$REPO_ROOT/toolchain/scripts/run-worker.sh" "$RUN_ID" "$REPO_ROOT/toolchain/runs/$RUN_ID/tasks/WK-010-hypothesis-generation.task.md" >/dev/null

# Seed a final report so the run already has a reporting destination.
cat > "$REPO_ROOT/toolchain/runs/$RUN_ID/reports/final-report.md" <<EOF
# Final report

- run_id: $RUN_ID
- status: initialized
- next_steps:
  - run read-only workers or replace prepared artifacts with Copilot-authored outputs
  - generate active tasks from validated hypotheses
  - execute validators
EOF

printf '%s\n' "$RUN_ID"
