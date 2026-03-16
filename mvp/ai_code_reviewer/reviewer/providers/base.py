"""Abstract interface for review providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import ReviewReport


class BaseReviewProvider(ABC):
    """Base class for anything that can review a diff."""

    @abstractmethod
    def review_diff(self, diff_text: str) -> ReviewReport:
        """Review a diff and return a typed report."""

