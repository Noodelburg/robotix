#!/usr/bin/env python3
"""Validator for reviewer.py outputs."""

import argparse
import json
from pathlib import Path

from mapper import normalize_string_list, normalize_text
from prompts import build_reviewer_validation_prompt
from reviewer import (
    ATTACK_PATH_FIELDS,
    CERTAINTY_ORDER,
    DEFAULT_INDEX_FILE,
    build_index,
    build_review_context,
    call_ai,
    canonicalize_guide_output,
    finding_key,
    load_system_map_output,
    load_repository_input,
    rejected_hypothesis_key,
)
from wstg_review_guides import load_review_guides


DEFAULT_REPORT_FILE = "validation.json"


def make_issue(wstg_id, category, message, output_file=""):
    """Create a normalized validation issue."""
    return {
        "wstg_id": normalize_text(wstg_id),
        "category": normalize_text(category),
        "message": normalize_text(message),
        "output_file": normalize_text(output_file),
    }


def merge_issues(*issue_lists):
    """Merge issue lists without duplicates while keeping stable ordering."""
    seen = set()
    merged = []

    for issue_list in issue_lists:
        for issue in issue_list:
            normalized = make_issue(
                wstg_id=issue.get("wstg_id", ""),
                category=issue.get("category", "review"),
                message=issue.get("message", ""),
                output_file=issue.get("output_file", ""),
            )
            key = (
                normalized["wstg_id"],
                normalized["category"],
                normalized["message"],
                normalized["output_file"],
            )

            if not normalized["message"] or key in seen:
                continue

            seen.add(key)
            merged.append(normalized)

    return sorted(
        merged,
        key=lambda issue: (
            issue["wstg_id"].casefold(),
            issue["category"].casefold(),
            issue["message"].casefold(),
            issue["output_file"].casefold(),
        ),
    )


def load_json_file(path):
    """Load a JSON file from disk."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_guide_output(output_path):
    """Load one per-guide output file."""
    path = Path(output_path)

    if not path.exists():
        return None, [
            make_issue(
                wstg_id="",
                category="input",
                message=f"Guide output is missing: {path.name}",
                output_file=path.name,
            )
        ]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [
            make_issue(
                wstg_id="",
                category="input",
                message=f"Guide output is unreadable: {exc}",
                output_file=path.name,
            )
        ]

    if not isinstance(payload, dict):
        return None, [
            make_issue(
                wstg_id="",
                category="input",
                message="Guide output must be a JSON object.",
                output_file=path.name,
            )
        ]

    return payload, []


def audit_evidence(wstg_id, category, evidence_list, context, reviewed_chunk_ids, output_file):
    """Audit evidence references for one finding-like record."""
    issues = []
    seen = set()

    if not isinstance(evidence_list, list) or not evidence_list:
        issues.append(
            make_issue(
                wstg_id=wstg_id,
                category=category,
                message="Item is missing evidence.",
                output_file=output_file,
            )
        )
        return issues

    for evidence in evidence_list:
        if not isinstance(evidence, dict):
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category=category,
                    message="Evidence entry must be an object.",
                    output_file=output_file,
                )
            )
            continue

        chunk_id = normalize_text(evidence.get("chunk_id"))
        files = normalize_string_list(evidence.get("files", []))
        rationale = normalize_text(evidence.get("rationale"))
        key = (chunk_id, tuple(files), rationale)

        if chunk_id not in context["known_chunk_ids"]:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category=category,
                    message=f"Evidence references unknown chunk id {chunk_id!r}.",
                    output_file=output_file,
                )
            )
            continue

        if reviewed_chunk_ids and chunk_id not in reviewed_chunk_ids:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category=category,
                    message=f"Evidence chunk {chunk_id} is not listed in reviewed_chunk_ids.",
                    output_file=output_file,
                )
            )

        if not files:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category=category,
                    message="Evidence entry is missing files.",
                    output_file=output_file,
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
                    wstg_id=wstg_id,
                    category=category,
                    message=(
                        "Evidence files do not match the referenced chunk: "
                        + ", ".join(invalid_paths)
                    ),
                    output_file=output_file,
                )
            )

        if not rationale:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category=category,
                    message="Evidence entry is missing rationale.",
                    output_file=output_file,
                )
            )

        if key in seen:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category=category,
                    message="Duplicate evidence entry found.",
                    output_file=output_file,
                )
            )
            continue

        seen.add(key)

    return issues


def audit_candidate_findings(output, context, output_file):
    """Audit candidate findings in one guide output."""
    wstg_id = output["guide"]["wstg_id"]
    issues = []
    seen_finding_ids = set()
    seen_keys = set()
    reviewed_chunk_ids = set(output["input"]["reviewed_chunk_ids"])

    for finding in output.get("candidate_findings", []):
        finding_id = normalize_text(finding.get("finding_id"))
        title = normalize_text(finding.get("title"))
        certainty = normalize_text(finding.get("certainty")).casefold()
        weakness_summary = normalize_text(finding.get("weakness_summary"))
        remediation_direction = normalize_text(finding.get("remediation_direction"))
        counter_evidence = normalize_string_list(finding.get("counter_evidence", []))
        attack_path = finding.get("attack_path")

        if not finding_id:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="candidate_findings",
                    message=f"Candidate finding {title or '<untitled>'} is missing finding_id.",
                    output_file=output_file,
                )
            )
        elif finding_id in seen_finding_ids:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="candidate_findings",
                    message=f"Duplicate finding_id found: {finding_id}.",
                    output_file=output_file,
                )
            )
        else:
            seen_finding_ids.add(finding_id)

        if certainty not in CERTAINTY_ORDER:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="candidate_findings",
                    message=f"Finding {finding_id or title!r} has invalid certainty {certainty!r}.",
                    output_file=output_file,
                )
            )

        if not title or not weakness_summary or not remediation_direction:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="candidate_findings",
                    message=f"Finding {finding_id or title!r} is missing required summary fields.",
                    output_file=output_file,
                )
            )

        if not counter_evidence:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="candidate_findings",
                    message=f"Finding {finding_id or title!r} has no counter_evidence notes.",
                    output_file=output_file,
                )
            )

        if not isinstance(attack_path, dict):
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="candidate_findings",
                    message=f"Finding {finding_id or title!r} is missing attack_path.",
                    output_file=output_file,
                )
            )
        else:
            missing_fields = [
                field_name
                for field_name in ATTACK_PATH_FIELDS
                if not normalize_text(attack_path.get(field_name))
            ]

            if missing_fields:
                issues.append(
                    make_issue(
                        wstg_id=wstg_id,
                        category="candidate_findings",
                        message=(
                            f"Finding {finding_id or title!r} is missing attack_path field(s): "
                            + ", ".join(missing_fields)
                        ),
                        output_file=output_file,
                    )
                )

        issues.extend(
            audit_evidence(
                wstg_id=wstg_id,
                category="candidate_findings",
                evidence_list=finding.get("evidence", []),
                context=context,
                reviewed_chunk_ids=reviewed_chunk_ids,
                output_file=output_file,
            )
        )

        key = finding_key(finding)
        if key in seen_keys:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="candidate_findings",
                    message=f"Duplicate candidate finding found for {title!r}.",
                    output_file=output_file,
                )
            )
        else:
            seen_keys.add(key)

    return issues


def audit_rejected_hypotheses(output, context, output_file):
    """Audit rejected hypotheses in one guide output."""
    wstg_id = output["guide"]["wstg_id"]
    issues = []
    seen = set()
    reviewed_chunk_ids = set(output["input"]["reviewed_chunk_ids"])

    for hypothesis in output.get("rejected_hypotheses", []):
        title = normalize_text(hypothesis.get("title"))
        reason = normalize_text(hypothesis.get("reason"))

        if not title or not reason:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="rejected_hypotheses",
                    message="Rejected hypothesis is missing title or reason.",
                    output_file=output_file,
                )
            )

        issues.extend(
            audit_evidence(
                wstg_id=wstg_id,
                category="rejected_hypotheses",
                evidence_list=hypothesis.get("evidence", []),
                context=context,
                reviewed_chunk_ids=reviewed_chunk_ids,
                output_file=output_file,
            )
        )

        key = rejected_hypothesis_key(hypothesis)
        if key in seen:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="rejected_hypotheses",
                    message=f"Duplicate rejected hypothesis found for {title!r}.",
                    output_file=output_file,
                )
            )
        else:
            seen.add(key)

    return issues


def audit_coverage_gaps(output, context, output_file):
    """Audit coverage gaps in one guide output."""
    wstg_id = output["guide"]["wstg_id"]
    issues = []
    seen = set()

    for gap in output.get("coverage_gaps", []):
        if not isinstance(gap, dict):
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="coverage_gaps",
                    message="Coverage gap entry must be an object.",
                    output_file=output_file,
                )
            )
            continue

        summary = normalize_text(gap.get("summary"))
        reason = normalize_text(gap.get("reason"))
        chunk_ids = normalize_string_list(gap.get("chunk_ids", []))
        key = (summary, reason, tuple(chunk_ids))

        if not summary or not reason:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="coverage_gaps",
                    message="Coverage gap is missing summary or reason.",
                    output_file=output_file,
                )
            )

        if not chunk_ids:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="coverage_gaps",
                    message="Coverage gap is missing chunk_ids.",
                    output_file=output_file,
                )
            )

        invalid_chunk_ids = [
            chunk_id for chunk_id in chunk_ids if chunk_id not in context["known_chunk_ids"]
        ]

        if invalid_chunk_ids:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="coverage_gaps",
                    message=(
                        "Coverage gap references unknown chunk ids: "
                        + ", ".join(invalid_chunk_ids)
                    ),
                    output_file=output_file,
                )
            )

        if key in seen:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="coverage_gaps",
                    message="Duplicate coverage gap found.",
                    output_file=output_file,
                )
            )
        else:
            seen.add(key)

    return issues


def audit_metrics(output, output_file):
    """Audit derived metrics in one guide output."""
    wstg_id = output["guide"]["wstg_id"]
    issues = []
    metrics = output.get("metrics")

    if not isinstance(metrics, dict):
        return [
            make_issue(
                wstg_id=wstg_id,
                category="metrics",
                message="Output is missing the metrics object.",
                output_file=output_file,
            )
        ]

    expected = {
        "routed_chunk_count": len(output["input"]["routed_chunk_ids"]),
        "reviewed_chunk_count": len(output["input"]["reviewed_chunk_ids"]),
        "candidate_finding_count": len(output["candidate_findings"]),
        "rejected_hypothesis_count": len(output["rejected_hypotheses"]),
        "coverage_gap_count": len(output["coverage_gaps"]),
        "expansion_performed": output["input"]["review_depth"] == "expanded",
    }

    for key, value in expected.items():
        if metrics.get(key) != value:
            issues.append(
                make_issue(
                    wstg_id=wstg_id,
                    category="metrics",
                    message=f"Metric {key!r} does not match the canonical value.",
                    output_file=output_file,
                )
            )

    return issues


def audit_guide_output(output, guide, context, system_map_path, output_file):
    """Run deterministic checks over the current guide output."""
    issues = []
    guide_payload = output.get("guide")
    input_payload = output.get("input")
    expected_support_paths = list(guide.get("support_paths", []))

    if normalize_text(output.get("status")) not in {"pass", "corrected", "needs_review"}:
        issues.append(
            make_issue(
                wstg_id=guide["wstg_id"],
                category="status",
                message="Output has an invalid status.",
                output_file=output_file,
            )
        )

    if not isinstance(guide_payload, dict):
        issues.append(
            make_issue(
                wstg_id=guide["wstg_id"],
                category="guide",
                message="Output is missing the guide object.",
                output_file=output_file,
            )
        )
    else:
        if normalize_text(guide_payload.get("wstg_id")) != guide["wstg_id"]:
            issues.append(
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="guide",
                    message="guide.wstg_id does not match the expected guide.",
                    output_file=output_file,
                )
            )

        if normalize_text(guide_payload.get("title")) != guide["title"]:
            issues.append(
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="guide",
                    message="guide.title does not match the expected guide.",
                    output_file=output_file,
                )
            )

        if normalize_text(guide_payload.get("path")) != guide["relative_path"]:
            issues.append(
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="guide",
                    message="guide.path does not match the expected guide path.",
                    output_file=output_file,
                )
            )

        if normalize_text(guide_payload.get("area")) != guide["area"]:
            issues.append(
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="guide",
                    message="guide.area does not match the expected area.",
                    output_file=output_file,
                )
            )

        if normalize_string_list(guide_payload.get("support_paths", [])) != expected_support_paths:
            issues.append(
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="guide",
                    message="guide.support_paths does not match the expected support bundle.",
                    output_file=output_file,
                )
            )

    if not isinstance(input_payload, dict):
        issues.append(
            make_issue(
                wstg_id=guide["wstg_id"],
                category="input",
                message="Output is missing the input object.",
                output_file=output_file,
            )
        )
    else:
        if normalize_text(input_payload.get("root")) != str(context["root_path"]):
            issues.append(
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="input",
                    message="input.root does not match the repository input root.",
                    output_file=output_file,
                )
            )

        if normalize_text(input_payload.get("system_map_path")) != str(Path(system_map_path).resolve()):
            issues.append(
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="input",
                    message="input.system_map_path does not match the system-map path used for review.",
                    output_file=output_file,
                )
            )

        routed_chunk_ids = normalize_string_list(input_payload.get("routed_chunk_ids", []))
        reviewed_chunk_ids = normalize_string_list(input_payload.get("reviewed_chunk_ids", []))

        if not reviewed_chunk_ids:
            issues.append(
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="input",
                    message="input.reviewed_chunk_ids is empty.",
                    output_file=output_file,
                )
            )

        invalid_routed_chunk_ids = [
            chunk_id for chunk_id in routed_chunk_ids if chunk_id not in context["known_chunk_ids"]
        ]
        invalid_reviewed_chunk_ids = [
            chunk_id for chunk_id in reviewed_chunk_ids if chunk_id not in context["known_chunk_ids"]
        ]

        if invalid_routed_chunk_ids:
            issues.append(
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="input",
                    message=(
                        "input.routed_chunk_ids contains unknown chunk ids: "
                        + ", ".join(invalid_routed_chunk_ids)
                    ),
                    output_file=output_file,
                )
            )

        if invalid_reviewed_chunk_ids:
            issues.append(
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="input",
                    message=(
                        "input.reviewed_chunk_ids contains unknown chunk ids: "
                        + ", ".join(invalid_reviewed_chunk_ids)
                    ),
                    output_file=output_file,
                )
            )

        if normalize_text(input_payload.get("review_depth")) not in {"initial", "expanded"}:
            issues.append(
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="input",
                    message="input.review_depth is invalid.",
                    output_file=output_file,
                )
            )

    issues.extend(audit_candidate_findings(output, context, output_file))
    issues.extend(audit_rejected_hypotheses(output, context, output_file))
    issues.extend(audit_coverage_gaps(output, context, output_file))
    issues.extend(audit_metrics(output, output_file))
    return issues


def collect_evidence_bundle(output):
    """Collect a compact evidence bundle for validation prompts."""
    bundle = {
        "candidate_findings": [],
        "rejected_hypotheses": [],
    }

    for finding in output.get("candidate_findings", []):
        bundle["candidate_findings"].append(
            {
                "finding_id": finding.get("finding_id", ""),
                "title": finding.get("title", ""),
                "evidence": finding.get("evidence", []),
            }
        )

    for hypothesis in output.get("rejected_hypotheses", []):
        bundle["rejected_hypotheses"].append(
            {
                "title": hypothesis.get("title", ""),
                "evidence": hypothesis.get("evidence", []),
            }
        )

    return bundle


def normalize_ai_validation_report(report, guide, context, system_map_path, audit_issues):
    """Normalize the AI validator response."""
    if not isinstance(report, dict):
        return {
            "status": "needs_review",
            "summary": "AI validation did not return a usable JSON object.",
            "issues": audit_issues,
            "corrected_output": None,
        }

    status = normalize_text(report.get("status")) or "needs_review"
    if status not in {"pass", "corrected", "needs_review"}:
        status = "needs_review"

    issues = merge_issues(report.get("issues", []))
    corrected_output = None
    raw_corrected_output = report.get("corrected_output")

    if isinstance(raw_corrected_output, dict):
        corrected_output, canonicalization_problems = canonicalize_guide_output(
            raw_output=raw_corrected_output,
            guide=guide,
            context=context,
            system_map_path=system_map_path,
        )
        issues = merge_issues(
            issues,
            [
                make_issue(
                    wstg_id=guide["wstg_id"],
                    category="validation",
                    message=problem,
                )
                for problem in canonicalization_problems
            ],
        )

    summary = normalize_text(report.get("summary"))
    if not summary:
        if corrected_output is not None:
            summary = "AI proposed corrections to the guide output."
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


def validate_guide_output(output_path, guide, context, system_map_path, input_document):
    """Validate and, if possible, correct one guide output."""
    output_path = Path(output_path)
    current_output, load_issues = load_guide_output(output_path)
    audit_issues = list(load_issues)

    if current_output is None:
        return {
            "wstg_id": guide["wstg_id"],
            "output_file": output_path.name,
            "status": "needs_review",
            "summary": "Guide output is missing or unreadable.",
            "corrections_applied": False,
            "issues": audit_issues,
            "remaining_issues": audit_issues,
        }

    current_output, canonicalization_problems = canonicalize_guide_output(
        raw_output=current_output,
        guide=guide,
        context=context,
        system_map_path=system_map_path,
    )
    audit_issues.extend(
        make_issue(
            wstg_id=guide["wstg_id"],
            category="validation",
            message=problem,
            output_file=output_path.name,
        )
        for problem in canonicalization_problems
    )
    audit_issues = merge_issues(
        audit_issues,
        audit_guide_output(
            current_output,
            guide,
            context,
            system_map_path,
            output_path.name,
        ),
    )
    corrections_applied = False

    if audit_issues:
        prompt = build_reviewer_validation_prompt(
            guide_json=json.dumps(
                {
                    "wstg_id": guide["wstg_id"],
                    "title": guide["title"],
                    "path": guide["relative_path"],
                    "area": guide["area"],
                    "support_paths": guide.get("support_paths", []),
                },
                indent=2,
            ),
            input_json=json.dumps(
                {
                    "root": str(context["root_path"]),
                    "chunks": input_document.get("chunks", []),
                },
                indent=2,
            ),
            audit_json=json.dumps(audit_issues, indent=2),
            current_output_json=json.dumps(current_output, indent=2),
            evidence_bundle_json=json.dumps(collect_evidence_bundle(current_output), indent=2),
        )
        ai_report = call_ai(prompt)
        normalized_ai_report = normalize_ai_validation_report(
            ai_report,
            guide=guide,
            context=context,
            system_map_path=system_map_path,
            audit_issues=audit_issues,
        )
        corrected_output = normalized_ai_report.get("corrected_output")

        if corrected_output is not None and corrected_output != current_output:
            output_path.write_text(json.dumps(corrected_output, indent=2), encoding="utf-8")
            current_output = corrected_output
            corrections_applied = True
    else:
        normalized_ai_report = {
            "status": "pass",
            "summary": "Validator found no issues.",
            "issues": [],
            "corrected_output": None,
        }

    remaining_issues = audit_guide_output(
        current_output,
        guide,
        context,
        system_map_path,
        output_path.name,
    )
    all_issues = merge_issues(audit_issues, normalized_ai_report["issues"])

    if remaining_issues:
        status = "needs_review"
    elif corrections_applied:
        status = "corrected"
    else:
        status = "pass"

    if status == "pass":
        summary = "Validator found no issues and made no changes."
    elif status == "corrected":
        summary = "Validator corrected the guide output and resolved the deterministic issues."
    elif corrections_applied:
        summary = (
            f"Validator applied corrections, but {len(remaining_issues)} issue(s) still need review."
        )
    else:
        summary = f"Validator found {len(all_issues)} issue(s) that need review."

    return {
        "wstg_id": guide["wstg_id"],
        "output_file": output_path.name,
        "status": status,
        "summary": summary,
        "corrections_applied": corrections_applied,
        "issues": all_issues,
        "remaining_issues": remaining_issues,
    }


def validate_reviewer(input_json_path, system_map_json_path, review_dir):
    """Validate and, if possible, correct WSTG review outputs in place."""
    input_path = Path(input_json_path).resolve()
    review_dir = Path(review_dir).resolve()
    report_path = review_dir / DEFAULT_REPORT_FILE
    index_path = review_dir / DEFAULT_INDEX_FILE
    input_document, input_messages = load_repository_input(input_path)
    context = build_review_context(input_document or {})
    _, system_map_issues = load_system_map_output(system_map_json_path)
    catalog = load_review_guides()
    issues = merge_issues(
        [
            make_issue(wstg_id="", category="input", message=message)
            for message in input_messages
        ],
        [
            make_issue(wstg_id="", category="system_map", message=message)
            for message in system_map_issues
        ],
        [
            make_issue(wstg_id="", category="guides", message=message)
            for message in catalog.get("issues", [])
        ],
    )
    guide_reports = []
    corrected_outputs = []

    for guide in catalog["test_cases"]:
        output_path = review_dir / f"{guide['wstg_id']}.json"
        guide_report = validate_guide_output(
            output_path=output_path,
            guide=guide,
            context=context,
            system_map_path=system_map_json_path,
            input_document=input_document,
        )
        guide_reports.append(guide_report)
        issues = merge_issues(issues, guide_report["issues"])

        if output_path.exists():
            corrected_outputs.append(load_json_file(output_path))

    canonical_index = build_index(
        output_dir=review_dir,
        guide_outputs=corrected_outputs,
        catalog=catalog,
        root_path=context["root_path"],
        system_map_path=system_map_json_path,
    )
    index_corrected = False

    if not index_path.exists():
        issues = merge_issues(
            issues,
            [
                make_issue(
                    wstg_id="",
                    category="index",
                    message="Aggregate index is missing and was rebuilt.",
                    output_file=index_path.name,
                )
            ],
        )
        index_corrected = True
    else:
        try:
            current_index = load_json_file(index_path)
        except Exception as exc:
            issues = merge_issues(
                issues,
                [
                    make_issue(
                        wstg_id="",
                        category="index",
                        message=f"Aggregate index is unreadable and was rebuilt: {exc}",
                        output_file=index_path.name,
                    )
                ],
            )
            current_index = None
            index_corrected = True

        if current_index != canonical_index:
            issues = merge_issues(
                issues,
                [
                    make_issue(
                        wstg_id="",
                        category="index",
                        message="Aggregate index did not match the canonical rebuilt index.",
                        output_file=index_path.name,
                    )
                ],
            )
            index_corrected = True

    if index_corrected:
        index_path.write_text(json.dumps(canonical_index, indent=2), encoding="utf-8")

    remaining_issues = merge_issues(
        [
            issue
            for guide_report in guide_reports
            for issue in guide_report["remaining_issues"]
        ]
    )
    corrections_applied = index_corrected or any(
        guide_report["corrections_applied"] for guide_report in guide_reports
    )

    if remaining_issues or any(
        guide_report["status"] == "needs_review" for guide_report in guide_reports
    ):
        status = "needs_review"
    elif corrections_applied:
        status = "corrected"
    else:
        status = "pass"

    if status == "pass":
        summary = "Validator found no issues and made no changes."
    elif status == "corrected":
        summary = "Validator corrected the review outputs and rebuilt the canonical aggregate index."
    else:
        summary = f"Validator found {len(issues)} issue(s) that need review."

    report = {
        "status": status,
        "summary": summary,
        "corrections_applied": corrections_applied,
        "index_corrected": index_corrected,
        "guide_reports": guide_reports,
        "issues": issues,
        "remaining_issues": remaining_issues,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Validate WSTG review outputs generated by reviewer.py."
    )
    parser.add_argument("input_json", help="Path to the normalized repository input JSON.")
    parser.add_argument("system_map_json", help="Path to the validated system-map output JSON.")
    parser.add_argument("review_dir", help="Path to the review output directory.")
    args = parser.parse_args()
    validate_reviewer(args.input_json, args.system_map_json, args.review_dir)


if __name__ == "__main__":
    main()
