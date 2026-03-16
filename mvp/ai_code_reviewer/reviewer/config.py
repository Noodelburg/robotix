"""Configuration helpers for the reviewer app.

The goal of this module is to keep configuration in one obvious place.
For a small CLI app, environment variables are enough and easy to learn.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    provider_name: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"


def load_settings() -> Settings:
    """Load settings from a local .env file and the current environment."""
    load_dotenv()

    return Settings(
        provider_name=os.getenv("REVIEWER_PROVIDER", "mock").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini").strip(),
    )

