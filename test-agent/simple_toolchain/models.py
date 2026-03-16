"""Data models for the simplified source review flow.

These dataclasses are intentionally small and explicit so the orchestrator,
worker, and renderers can share structured state without depending on a larger
framework.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, List, Optional


@dataclass
class RunConfig:
    """Runtime configuration for one source-review run."""

    repo_path: Path
    output_root: Path
    run_id: str
    max_files: int
    max_file_bytes: int
    batch_size: int = 25


@dataclass
class SourceFile:
    """A source or config file selected for review."""

    path: str
    absolute_path: str
    extension: str
    size_bytes: int
    text: str
    batch_id: int = 0


@dataclass
class SourceIndexEntry:
    """Serializable summary of one discovered file."""

    path: str
    extension: str
    size_bytes: int
    batch_id: int


@dataclass
class Finding:
    """One normalized security-focused finding emitted by the worker."""

    category: str
    title: str
    severity: str
    file_path: str
    line_number: Optional[int]
    evidence: str
    reasoning: str
    suggested_test: str
    curl_confirmable: bool = False
    route_hint: Optional[str] = None
    finding_id: Optional[str] = None


@dataclass
class GeneratedTest:
    """Renderable test artifact derived from a finding."""

    finding_id: str
    title: str
    target_file: str
    why_it_matters: str
    preconditions: List[str]
    suggested_setup: List[str]
    test_steps: List[str]
    expected_secure_behavior: List[str]
    expected_vulnerable_behavior: List[str]
    curl_script_name: Optional[str] = None


def to_jsonable(value: Any) -> Any:
    """Convert dataclasses and Paths into JSON-friendly primitives."""

    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value
