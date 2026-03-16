"""Provider exports and a tiny provider factory."""

from __future__ import annotations

from ..config import Settings
from .base import BaseReviewProvider
from .mock_provider import MockProvider


def build_provider(settings: Settings) -> BaseReviewProvider:
    """Create the active provider from configuration."""
    if settings.provider_name == "mock":
        return MockProvider()

    if settings.provider_name == "openai":
        # Import lazily so the mock path stays usable even if OpenAI
        # dependencies are not installed yet.
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    raise ValueError(
        f"Unknown provider '{settings.provider_name}'. Expected 'mock' or 'openai'."
    )


__all__ = ["BaseReviewProvider", "MockProvider", "build_provider"]
