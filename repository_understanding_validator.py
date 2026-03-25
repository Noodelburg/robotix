#!/usr/bin/env python3
"""Validator for repository_understanding_worker.py outputs."""

import argparse
import json
from pathlib import Path

from prompts import build_repository_understanding_validation_prompt
from repository_understanding_worker import (
    CATEGORIES,
    CATEGORY_ALLOWED_VALUES,
    CATEGORY_FIELDS,
    DEFAULT_OUTPUT_FILE,
    build_final_summary,
    build_output,
    call_ai,
    find_finding_like_terms,
    load_repository_input,
    normalize_ai_repository_map,
    normalize_string_list,
    normalize_text,
)

DEFAULT_REPORT_FILE = "repository-understanding-validation.json"


def make_issue(message, category="system_map", entity_name=None):
    """Create a normalized validation issue."""
    return {
        "category": normalize_text(category),
        "entity_name": normalize_text(entity_name),
        "message": normalize_text(message),
    }


def merge_issues(*issue_lists):
    """Merge issue lists without duplicates while keeping stable ordering."""
    seen = set()
    merged = []

    for issue_list in issue_lists:
        for issue in issue_list:
            normalized = make_issue(
                message=issue.get("message", ""),
                category=issue.get("category", "system_map"),
                entity_name=issue.get("entity_name", ""),
            )
            key = (
                normalized["category"],
                normalized["entity_name"],
                normalized["message"],
            )

            if not normalized["message"] or key in seen:
                continue

            seen.add(key)
            merged.append(normalized)

    return sorted(
        merged,
        key=lambda issue: (
            issue["category"].casefold(),
            issue["entity_name"].casefold(),
            issue["message"].casefold(),
        ),
    )


def load_repository_output(output_path: Path):
    """Load the repository-understanding output to be validated."""
    issues = []

    if not output_path.exists():
        issues.append(
            make_issue(
                f"Repository-understanding output is missing: {output_path.name}",
                category="input",
            )
        )
        return None, issues

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(
            make_issue(
                f"Repository-understanding output is unreadable: {exc}",
                category="input",
            )
        )
        return None, issues

    if not isinstance(payload, dict):
        issues.append(
            make_issue(
                "Repository-understanding output must be a JSON object.",
                category="input",
            )
        )
        return None, issues

    return payload, issues


def build_known_context(document):
    """Build lookup tables from the validated repository-understanding input."""
    chunks = document.get("chunks", [])
    known_chunk_ids = {chunk["id"] for chunk in chunks}
    files_by_chunk = {
        chunk["id"]: {file_info["path"] for file_info in chunk.get("files", [])}
        for chunk in chunks
    }
    known_paths = {
        file_info["path"]
        for chunk in chunks
        for file_info in chunk.get("files", [])
    }

    return {
        "root_path": document.get("root_path"),
        "chunks": chunks,
        "known_chunk_ids": known_chunk_ids,
        "files_by_chunk": files_by_chunk,
        "known_paths": known_paths,
        "source_file_count": len(known_paths),
    }


def audit_input_metadata(output, context):
    """Audit the top-level input metadata in the current output."""
    issues = []
    input_payload = output.get("input")
    root_path = context["root_path"]

    if not isinstance(input_payload, dict):
        issues.append(
            make_issue(
                "Output is missing the top-level input metadata object.",
                category="input",
            )
        )
        return issues

    if normalize_text(input_payload.get("root")) != str(root_path):
        issues.append(
            make_issue(
                "Output input.root does not match the validated repository input root.",
                category="input",
            )
        )

    chunk_count = int(input_payload.get("chunk_count", -1)) if str(input_payload.get("chunk_count", "")).isdigit() else -1
    if chunk_count != len(context["chunks"]):
        issues.append(
            make_issue(
                "Output input.chunk_count does not match the validated input.",
                category="input",
            )
        )

    source_file_count = (
        int(input_payload.get("source_file_count", -1))
        if str(input_payload.get("source_file_count", "")).isdigit()
        else -1
    )
    if source_file_count != context["source_file_count"]:
        issues.append(
            make_issue(
                "Output input.source_file_count does not match the validated input.",
                category="input",
            )
        )

    return issues


def audit_context_only_text(text, message, category, entity_name=None):
    """Create an issue when text looks like a vulnerability finding."""
    finding_like_terms = find_finding_like_terms(text)

    if not finding_like_terms:
        return []

    return [
        make_issue(
            f"{message} ({', '.join(finding_like_terms)})",
            category=category,
            entity_name=entity_name,
        )
    ]


def audit_evidence(category, item_name, evidence_list, context):
    """Audit evidence references for a single entity."""
    issues = []
    seen = set()
    valid_evidence = 0

    if not isinstance(evidence_list, list) or not evidence_list:
        issues.append(
            make_issue(
                f"{category} item is missing evidence.",
                category=category,
                entity_name=item_name,
            )
        )
        return issues

    for evidence in evidence_list:
        if not isinstance(evidence, dict):
            issues.append(
                make_issue(
                    "Evidence entry must be a JSON object.",
                    category=category,
                    entity_name=item_name,
                )
            )
            continue

        chunk_id = normalize_text(evidence.get("chunk_id"))
        files = normalize_string_list(evidence.get("files", []))
        rationale = normalize_text(evidence.get("rationale"))

        if chunk_id not in context["known_chunk_ids"]:
            issues.append(
                make_issue(
                    f"Evidence references unknown chunk id {chunk_id!r}.",
                    category=category,
                    entity_name=item_name,
                )
            )
            continue

        if not files:
            issues.append(
                make_issue(
                    "Evidence entry is missing files.",
                    category=category,
                    entity_name=item_name,
                )
            )
            continue

        invalid_paths = []

        for path in files:
            if path not in context["known_paths"]:
                invalid_paths.append(path)
                continue
            if path not in context["files_by_chunk"].get(chunk_id, set()):
                invalid_paths.append(path)

        if invalid_paths:
            issues.append(
                make_issue(
                    f"Evidence files do not match the referenced chunk: {', '.join(invalid_paths)}",
                    category=category,
                    entity_name=item_name,
                )
            )
            continue

        if not rationale:
            issues.append(
                make_issue(
                    "Evidence entry is missing rationale.",
                    category=category,
                    entity_name=item_name,
                )
            )
            continue

        evidence_key = (chunk_id, tuple(files), rationale.casefold())
        if evidence_key in seen:
            issues.append(
                make_issue(
                    "Entity contains duplicate evidence entries.",
                    category=category,
                    entity_name=item_name,
                )
            )
            continue

        seen.add(evidence_key)
        valid_evidence += 1

    if valid_evidence == 0:
        issues.append(
            make_issue(
                "Entity has no valid evidence after validation.",
                category=category,
                entity_name=item_name,
            )
        )

    return issues


def audit_category_items(category, raw_items, context):
    """Audit one system_map category."""
    issues = []
    seen_names = set()

    if not isinstance(raw_items, list):
        issues.append(
            make_issue(
                f"{category} must be a list.",
                category=category,
            )
        )
        return issues

    for item in raw_items:
        if not isinstance(item, dict):
            issues.append(
                make_issue(
                    f"{category} contains a non-object entity.",
                    category=category,
                )
            )
            continue

        name = normalize_text(item.get("name"))
        summary = normalize_text(item.get("summary"))

        if not name:
            issues.append(
                make_issue(
                    "Entity is missing name.",
                    category=category,
                )
            )
            continue

        if not summary:
            issues.append(
                make_issue(
                    "Entity is missing summary.",
                    category=category,
                    entity_name=name,
                )
            )

        issues.extend(
            audit_context_only_text(
                text=name,
                message="Entity name looks like a vulnerability finding instead of neutral context.",
                category=category,
                entity_name=name,
            )
        )
        issues.extend(
            audit_context_only_text(
                text=summary,
                message="Entity summary looks like a vulnerability finding instead of neutral context.",
                category=category,
                entity_name=name,
            )
        )

        name_key = name.casefold()
        if name_key in seen_names:
            issues.append(
                make_issue(
                    "Category contains a duplicate entity name.",
                    category=category,
                    entity_name=name,
                )
            )
        else:
            seen_names.add(name_key)

        for field_name, default_value in CATEGORY_FIELDS[category].items():
            if field_name not in item:
                issues.append(
                    make_issue(
                        f"Entity is missing category field {field_name!r}.",
                        category=category,
                        entity_name=name,
                    )
                )
                continue

            field_value = item.get(field_name)

            if isinstance(default_value, list) and not isinstance(field_value, list):
                issues.append(
                    make_issue(
                        f"Category field {field_name!r} must be a list.",
                        category=category,
                        entity_name=name,
                    )
                )
            if isinstance(default_value, str) and not isinstance(field_value, str):
                issues.append(
                    make_issue(
                        f"Category field {field_name!r} must be a string.",
                        category=category,
                        entity_name=name,
                    )
                )

        for field_name, allowed_values in CATEGORY_ALLOWED_VALUES.get(category, {}).items():
            field_value = normalize_text(item.get(field_name))
            if field_value and field_value not in allowed_values:
                issues.append(
                    make_issue(
                        f"Category field {field_name!r} has unsupported value {field_value!r}.",
                        category=category,
                        entity_name=name,
                    )
                )

        issues.extend(audit_evidence(category, name, item.get("evidence", []), context))

    return issues


def audit_coverage_gaps(raw_gaps, context):
    """Audit top-level coverage gaps."""
    issues = []

    if not isinstance(raw_gaps, list):
        issues.append(
            make_issue(
                "coverage_gaps must be a list.",
                category="coverage_gaps",
            )
        )
        return issues

    for gap in raw_gaps:
        if not isinstance(gap, dict):
            issues.append(
                make_issue(
                    "coverage_gaps contains a non-object entry.",
                    category="coverage_gaps",
                )
            )
            continue

        category = normalize_text(gap.get("category"))
        summary = normalize_text(gap.get("summary"))
        chunk_ids = normalize_string_list(gap.get("chunk_ids", []))

        if not category:
            issues.append(
                make_issue(
                    "Coverage gap is missing category.",
                    category="coverage_gaps",
                )
            )

        if not summary:
            issues.append(
                make_issue(
                    "Coverage gap is missing summary.",
                    category="coverage_gaps",
                )
            )

        issues.extend(
            audit_context_only_text(
                text=summary,
                message="Coverage gap summary looks like a vulnerability finding instead of neutral context.",
                category="coverage_gaps",
            )
        )

        invalid_chunk_ids = [
            chunk_id for chunk_id in chunk_ids if chunk_id not in context["known_chunk_ids"]
        ]
        if invalid_chunk_ids:
            issues.append(
                make_issue(
                    f"Coverage gap references unknown chunk ids: {', '.join(invalid_chunk_ids)}",
                    category="coverage_gaps",
                )
            )

    return issues


def audit_repository_understanding_output(output, document):
    """Run deterministic checks over the current repository-understanding output."""
    issues = []

    if not isinstance(output, dict):
        return [
            make_issue(
                "Repository-understanding output must be a JSON object.",
                category="input",
            )
        ]

    context = build_known_context(document)
    status = normalize_text(output.get("status"))
    summary = normalize_text(output.get("summary"))
    system_map = output.get("system_map")
    coverage_gaps = output.get("coverage_gaps")

    if status not in {"pass", "needs_review"}:
        issues.append(
            make_issue(
                "Output status must be either 'pass' or 'needs_review'.",
                category="input",
            )
        )

    if not summary:
        issues.append(
            make_issue(
                "Output summary is missing.",
                category="input",
            )
        )
    else:
        issues.extend(
            audit_context_only_text(
                text=summary,
                message="Output summary looks like a vulnerability finding instead of neutral repository context.",
                category="input",
            )
        )

    issues.extend(audit_input_metadata(output, context))

    if not isinstance(system_map, dict):
        issues.append(
            make_issue(
                "Output is missing a system_map object.",
                category="system_map",
            )
        )
    else:
        for category in CATEGORIES:
            issues.extend(audit_category_items(category, system_map.get(category, []), context))

    issues.extend(audit_coverage_gaps(coverage_gaps, context))

    if isinstance(system_map, dict):
        non_empty_categories = any(system_map.get(category) for category in CATEGORIES)
        if not non_empty_categories and not coverage_gaps:
            issues.append(
                make_issue(
                    "Output has no entities and no coverage gaps.",
                    category="system_map",
                )
            )

    return merge_issues(issues)


def collect_evidence_bundle(output, context):
    """Collect evidence-backed file contents for the AI validation pass."""
    if not isinstance(output, dict):
        return "[current output unavailable]"

    system_map = output.get("system_map")
    if not isinstance(system_map, dict):
        return "[system_map unavailable]"

    referenced_paths = []
    seen = set()

    for category in CATEGORIES:
        for item in system_map.get(category, []):
            if not isinstance(item, dict):
                continue
            for evidence in item.get("evidence", []):
                if not isinstance(evidence, dict):
                    continue
                for path in normalize_string_list(evidence.get("files", [])):
                    if path in context["known_paths"] and path not in seen:
                        seen.add(path)
                        referenced_paths.append(path)

    if not referenced_paths:
        return "[no evidence-backed files referenced by current output]"

    sections = []
    root_path = context["root_path"]

    for relative_path in referenced_paths:
        file_path = root_path / relative_path
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            content = f"[unreadable file: {exc}]"

        sections.append(f"=== FILE: {relative_path} ===\n{content}")

    return "\n\n".join(sections)


def fallback_report(audit_issues):
    """Build a deterministic fallback validation report."""
    if audit_issues:
        return {
            "status": "needs_review",
            "summary": f"Deterministic audit found {len(audit_issues)} issue(s).",
            "issues": audit_issues,
            "corrected_output": None,
        }

    return {
        "status": "pass",
        "summary": "Deterministic audit found no issues.",
        "issues": [],
        "corrected_output": None,
    }


def canonicalize_candidate_output(candidate_output, document):
    """Normalize a candidate corrected output into the worker's canonical shape."""
    context = build_known_context(document)
    normalized_result, problems = normalize_ai_repository_map(
        raw_result=candidate_output,
        allowed_chunk_ids=context["known_chunk_ids"],
        allowed_paths=context["known_paths"],
        fallback_chunk_ids=sorted(context["known_chunk_ids"]),
    )
    canonical_output = build_output(
        status="needs_review" if problems else "pass",
        summary=build_final_summary(
            chunk_count=len(context["chunks"]),
            coverage_gaps=normalized_result["coverage_gaps"],
            problems=problems,
            synthesized_summary=normalized_result["summary"],
        ),
        root_path=context["root_path"],
        chunks=context["chunks"],
        system_map=normalized_result["system_map"],
        coverage_gaps=normalized_result["coverage_gaps"],
    )
    problem_issues = [
        make_issue(message=problem, category="system_map")
        for problem in problems
    ]
    return canonical_output, problem_issues


def normalize_ai_validation_report(report, document, audit_issues):
    """Normalize the AI validator response into a stable structure."""
    if not isinstance(report, dict):
        return fallback_report(audit_issues)

    status = normalize_text(report.get("status")) or "needs_review"
    if status not in {"pass", "corrected", "needs_review"}:
        status = "needs_review"

    issues = merge_issues(report.get("issues", []))
    corrected_output = None

    raw_corrected_output = report.get("corrected_output")
    if isinstance(raw_corrected_output, dict):
        corrected_output, correction_issues = canonicalize_candidate_output(
            raw_corrected_output,
            document,
        )
        issues = merge_issues(issues, correction_issues)

    summary = normalize_text(report.get("summary"))
    if not summary:
        if corrected_output is not None:
            summary = "AI proposed corrections to the repository-understanding output."
        elif issues:
            summary = "AI found issues that need review."
        else:
            summary = "AI found no issues."

    return {
        "status": status,
        "summary": summary,
        "issues": issues,
        "corrected_output": corrected_output,
    }


def validate_repository_understanding(input_json_path, output_json_path=None):
    """Validate and, if possible, correct repository-understanding output in place."""
    input_path = Path(input_json_path).resolve()
    output_path = (
        Path(output_json_path).resolve()
        if output_json_path
        else input_path.parent / DEFAULT_OUTPUT_FILE
    )
    report_path = output_path.parent / DEFAULT_REPORT_FILE

    document, input_messages = load_repository_input(input_path)
    input_issues = [
        make_issue(message=message, category="input")
        for message in input_messages
    ]
    current_output, output_issues = load_repository_output(output_path)
    audit_issues = merge_issues(input_issues, output_issues)

    if document and current_output is not None:
        audit_issues = merge_issues(
            audit_issues,
            audit_repository_understanding_output(current_output, document),
        )

    normalized_ai_report = fallback_report(audit_issues)
    corrections_applied = False

    if document and current_output is not None:
        context = build_known_context(document)
        prompt = build_repository_understanding_validation_prompt(
            input_json=json.dumps(
                {
                    "root": str(context["root_path"]) if context["root_path"] else "",
                    "chunks": context["chunks"],
                },
                indent=2,
            ),
            audit_json=json.dumps(audit_issues, indent=2),
            current_output_json=json.dumps(current_output, indent=2),
            evidence_bundle=collect_evidence_bundle(current_output, context),
        )
        ai_report = call_ai(prompt)
        normalized_ai_report = normalize_ai_validation_report(
            ai_report,
            document,
            audit_issues,
        )

    corrected_output = normalized_ai_report.get("corrected_output")
    if corrected_output is not None and current_output is not None:
        if current_output != corrected_output:
            output_path.write_text(json.dumps(corrected_output, indent=2), encoding="utf-8")
            current_output = corrected_output
            corrections_applied = True

    remaining_issues = []
    if document and current_output is not None:
        remaining_issues = audit_repository_understanding_output(current_output, document)
    elif audit_issues:
        remaining_issues = audit_issues

    all_issues = merge_issues(audit_issues, normalized_ai_report["issues"])
    if remaining_issues:
        final_status = "needs_review"
    elif corrections_applied:
        final_status = "corrected"
    else:
        final_status = "pass"

    if final_status == "pass":
        final_summary = "Validator found no issues and made no changes."
    elif final_status == "corrected":
        final_summary = (
            f"Validator corrected the repository-understanding output and resolved "
            f"{len(all_issues)} issue(s)."
        )
    elif corrections_applied:
        final_summary = (
            f"Validator applied corrections, but {len(remaining_issues)} issue(s) still need review."
        )
    else:
        final_summary = f"Validator found {len(all_issues)} issue(s) that need review."

    final_report = {
        "status": final_status,
        "summary": final_summary,
        "corrections_applied": corrections_applied,
        "issues": all_issues,
        "remaining_issues": remaining_issues,
    }

    if corrections_applied:
        final_report["output_file"] = output_path.name

    report_path.write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    return final_report


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Validate repository-understanding output generated by repository_understanding_worker.py."
    )
    parser.add_argument("input_json", help="Path to the repository-understanding input JSON.")
    parser.add_argument(
        "output_json",
        nargs="?",
        help="Optional path to repository-understanding.json. Defaults next to the input JSON.",
    )
    args = parser.parse_args()
    validate_repository_understanding(args.input_json, args.output_json)


if __name__ == "__main__":
    main()
