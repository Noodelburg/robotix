"""Application service that coordinates the review flow."""

from __future__ import annotations

from .models import ReviewReport
from .providers.base import BaseReviewProvider


class ReviewerService:
    """Small orchestration layer around the active provider."""

    def __init__(self, provider: BaseReviewProvider) -> None:
        self.provider = provider

    def review_diff(self, diff_text: str) -> ReviewReport:
        """Review a diff after a tiny bit of validation."""
        if not diff_text.strip():
            raise ValueError("The diff is empty. There is nothing to review.")

        return self.provider.review_diff(diff_text)

