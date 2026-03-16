"""Small data models used across the project.

Dataclasses keep the project lightweight while still giving us a clear
shape for inputs and outputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReviewFinding:
    """A single issue found in the reviewed diff."""

    file_path: str
    severity: str
    category: str
    title: str
    explanation: str
    suggested_fix: str


@dataclass
class ReviewReport:
    """The full review result returned by a provider."""

    summary: str
    findings: list[ReviewFinding] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewReport":
        """Convert a plain dictionary into typed dataclasses."""
        findings = [
            ReviewFinding(
                file_path=str(item["file_path"]),
                severity=str(item["severity"]),
                category=str(item["category"]),
                title=str(item["title"]),
                explanation=str(item["explanation"]),
                suggested_fix=str(item["suggested_fix"]),
            )
            for item in data.get("findings", [])
        ]
        return cls(summary=str(data.get("summary", "")), findings=findings)

    @classmethod
    def from_json(cls, raw_json: str) -> "ReviewReport":
        """Parse JSON text into a ReviewReport."""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError("Provider returned invalid JSON.") from exc

        return cls.from_dict(data)


def review_report_json_schema() -> dict[str, Any]:
    """JSON Schema used for structured model output.

    Keeping the schema close to the dataclasses makes it easy to see how
    model output maps into Python objects.
    """

    finding_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "file_path": {"type": "string"},
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
            },
            "category": {
                "type": "string",
                "enum": ["bug", "correctness", "security", "maintainability"],
            },
            "title": {"type": "string"},
            "explanation": {"type": "string"},
            "suggested_fix": {"type": "string"},
        },
        "required": [
            "file_path",
            "severity",
            "category",
            "title",
            "explanation",
            "suggested_fix",
        ],
    }

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "findings": {"type": "array", "items": finding_schema},
        },
        "required": ["summary", "findings"],
    }
