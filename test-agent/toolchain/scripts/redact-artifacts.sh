#!/usr/bin/env bash
#
# redact-artifacts.sh
# -------------------
# Purpose:
#   Scrub common secret-like values from text artifacts before they are shared or
#   promoted into higher-level reports.
# Inputs:
#   $1 = file or directory path
# Outputs:
#   Rewritten text files with matched secret-like values replaced by [REDACTED].
# Lifecycle role:
#   This is a cleanup/safety helper for artifact hygiene before reporting.

# Fail fast on command errors, unset variables, and failed pipelines.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <path>" >&2
  exit 1
fi

TARGET="$1"

# Use Python because recursive traversal and regex replacement are simpler and clearer here.
python3 - "$TARGET" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
patterns = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9._-]+"),
    re.compile(r"([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD)[A-Z0-9_]*=)[^\s]+", re.IGNORECASE),
]

def redact_text(text: str) -> str:
    """Replace known secret-like values with [REDACTED]."""
    for pattern in patterns:
        text = pattern.sub(lambda m: m.group(1) + "[REDACTED]", text)
    return text

# Support both a single file and a directory tree.
paths = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
for path in paths:
    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    redacted = redact_text(original)
    if redacted != original:
        path.write_text(redacted, encoding="utf-8")
PY
