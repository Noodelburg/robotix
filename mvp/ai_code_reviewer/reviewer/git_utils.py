"""Helpers for loading diffs from a file or from git."""

from __future__ import annotations

import subprocess
from pathlib import Path


def read_diff_file(diff_file: str) -> str:
    """Read a diff from a text file."""
    return Path(diff_file).read_text(encoding="utf-8")


def get_git_diff(repo_path: str, base_ref: str) -> str:
    """Collect a diff using `git diff`.

    This intentionally uses a small subprocess call so the flow is easy to
    understand and later replace if needed.
    """

    command = ["git", "-C", repo_path, "diff", base_ref]
    result = subprocess.run(command, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")

    return result.stdout

