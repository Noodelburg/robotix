"""CLI entrypoint for the simplified Python source-review flow."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

from models import RunConfig
from orchestrator import run_review


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the review run."""

    parser = argparse.ArgumentParser(
        description="Review a repository's source code for simple security-focused findings and generate test specs."
    )
    parser.add_argument("--repo", required=True, help="Path to the repository that should be reviewed.")
    parser.add_argument(
        "--output-root",
        default="simple_toolchain/runs",
        help="Directory where run outputs should be written.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional explicit run ID. Defaults to a timestamp-based ID.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=250,
        help="Maximum number of source/config files to review.",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=200000,
        help="Maximum size in bytes for any reviewed file.",
    )
    return parser.parse_args()


def default_run_id() -> str:
    """Return a deterministic timestamp-style run ID."""

    return "RUN-" + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def main() -> int:
    """Build the run configuration, execute the review, and print the run directory."""

    args = parse_args()
    config = RunConfig(
        repo_path=Path(args.repo),
        output_root=Path(args.output_root),
        run_id=args.run_id or default_run_id(),
        max_files=args.max_files,
        max_file_bytes=args.max_file_bytes,
    )
    try:
        run_dir = run_review(config)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
