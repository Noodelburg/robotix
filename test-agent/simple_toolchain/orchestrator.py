"""Orchestrator for the simplified Python source-review flow."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence

from models import Finding, RunConfig, SourceFile, SourceIndexEntry
from renderers import (
    build_generated_test,
    render_curl_script,
    render_findings_markdown,
    render_test_markdown,
    sort_findings,
    write_json,
)
from worker import review_batch


EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "vendor",
    "target",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
}

INCLUDED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".rs",
    ".kt",
    ".kts",
    ".yaml",
    ".yml",
    ".json",
}


def run_review(config: RunConfig) -> Path:
    """Run the full simplified review flow and return the run directory path."""

    repo_path = config.repo_path.resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {repo_path}")

    run_dir = config.output_root / config.run_id
    tests_dir = run_dir / "tests"
    logs_dir = run_dir / "logs"
    tests_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    orchestrator_log: List[str] = []
    worker_log: List[str] = []

    orchestrator_log.append(f"run_id={config.run_id}")
    orchestrator_log.append(f"repo_path={repo_path}")

    source_files = discover_source_files(config, repo_path)
    orchestrator_log.append(f"discovered_files={len(source_files)}")

    write_manifest(run_dir, config, repo_path, len(source_files))
    write_source_index(run_dir, source_files)

    findings = collect_findings(source_files, config.batch_size, worker_log)
    findings = sort_findings(dedupe_findings(findings))
    findings = assign_finding_ids(findings)

    write_json(run_dir / "findings.json", findings)
    (run_dir / "findings.md").write_text(render_findings_markdown(findings), encoding="utf-8")
    write_tests(tests_dir, findings)

    (logs_dir / "orchestrator.log").write_text("\n".join(orchestrator_log) + "\n", encoding="utf-8")
    (logs_dir / "worker.log").write_text("\n".join(worker_log) + "\n", encoding="utf-8")
    return run_dir


def discover_source_files(config: RunConfig, repo_path: Path) -> List[SourceFile]:
    """Discover reviewable files while respecting extension and size limits."""

    discovered: List[SourceFile] = []
    output_root_resolved = config.output_root.resolve()
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        if _is_inside(path.resolve(), output_root_resolved):
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in INCLUDED_EXTENSIONS:
            continue
        try:
            size_bytes = path.stat().st_size
        except OSError:
            continue
        if size_bytes > config.max_file_bytes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        relative_path = path.relative_to(repo_path).as_posix()
        discovered.append(
            SourceFile(
                path=relative_path,
                absolute_path=str(path.resolve()),
                extension=path.suffix.lower(),
                size_bytes=size_bytes,
                text=text,
            )
        )
        if len(discovered) >= config.max_files:
            break

    for index, source_file in enumerate(discovered):
        source_file.batch_id = (index // config.batch_size) + 1
    return discovered


def collect_findings(source_files: Sequence[SourceFile], batch_size: int, worker_log: List[str]) -> List[Finding]:
    """Batch the files and send each batch through the worker."""

    findings: List[Finding] = []
    for batch_number, batch in enumerate(chunked(source_files, batch_size), start=1):
        worker_log.append(f"batch={batch_number} files={len(batch)}")
        batch_findings = review_batch(list(batch))
        worker_log.append(f"batch={batch_number} findings={len(batch_findings)}")
        findings.extend(batch_findings)
    return findings


def dedupe_findings(findings: Iterable[Finding]) -> List[Finding]:
    """Remove duplicate findings by category, file path, and line number."""

    seen = set()
    deduped: List[Finding] = []
    for finding in findings:
        key = (finding.category, finding.file_path, finding.line_number or 0)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def assign_finding_ids(findings: List[Finding]) -> List[Finding]:
    """Assign stable sequential IDs after deduplication and sorting."""

    for index, finding in enumerate(findings, start=1):
        finding.finding_id = f"FND-{index:03d}"
    return findings


def write_manifest(run_dir: Path, config: RunConfig, repo_path: Path, discovered_file_count: int) -> None:
    """Write a small run manifest describing the target and scan limits."""

    manifest = {
        "run_id": config.run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target_repo_path": str(repo_path),
        "output_root": str(config.output_root),
        "max_files": config.max_files,
        "max_file_bytes": config.max_file_bytes,
        "batch_size": config.batch_size,
        "discovered_file_count": discovered_file_count,
    }
    write_json(run_dir / "manifest.json", manifest)


def write_source_index(run_dir: Path, source_files: Sequence[SourceFile]) -> None:
    """Write a summary of the files included in the review."""

    index_entries = [
        SourceIndexEntry(
            path=source_file.path,
            extension=source_file.extension,
            size_bytes=source_file.size_bytes,
            batch_id=source_file.batch_id,
        )
        for source_file in source_files
    ]
    write_json(run_dir / "source-index.json", index_entries)


def write_tests(tests_dir: Path, findings: Sequence[Finding]) -> None:
    """Write one Markdown test spec per finding and optional curl templates."""

    for finding in findings:
        generated_test = build_generated_test(finding)
        (tests_dir / f"{finding.finding_id}.test.md").write_text(
            render_test_markdown(generated_test),
            encoding="utf-8",
        )
        if finding.curl_confirmable and finding.route_hint:
            (tests_dir / f"{finding.finding_id}-confirm.sh").write_text(
                render_curl_script(finding),
                encoding="utf-8",
            )


def chunked(items: Sequence[SourceFile], size: int) -> Iterable[Sequence[SourceFile]]:
    """Yield fixed-size slices from a sequence."""

    for start in range(0, len(items), size):
        yield items[start : start + size]


def _is_inside(path: Path, parent: Path) -> bool:
    """Return True when path is inside parent, otherwise False."""

    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
