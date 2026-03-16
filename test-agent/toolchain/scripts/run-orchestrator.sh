#!/usr/bin/env bash
#
# run-orchestrator.sh
# -------------------
# Purpose:
#   Create starter worker task files for a given run phase and record a simple
#   orchestrator log.
# Inputs:
#   $1 = run ID
#   $2 = phase name such as read-only-plan or active-plan
# Outputs:
#   Task files under toolchain/runs/<run-id>/tasks/ and an orchestrator log.
# Lifecycle role:
#   This represents the planning step that decides what workers should exist.
# Note:
#   This is currently scaffold behavior rather than a live agent run.

# Fail fast on command errors, unset variables, and failed pipelines.
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <run-id> <phase>" >&2
  exit 1
fi

# Resolve the run-scoped paths that this script will write to.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_ID="$1"
PHASE="$2"
RUN_DIR="$REPO_ROOT/toolchain/runs/$RUN_ID"
OUT="$RUN_DIR/logs/orchestrator-${PHASE}.session.md"
TASK_TEMPLATE="$REPO_ROOT/toolchain/templates/worker-task.template.md"

# Helper: build one task file by replacing placeholders in the Markdown template.
create_task() {
  local task_id="$1"
  local worker="$2"
  local category="$3"
  local active_testing="$4"
  local target_url="$5"
  local objective="$6"
  local code_reference="$7"
  local task_slug="${task_id}-${category}"
  local task_file="$RUN_DIR/tasks/${task_slug}.task.md"

  sed \
    -e "s/__RUN_ID__/$RUN_ID/g" \
    -e "s/__TASK_ID__/$task_id/g" \
    -e "s/__WORKER__/$worker/g" \
    -e "s/__CATEGORY__/$category/g" \
    -e "s/__ACTIVE_TESTING__/$active_testing/g" \
    -e "s#__TARGET_BASE_URL__#$target_url#g" \
    -e "s/__TASK_SLUG__/$task_slug/g" \
    -e "s/__OBJECTIVE__/$objective/g" \
    -e "s#__CODE_REFERENCE__#$code_reference#g" \
    "$TASK_TEMPLATE" > "$task_file"
}

# Create a small starter task set based on the requested phase.
case "$PHASE" in
  read-only-plan)
    # Read-only tasks analyze source and configuration before any active probing.
    create_task \
      "WK-001" \
      "code-surface-mapper" \
      "surface-map" \
      "false" \
      "https://api.staging.example.com" \
      "Build the source-aware system profile, attack surface map, and trust-boundary summary for this repository." \
      "repository-wide"
    create_task \
      "WK-010" \
      "security-hypothesis" \
      "hypothesis-generation" \
      "false" \
      "https://api.staging.example.com" \
      "Generate prioritized security and robustness hypotheses from source, config, and deployment artifacts." \
      "toolchain-overview.md"
    ;;
  active-plan)
    # Active tasks assume useful hypotheses already exist and are ready to be exercised.
    create_task \
      "WK-020" \
      "exploitability-runner" \
      "exploitability" \
      "true" \
      "https://api.staging.example.com" \
      "Convert validated high-value hypotheses into payload packs and execute approved curl-based checks." \
      "toolchain-implementation.md"
    create_task \
      "WK-030" \
      "robustness-runner" \
      "robustness" \
      "true" \
      "https://api.staging.example.com" \
      "Expand suspicious exploitability signals into focused malformed-input and boundary-condition checks." \
      "toolchain-overview.md"
    ;;
esac

# Record the fact that this phase was prepared and where the generated tasks live.
cat > "$OUT" <<EOF
# Orchestrator session

- run_id: $RUN_ID
- phase: $PHASE
- status: planned
- tasks_directory: $RUN_DIR/tasks
- next_step: invoke Copilot CLI with the test-orchestrator agent in the target environment if you want model-authored task refinement
EOF

printf '%s\n' "$OUT"
