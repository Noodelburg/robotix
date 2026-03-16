"""Simple mock provider for learning and local testing."""

from __future__ import annotations

from ..models import ReviewFinding, ReviewReport
from .base import BaseReviewProvider


def _guess_file_path(diff_text: str) -> str:
    """Extract the first changed file path from a unified diff."""
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            return line.removeprefix("+++ b/")
    return "unknown_file"


class MockProvider(BaseReviewProvider):
    """Return a predictable hardcoded report without calling any API."""

    def review_diff(self, diff_text: str) -> ReviewReport:
        file_path = _guess_file_path(diff_text)

        finding = ReviewFinding(
            file_path=file_path,
            severity="medium",
            category="maintainability",
            title="Mock finding for local testing",
            explanation=(
                "This result is intentionally hardcoded so you can test the CLI "
                "and report formatting before using a real model provider."
            ),
            suggested_fix=(
                "Switch to OpenAIProvider when you are ready to review real diffs."
            ),
        )

        return ReviewReport(
            summary="Mock review completed. This is sample output for local testing.",
            findings=[finding],
        )

