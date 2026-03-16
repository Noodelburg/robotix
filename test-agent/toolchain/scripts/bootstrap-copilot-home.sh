#!/usr/bin/env bash
#
# bootstrap-copilot-home.sh
# -------------------------
# Purpose:
#   Create an isolated COPILOT_HOME for this repository so the toolchain uses
#   repo-local Copilot state instead of depending on a user's global setup.
# Inputs:
#   Optional COPILOT_HOME environment variable override.
# Outputs:
#   A repo-local Copilot config directory and a copied config.json.
# Lifecycle role:
#   This is usually the first script you run before planning or executing a run.

# Fail fast on command errors, unset variables, and failed pipelines.
set -euo pipefail

# Resolve the repository root relative to this script so callers can run it from
# any working directory.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Respect an existing COPILOT_HOME override, but default to a repo-local folder.
export COPILOT_HOME="${COPILOT_HOME:-$REPO_ROOT/.toolchain-copilot-home}"

# Create the destination directory if it does not already exist.
mkdir -p "$COPILOT_HOME"

# Materialize the template config into the isolated Copilot home.
cp "$REPO_ROOT/toolchain/config/copilot-config.template.json" "$COPILOT_HOME/config.json"

# Print the final path so wrapper scripts and users can see where state was written.
printf 'COPILOT_HOME=%s\n' "$COPILOT_HOME"
