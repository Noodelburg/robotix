"""Command line entrypoint for the AI code reviewer."""

from __future__ import annotations

import argparse
import sys

from .config import load_settings
from .git_utils import get_git_diff, read_diff_file
from .models import ReviewReport
from .providers import build_provider
from .reviewer_service import ReviewerService


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    The CLI supports two input modes:
    1. Read an existing diff file
    2. Generate a diff from a git repository
    """

    parser = argparse.ArgumentParser(description="Review a git diff with an LLM.")
    parser.add_argument(
        "--diff-file",
        help="Path to a patch or diff file to review.",
    )
    parser.add_argument(
        "--repo-path",
        help="Path to a git repository. If set, a diff is generated with git.",
    )
    parser.add_argument(
        "--base-ref",
        default="HEAD~1",
        help="Base ref to compare against when --repo-path is used. Default: HEAD~1",
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "openai"],
        help="Override the provider from the environment.",
    )
    return parser.parse_args()


def load_diff_from_args(args: argparse.Namespace) -> str:
    """Choose the diff source based on CLI arguments."""
    if args.diff_file and args.repo_path:
        raise ValueError("Use either --diff-file or --repo-path, not both.")

    if args.diff_file:
        return read_diff_file(args.diff_file)

    if args.repo_path:
        return get_git_diff(args.repo_path, args.base_ref)

    raise ValueError("Provide --diff-file or --repo-path.")


def print_report(report: ReviewReport) -> None:
    """Render the review report in a readable console format."""
    print("Review summary")
    print("--------------")
    print(report.summary.strip() or "No summary provided.")

    if not report.findings:
        print("\nNo significant issues found.")
        return

    print("\nFindings")
    print("--------")

    for index, finding in enumerate(report.findings, start=1):
        print(f"{index}. [{finding.severity.upper()}] {finding.title}")
        print(f"   File: {finding.file_path}")
        print(f"   Category: {finding.category}")
        print(f"   Why it matters: {finding.explanation}")
        print(f"   Suggested fix: {finding.suggested_fix}")


def main() -> int:
    """Run the CLI program."""
    args = parse_args()
    settings = load_settings()

    if args.provider:
        settings.provider_name = args.provider

    try:
        diff_text = load_diff_from_args(args)
        provider = build_provider(settings)
        service = ReviewerService(provider)
        report = service.review_diff(diff_text)
        print_report(report)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

