#!/usr/bin/env python3
"""Summarize machine-readable finding files for one run.

This helper scans toolchain/runs/<run-id>/findings/*.json, merges the valid
JSON finding arrays it finds, and writes a compact summary to reports/summary.json.
"""

import json
import pathlib
import sys
from collections import Counter


def load_findings(findings_dir: pathlib.Path):
    """Load all dictionary findings from JSON files in the findings directory."""

    findings = []
    for path in sorted(findings_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Skip malformed JSON so one bad file does not block the whole summary.
            continue
        if isinstance(data, list):
            findings.extend(item for item in data if isinstance(item, dict))
    return findings


def main() -> int:
    """Build aggregate counts for one run and write reports/summary.json."""

    if len(sys.argv) != 2:
        print("usage: summarize-findings.py <run-dir>", file=sys.stderr)
        return 1

    run_dir = pathlib.Path(sys.argv[1])
    findings = load_findings(run_dir / "findings")

    # Aggregate the most useful dimensions for quick reporting and automation.
    severity_counts = Counter(f.get("severity", "unknown") for f in findings)
    status_counts = Counter(f.get("status", "unknown") for f in findings)
    category_counts = Counter(f.get("category", "unknown") for f in findings)

    summary = {
        "run_id": run_dir.name,
        "finding_count": len(findings),
        "severity_counts": dict(sorted(severity_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
    }

    out_path = run_dir / "reports" / "summary.json"
    out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
