"""OpenAI implementation of the review provider.

This module is intentionally small:
- build a prompt
- call the Responses API
- parse JSON into dataclasses
"""

from __future__ import annotations

from openai import OpenAI

from ..models import ReviewReport, review_report_json_schema
from ..prompts import SYSTEM_PROMPT, build_review_prompt
from .base import BaseReviewProvider


class OpenAIProvider(BaseReviewProvider):
    """Review diffs using OpenAI's Responses API."""

    def __init__(self, api_key: str | None, model: str) -> None:
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is missing. Set it in your environment or .env file."
            )

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def review_diff(self, diff_text: str) -> ReviewReport:
        """Send the diff to OpenAI and parse the structured JSON response."""
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=build_review_prompt(diff_text),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "review_report",
                        "strict": True,
                        "schema": review_report_json_schema(),
                    }
                },
            )
        except Exception as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        if not response.output_text:
            raise RuntimeError("OpenAI returned no text output.")

        return ReviewReport.from_json(response.output_text)
