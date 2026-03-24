#!/usr/bin/env python3
import json, logging
from collections import defaultdict
from pathlib import Path

from chunker import (
    DEFAULT_MAX_LINES,
    DEFAULT_OUTPUT_DIR,
    call_ai,
    inventory as build_inventory,
    normalize as normalize_chunk_plan,
    write_outputs,
)
from prompts import build_validation_prompt


DEFAULT_CHUNKS_DIR = DEFAULT_OUTPUT_DIR
DEFAULT_REPORT_FILE = "validation.json"


logging.basicConfig(
    filename="validator.log",
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def make_issue(message, severity="medium", chunk_id=None):
    return {
        "chunk_id": chunk_id,
        "severity": severity,
        "message": message,
    }


def merge_issues(*issue_lists):
    """Merge issue lists without duplicates and keep stable ordering."""
    seen = set()
    merged = []
    severity_order = {"high": 0, "medium": 1, "low": 2}

    for issue_list in issue_lists:
        for issue in issue_list:
            normalized = {
                "chunk_id": issue.get("chunk_id"),
                "severity": issue.get("severity", "medium"),
                "message": str(issue.get("message", "")).strip(),
            }
            key = (
                normalized["chunk_id"],
                normalized["severity"],
                normalized["message"],
            )

            if not normalized["message"] or key in seen:
                continue

            seen.add(key)
            merged.append(normalized)

    return sorted(
        merged,
        key=lambda issue: (
            severity_order.get(issue["severity"], 99),
            issue["chunk_id"] or "",
            issue["message"],
        ),
    )


def load_manifest(chunks_dir: Path):
    """Load the chunk manifest JSON."""
    manifest_path = chunks_dir / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def extract_chunk_metadata(chunk_document):
    """Extract metadata from a structured chunk JSON document."""
    return {
        "id": chunk_document.get("id"),
        "name": chunk_document.get("name"),
        "reason": chunk_document.get("reason", ""),
        "total_lines": chunk_document.get("total_lines", 0),
        "files": [
            {
                "path": file_info.get("path"),
                "lines": file_info.get("lines", 0),
            }
            for file_info in chunk_document.get("files", [])
        ],
    }


def load_chunk_artifacts(chunks_dir: Path, manifest):
    """Load chunk JSON files, metadata, and raw contents."""
    artifacts = []
    issues = []

    for chunk in manifest.get("chunks", []):
        chunk_file = chunks_dir / chunk["file"]
        artifact = {
            "id": chunk.get("id"),
            "file": chunk.get("file"),
            "content": "",
            "metadata": None,
        }

        if not chunk_file.exists():
            issues.append(
                make_issue(
                    f"Chunk file is missing: {chunk_file.name}",
                    severity="high",
                    chunk_id=chunk.get("id"),
                )
            )
            artifacts.append(artifact)
            continue

        raw_content = chunk_file.read_text(encoding="utf-8", errors="ignore")

        try:
            chunk_document = json.loads(raw_content)
            artifact["metadata"] = extract_chunk_metadata(chunk_document)
            artifact["content"] = json.dumps(chunk_document, indent=2)
        except Exception as exc:
            issues.append(
                make_issue(
                    f"Chunk JSON is unreadable: {chunk_file.name} ({exc})",
                    severity="high",
                    chunk_id=chunk.get("id"),
                )
            )
            artifact["content"] = raw_content

        artifacts.append(artifact)

    return artifacts, issues


def plan_from_manifest(manifest):
    """Convert manifest structure into a normalized chunk plan shape."""
    return {
        "chunks": [
            {
                "id": chunk.get("id"),
                "name": chunk.get("name") or chunk.get("id"),
                "reason": chunk.get("reason", ""),
                "files": list(chunk.get("files", [])),
            }
            for chunk in manifest.get("chunks", [])
        ]
    }


def audit_chunk_output(manifest, artifacts, items):
    """Run deterministic checks on the current chunk outputs."""
    issues = []
    known = {item["path"]: item for item in items}
    max_lines = manifest.get("max_lines", DEFAULT_MAX_LINES)
    artifact_by_id = {artifact["id"]: artifact for artifact in artifacts}
    assignments = defaultdict(list)

    if manifest.get("chunk_count") != len(manifest.get("chunks", [])):
        issues.append(
            make_issue(
                "Manifest chunk_count does not match the number of chunk entries.",
                severity="medium",
            )
        )

    if manifest.get("source_file_count") not in (None, len(items)):
        issues.append(
            make_issue(
                "Manifest source_file_count does not match the rebuilt repo inventory.",
                severity="medium",
            )
        )

    for chunk in manifest.get("chunks", []):
        chunk_id = chunk.get("id")
        manifest_files = list(chunk.get("files", []))
        manifest_total = chunk.get("total_lines", 0)
        actual_total = sum(known[path]["lines"] for path in manifest_files if path in known)
        oversize_allowed = any(
            known[path]["lines"] > max_lines
            for path in manifest_files
            if path in known
        )

        if manifest_total != actual_total:
            issues.append(
                make_issue(
                    "Manifest total_lines does not match the summed file line counts.",
                    severity="medium",
                    chunk_id=chunk_id,
                )
            )

        if max_lines and actual_total > max_lines and not oversize_allowed:
            issues.append(
                make_issue(
                    "Chunk exceeds max_lines even though no single file requires the overflow.",
                    severity="medium",
                    chunk_id=chunk_id,
                )
            )

        artifact = artifact_by_id.get(chunk_id)
        if artifact and artifact.get("metadata"):
            metadata = artifact["metadata"]
            metadata_files = [file_info.get("path") for file_info in metadata.get("files", [])]
            metadata_total = metadata.get("total_lines", 0)

            if metadata_files != manifest_files:
                issues.append(
                    make_issue(
                        "Chunk metadata file list does not match the manifest entry.",
                        severity="medium",
                        chunk_id=chunk_id,
                    )
                )

            if metadata_total != actual_total:
                issues.append(
                    make_issue(
                        "Chunk metadata total_lines does not match the summed file line counts.",
                        severity="medium",
                        chunk_id=chunk_id,
                    )
                )

        for path in manifest_files:
            if path not in known:
                issues.append(
                    make_issue(
                        f"Chunk references a file that is not in the rebuilt inventory: {path}",
                        severity="high",
                        chunk_id=chunk_id,
                    )
                )
            assignments[path].append(chunk_id)

    assigned_paths = set(assignments)
    missing_paths = sorted(set(known) - assigned_paths)

    for path in missing_paths:
        issues.append(
            make_issue(
                f"File is missing from the chunk plan: {path}",
                severity="high",
            )
        )

    for path, chunk_ids in sorted(assignments.items()):
        if len(chunk_ids) > 1:
            issues.append(
                make_issue(
                    f"File appears in multiple chunks: {path} ({', '.join(chunk_ids)})",
                    severity="high",
                )
            )

    return merge_issues(issues)


def inventory_summary(items):
    return "\n".join(
        f'{item["path"]}\t{item["lines"]}\t{item["dir"]}'
        for item in items
    )


def chunk_metadata_summary(artifacts):
    metadata = [
        artifact["metadata"]
        for artifact in artifacts
        if artifact.get("metadata") is not None
    ]
    return json.dumps(metadata, indent=2)


def chunk_content_summary(artifacts):
    sections = []

    for artifact in artifacts:
        title = artifact.get("file") or artifact.get("id") or "unknown"
        content = artifact.get("content") or "[missing chunk file]"
        sections.append(f"=== CHUNK JSON FILE: {title} ===\n{content}")

    return "\n\n".join(sections)


def fallback_report(audit_issues):
    """Build a deterministic report if AI output is unavailable."""
    if audit_issues:
        return {
            "status": "needs_review",
            "summary": f"Deterministic audit found {len(audit_issues)} issue(s).",
            "issues": audit_issues,
            "corrected_chunks": [],
        }

    return {
        "status": "pass",
        "summary": "Deterministic audit found no issues.",
        "issues": [],
        "corrected_chunks": [],
    }


def normalize_ai_report(report, fallback_issues):
    """Normalize the AI response into a stable correction-aware shape."""
    if not isinstance(report, dict):
        return fallback_report(fallback_issues)

    status = report.get("status", "needs_review")
    if status not in {"pass", "corrected", "needs_review"}:
        status = "needs_review"

    issues = merge_issues(report.get("issues", []))
    corrected_chunks = []

    for chunk in report.get("corrected_chunks", []):
        if not isinstance(chunk, dict):
            continue

        files = [str(path) for path in chunk.get("files", []) if str(path).strip()]
        if not files:
            continue

        corrected_chunks.append(
            {
                "id": chunk.get("id"),
                "name": chunk.get("name"),
                "reason": chunk.get("reason", ""),
                "files": files,
            }
        )

    summary = str(report.get("summary", "")).strip()
    if not summary:
        if corrected_chunks:
            summary = "AI proposed corrections to the chunk plan."
        elif issues:
            summary = "AI found issues that need review."
        else:
            summary = "AI found no issues."

    return {
        "status": status,
        "summary": summary,
        "issues": issues,
        "corrected_chunks": corrected_chunks,
    }


def plans_equal(left, right):
    return left.get("chunks", []) == right.get("chunks", [])


def determine_final_status(corrections_applied, remaining_issues):
    if remaining_issues:
        return "needs_review"
    if corrections_applied:
        return "corrected"
    return "pass"


def determine_final_summary(status, corrections_applied, original_issues, remaining_issues):
    if status == "pass":
        return "Validator found no issues and made no changes."
    if status == "corrected":
        return (
            f"Validator corrected the chunk plan and resolved {len(original_issues)} issue(s)."
        )
    if corrections_applied:
        return (
            f"Validator applied corrections, but {len(remaining_issues)} issue(s) still need review."
        )
    return f"Validator found {len(original_issues)} issue(s) that need review."


def write_output(chunks_dir: Path, report):
    """Write the validation report to disk."""
    outpath = chunks_dir / DEFAULT_REPORT_FILE
    outpath.write_text(json.dumps(report, indent=2), encoding="utf-8")


def validate_chunks(chunks_dir: Path):
    """Validate and, if possible, correct chunk output in place."""
    manifest = load_manifest(chunks_dir)
    root = Path(manifest["root"])
    items = build_inventory(root)
    artifacts, artifact_issues = load_chunk_artifacts(chunks_dir, manifest)
    audit_issues = merge_issues(artifact_issues, audit_chunk_output(manifest, artifacts, items))

    ai_prompt = build_validation_prompt(
        inventory_summary=inventory_summary(items),
        manifest_json=json.dumps(manifest, indent=2),
        audit_json=json.dumps(audit_issues, indent=2),
        chunk_metadata_json=chunk_metadata_summary(artifacts),
        chunk_contents=chunk_content_summary(artifacts),
    )
    ai_report = call_ai(ai_prompt)
    normalized_ai_report = (
        normalize_ai_report(ai_report, audit_issues)
        if ai_report
        else fallback_report(audit_issues)
    )

    original_plan = plan_from_manifest(manifest)
    corrected_plan = None
    corrections_applied = False
    max_lines = manifest.get("max_lines", DEFAULT_MAX_LINES)

    if normalized_ai_report["corrected_chunks"]:
        corrected_plan = normalize_chunk_plan(
            {"chunks": normalized_ai_report["corrected_chunks"]},
            items,
            max_lines,
        )

        if not plans_equal(original_plan, corrected_plan):
            write_outputs(root, chunks_dir, corrected_plan, items, max_lines=max_lines)
            corrections_applied = True
            manifest = load_manifest(chunks_dir)
            artifacts, artifact_issues = load_chunk_artifacts(chunks_dir, manifest)

    remaining_issues = merge_issues(
        artifact_issues,
        audit_chunk_output(manifest, artifacts, items),
    )
    all_issues = merge_issues(audit_issues, normalized_ai_report["issues"])
    final_status = determine_final_status(corrections_applied, remaining_issues)
    final_report = {
        "status": final_status,
        "summary": determine_final_summary(
            final_status,
            corrections_applied,
            all_issues,
            remaining_issues,
        ),
        "corrections_applied": corrections_applied,
        "issues": all_issues,
        "remaining_issues": remaining_issues,
    }

    if corrections_applied and corrected_plan is not None:
        final_report["corrected_chunk_count"] = len(corrected_plan["chunks"])

    write_output(chunks_dir, final_report)
    return final_report


def main():
    """Validate the chunking job in the default chunks directory."""
    chunks_dir = Path(DEFAULT_CHUNKS_DIR)

    if not chunks_dir.exists():
        raise FileNotFoundError(f"Chunks directory does not exist: {chunks_dir}")

    validate_chunks(chunks_dir)


if __name__ == "__main__":
    main()
