#!/usr/bin/env python3
"""WSTG-guided repository review workers."""

import argparse
import json
import logging
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from mapper import (
    build_chunk_contents,
    call_ai as mapper_call_ai,
    dedupe_evidence,
    load_repository_input,
    make_empty_system_map,
    merge_string_field,
    normalize_path_list,
    normalize_string_list,
    normalize_text,
)
from prompts import (
    build_reviewer_merge_prompt,
    build_reviewer_routing_prompt,
    build_reviewer_subtask_prompt,
)
from wstg_review_guides import load_review_guides, load_support_bundle


CMD = "copilot -p"
FLEET_CMD = "/fleet"
DEFAULT_OUTPUT_DIR = "reviews/wstg"
DEFAULT_INDEX_FILE = "index.json"
DEFAULT_GUIDE_WORKERS = 4
CERTAINTY_ORDER = {
    "suspected": 0,
    "plausible": 1,
    "high-confidence": 2,
}
VALID_REVIEW_DEPTHS = {"initial", "expanded"}
ATTACK_PATH_FIELDS = (
    "entrypoint",
    "controllable_input",
    "control_gap",
    "sensitive_sink_or_boundary",
    "impact",
)
TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}

LOGGER = logging.getLogger(__name__)


def call_ai(prompt: str, cmd=CMD):
    """Call the configured AI backend."""
    return mapper_call_ai(prompt, cmd=cmd)


def resolve_review_cmd():
    """Prefer /fleet for review subtasks when it is available."""
    if Path(FLEET_CMD).exists() and os.access(FLEET_CMD, os.X_OK):
        return FLEET_CMD

    fleet_binary = shutil.which("fleet")
    if fleet_binary:
        return fleet_binary

    return CMD


def determine_review_workers(task_count):
    """Determine reviewer guide parallelism."""
    configured = normalize_text(os.environ.get("REVIEW_MAX_PARALLEL"))

    if configured.isdigit() and int(configured) > 0:
        return max(1, min(int(configured), task_count))

    return max(1, min(DEFAULT_GUIDE_WORKERS, task_count))


def make_gap(summary, chunk_ids, reason):
    """Create a normalized coverage gap."""
    return {
        "summary": normalize_text(summary),
        "chunk_ids": normalize_string_list(chunk_ids),
        "reason": normalize_text(reason),
    }


def make_review_fragment(summary="", candidate_findings=None, rejected_hypotheses=None, coverage_gaps=None):
    """Build a normalized review fragment payload."""
    return {
        "summary": normalize_text(summary),
        "candidate_findings": candidate_findings or [],
        "rejected_hypotheses": rejected_hypotheses or [],
        "coverage_gaps": dedupe_coverage_gaps(coverage_gaps or []),
    }


def build_review_context(document):
    """Build lookup tables from the validated repository input."""
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
        "chunk_by_id": {chunk["id"]: chunk for chunk in chunks},
        "known_chunk_ids": known_chunk_ids,
        "files_by_chunk": files_by_chunk,
        "known_paths": known_paths,
    }


def load_system_map_output(system_map_json_path):
    """Load the validated system-map output to be used as shared context."""
    issues = []
    path = Path(system_map_json_path).resolve()

    if not path.exists():
        issues.append(f"System-map output is missing: {path}")
        return {
            "summary": "",
            "system_map": make_empty_system_map(),
            "coverage_gaps": [],
        }, issues

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(f"System-map output is unreadable: {exc}")
        return {
            "summary": "",
            "system_map": make_empty_system_map(),
            "coverage_gaps": [],
        }, issues

    if not isinstance(payload, dict):
        issues.append("System-map output must be a JSON object.")
        return {
            "summary": "",
            "system_map": make_empty_system_map(),
            "coverage_gaps": [],
        }, issues

    system_map = payload.get("system_map")
    if not isinstance(system_map, dict):
        issues.append("System-map output is missing the system_map object.")
        system_map = make_empty_system_map()

    coverage_gaps = payload.get("coverage_gaps")
    if not isinstance(coverage_gaps, list):
        coverage_gaps = []

    return {
        "summary": normalize_text(payload.get("summary")),
        "system_map": {
            category: list(system_map.get(category, []))
            for category in make_empty_system_map()
        },
        "coverage_gaps": coverage_gaps,
    }, issues


def normalize_note_list(values):
    """Normalize a list of explanatory notes."""
    if isinstance(values, str):
        values = [values]

    return normalize_string_list(values)


def normalize_evidence(raw_evidence, allowed_chunk_ids, allowed_paths, default_chunk_id=None):
    """Normalize evidence references."""
    if not isinstance(raw_evidence, list):
        return []

    normalized = []

    for entry in raw_evidence:
        if not isinstance(entry, dict):
            continue

        chunk_id = normalize_text(entry.get("chunk_id")) or normalize_text(default_chunk_id)
        files = normalize_path_list(entry.get("files", []), allowed_paths)
        rationale = normalize_text(entry.get("rationale"))

        if chunk_id not in allowed_chunk_ids or not files or not rationale:
            continue

        normalized.append(
            {
                "chunk_id": chunk_id,
                "files": files,
                "rationale": rationale,
            }
        )

    return dedupe_evidence(normalized)


def normalize_attack_path(raw_attack_path):
    """Normalize one attack-path object."""
    if not isinstance(raw_attack_path, dict):
        return None, ["attack_path was not an object."]

    attack_path = {
        field_name: normalize_text(raw_attack_path.get(field_name))
        for field_name in ATTACK_PATH_FIELDS
    }
    attack_path["assumptions"] = normalize_note_list(raw_attack_path.get("assumptions", []))
    issues = []

    missing_fields = [
        field_name
        for field_name in ATTACK_PATH_FIELDS
        if not attack_path[field_name]
    ]

    if missing_fields:
        issues.append(
            f"attack_path is missing required field(s): {', '.join(missing_fields)}."
        )

    return attack_path, issues


def normalize_candidate_findings(
    raw_findings,
    allowed_chunk_ids,
    allowed_paths,
    default_chunk_id,
    problems,
):
    """Normalize candidate findings into the fixed schema."""
    if not isinstance(raw_findings, list):
        problems.append("candidate_findings was not a list.")
        return []

    normalized = []

    for finding in raw_findings:
        if not isinstance(finding, dict):
            continue

        title = normalize_text(finding.get("title"))
        certainty = normalize_text(finding.get("certainty")).casefold()
        weakness_summary = normalize_text(finding.get("weakness_summary"))
        attack_path, attack_path_issues = normalize_attack_path(finding.get("attack_path", {}))
        evidence = normalize_evidence(
            finding.get("evidence", []),
            allowed_chunk_ids=allowed_chunk_ids,
            allowed_paths=allowed_paths,
            default_chunk_id=default_chunk_id,
        )
        counter_evidence = normalize_note_list(finding.get("counter_evidence", []))
        remediation_direction = normalize_text(finding.get("remediation_direction"))

        if not title or not weakness_summary:
            problems.append("Dropped candidate finding with missing title or weakness_summary.")
            continue

        if certainty not in CERTAINTY_ORDER:
            problems.append(f"Dropped candidate finding {title} with invalid certainty {certainty!r}.")
            continue

        if attack_path_issues:
            problems.append(f"Dropped candidate finding {title}: {' '.join(attack_path_issues)}")
            continue

        if not evidence:
            problems.append(f"Dropped candidate finding {title} without usable evidence.")
            continue

        if not counter_evidence:
            problems.append(f"Dropped candidate finding {title} without any counter_evidence notes.")
            continue

        if not remediation_direction:
            problems.append(
                f"Dropped candidate finding {title} without remediation_direction."
            )
            continue

        normalized.append(
            {
                "finding_id": normalize_text(finding.get("finding_id")),
                "title": title,
                "certainty": certainty,
                "weakness_summary": weakness_summary,
                "attack_path": attack_path,
                "evidence": evidence,
                "counter_evidence": counter_evidence,
                "remediation_direction": remediation_direction,
            }
        )

    return sorted(
        normalized,
        key=lambda item: (
            item["title"].casefold(),
            -CERTAINTY_ORDER[item["certainty"]],
        ),
    )


def normalize_rejected_hypotheses(
    raw_hypotheses,
    allowed_chunk_ids,
    allowed_paths,
    default_chunk_id,
    problems,
):
    """Normalize rejected hypotheses into the fixed schema."""
    if not isinstance(raw_hypotheses, list):
        problems.append("rejected_hypotheses was not a list.")
        return []

    normalized = []

    for hypothesis in raw_hypotheses:
        if not isinstance(hypothesis, dict):
            continue

        title = normalize_text(hypothesis.get("title"))
        reason = normalize_text(hypothesis.get("reason"))
        evidence = normalize_evidence(
            hypothesis.get("evidence", []),
            allowed_chunk_ids=allowed_chunk_ids,
            allowed_paths=allowed_paths,
            default_chunk_id=default_chunk_id,
        )

        if not title or not reason:
            problems.append("Dropped rejected hypothesis with missing title or reason.")
            continue

        if not evidence:
            problems.append(f"Dropped rejected hypothesis {title} without usable evidence.")
            continue

        normalized.append(
            {
                "title": title,
                "reason": reason,
                "evidence": evidence,
            }
        )

    return sorted(normalized, key=lambda item: item["title"].casefold())


def dedupe_coverage_gaps(coverage_gaps):
    """Deduplicate coverage gaps with stable ordering."""
    deduped = []
    seen = set()

    for gap in coverage_gaps:
        summary = normalize_text(gap.get("summary"))
        reason = normalize_text(gap.get("reason"))
        chunk_ids = tuple(normalize_string_list(gap.get("chunk_ids", [])))
        key = (summary, reason, chunk_ids)

        if not summary or not reason or not chunk_ids or key in seen:
            continue

        seen.add(key)
        deduped.append(
            {
                "summary": summary,
                "chunk_ids": list(chunk_ids),
                "reason": reason,
            }
        )

    return sorted(
        deduped,
        key=lambda gap: (
            gap["summary"].casefold(),
            gap["reason"].casefold(),
            tuple(chunk_id.casefold() for chunk_id in gap["chunk_ids"]),
        ),
    )


def normalize_review_coverage_gaps(raw_gaps, allowed_chunk_ids, fallback_chunk_ids):
    """Normalize coverage gaps returned by AI."""
    if not isinstance(raw_gaps, list):
        return []

    normalized = []

    for gap in raw_gaps:
        if not isinstance(gap, dict):
            continue

        summary = normalize_text(gap.get("summary"))
        reason = normalize_text(gap.get("reason"))
        chunk_ids = normalize_string_list(gap.get("chunk_ids", []))

        if not chunk_ids:
            chunk_ids = normalize_string_list(fallback_chunk_ids)

        filtered_chunk_ids = [
            chunk_id for chunk_id in chunk_ids if chunk_id in allowed_chunk_ids
        ]

        if not summary or not reason or not filtered_chunk_ids:
            continue

        normalized.append(
            {
                "summary": summary,
                "chunk_ids": filtered_chunk_ids,
                "reason": reason,
            }
        )

    return dedupe_coverage_gaps(normalized)


def normalize_ai_review_result(
    raw_result,
    allowed_chunk_ids,
    allowed_paths,
    fallback_chunk_ids=None,
    default_chunk_id=None,
):
    """Normalize an AI-produced review result or fragment."""
    problems = []
    summary = ""
    candidate_findings = []
    rejected_hypotheses = []
    coverage_gaps = []

    if not isinstance(raw_result, dict):
        problems.append("AI did not return a JSON object.")
        return make_review_fragment(), problems

    summary = normalize_text(raw_result.get("summary"))
    candidate_findings = normalize_candidate_findings(
        raw_result.get("candidate_findings", []),
        allowed_chunk_ids=allowed_chunk_ids,
        allowed_paths=allowed_paths,
        default_chunk_id=default_chunk_id,
        problems=problems,
    )
    rejected_hypotheses = normalize_rejected_hypotheses(
        raw_result.get("rejected_hypotheses", []),
        allowed_chunk_ids=allowed_chunk_ids,
        allowed_paths=allowed_paths,
        default_chunk_id=default_chunk_id,
        problems=problems,
    )
    coverage_gaps = normalize_review_coverage_gaps(
        raw_result.get("coverage_gaps", []),
        allowed_chunk_ids=allowed_chunk_ids,
        fallback_chunk_ids=fallback_chunk_ids or [],
    )

    return make_review_fragment(
        summary=summary,
        candidate_findings=candidate_findings,
        rejected_hypotheses=rejected_hypotheses,
        coverage_gaps=coverage_gaps,
    ), problems


def merge_attack_paths(current_attack_path, incoming_attack_path):
    """Merge two attack paths conservatively."""
    merged = {
        field_name: merge_string_field(
            current_attack_path.get(field_name, ""),
            incoming_attack_path.get(field_name, ""),
        )
        for field_name in ATTACK_PATH_FIELDS
    }
    merged["assumptions"] = normalize_string_list(
        list(current_attack_path.get("assumptions", []))
        + list(incoming_attack_path.get("assumptions", []))
    )
    return merged


def pick_stronger_certainty(current_value, incoming_value):
    """Prefer the stronger certainty classification."""
    if CERTAINTY_ORDER.get(incoming_value, -1) > CERTAINTY_ORDER.get(current_value, -1):
        return incoming_value
    return current_value


def merge_findings(current_finding, incoming_finding):
    """Merge duplicate candidate findings."""
    return {
        "finding_id": current_finding.get("finding_id", ""),
        "title": current_finding.get("title", ""),
        "certainty": pick_stronger_certainty(
            current_finding.get("certainty", "suspected"),
            incoming_finding.get("certainty", "suspected"),
        ),
        "weakness_summary": merge_string_field(
            current_finding.get("weakness_summary", ""),
            incoming_finding.get("weakness_summary", ""),
        ),
        "attack_path": merge_attack_paths(
            current_finding.get("attack_path", {}),
            incoming_finding.get("attack_path", {}),
        ),
        "evidence": dedupe_evidence(
            current_finding.get("evidence", []) + incoming_finding.get("evidence", [])
        ),
        "counter_evidence": normalize_string_list(
            list(current_finding.get("counter_evidence", []))
            + list(incoming_finding.get("counter_evidence", []))
        ),
        "remediation_direction": merge_string_field(
            current_finding.get("remediation_direction", ""),
            incoming_finding.get("remediation_direction", ""),
        ),
    }


def merge_rejected_hypothesis(current_hypothesis, incoming_hypothesis):
    """Merge duplicate rejected hypotheses."""
    return {
        "title": current_hypothesis.get("title", ""),
        "reason": merge_string_field(
            current_hypothesis.get("reason", ""),
            incoming_hypothesis.get("reason", ""),
        ),
        "evidence": dedupe_evidence(
            current_hypothesis.get("evidence", [])
            + incoming_hypothesis.get("evidence", [])
        ),
    }


def finding_key(finding):
    """Build a conservative dedupe key for candidate findings."""
    primary_files = ()

    if finding.get("evidence"):
        primary_files = tuple(finding["evidence"][0].get("files", []))

    return (
        normalize_text(finding.get("title")).casefold(),
        normalize_text(
            finding.get("attack_path", {}).get("control_gap")
        ).casefold(),
        primary_files,
    )


def rejected_hypothesis_key(hypothesis):
    """Build a conservative dedupe key for rejected hypotheses."""
    return (
        normalize_text(hypothesis.get("title")).casefold(),
        normalize_text(hypothesis.get("reason")).casefold(),
    )


def merge_review_fragments(fragments):
    """Deterministically merge chunk-level review fragments."""
    summary = ""
    findings_by_key = {}
    hypotheses_by_key = {}
    coverage_gaps = []

    for fragment in fragments:
        summary = merge_string_field(summary, fragment.get("summary", ""))
        coverage_gaps.extend(fragment.get("coverage_gaps", []))

        for finding in fragment.get("candidate_findings", []):
            key = finding_key(finding)

            if key in findings_by_key:
                findings_by_key[key] = merge_findings(findings_by_key[key], finding)
            else:
                findings_by_key[key] = finding

        for hypothesis in fragment.get("rejected_hypotheses", []):
            key = rejected_hypothesis_key(hypothesis)

            if key in hypotheses_by_key:
                hypotheses_by_key[key] = merge_rejected_hypothesis(
                    hypotheses_by_key[key],
                    hypothesis,
                )
            else:
                hypotheses_by_key[key] = hypothesis

    return make_review_fragment(
        summary=summary,
        candidate_findings=sorted(
            findings_by_key.values(),
            key=lambda item: (
                item["title"].casefold(),
                -CERTAINTY_ORDER[item["certainty"]],
            ),
        ),
        rejected_hypotheses=sorted(
            hypotheses_by_key.values(),
            key=lambda item: item["title"].casefold(),
        ),
        coverage_gaps=dedupe_coverage_gaps(coverage_gaps),
    )


def assign_finding_ids(wstg_id, findings):
    """Assign deterministic finding ids within a guide output."""
    ordered = sorted(
        findings,
        key=lambda item: (
            item["title"].casefold(),
            -CERTAINTY_ORDER[item["certainty"]],
            tuple(item["evidence"][0]["files"]) if item.get("evidence") else (),
        ),
    )
    normalized = []

    for index, finding in enumerate(ordered, 1):
        finding_copy = dict(finding)
        finding_copy["finding_id"] = f"{wstg_id}-F{index:03d}"
        normalized.append(finding_copy)

    return normalized


def build_guide_summary(candidate_findings, rejected_hypotheses, coverage_gaps, problems, synthesized_summary=""):
    """Build a top-level guide summary string."""
    if problems:
        return (
            f"Guide review completed with {len(problems)} issue(s), "
            f"{len(candidate_findings)} candidate finding(s), and "
            f"{len(coverage_gaps)} coverage gap(s)."
        )

    if synthesized_summary:
        return synthesized_summary

    if candidate_findings:
        return (
            f"Guide review produced {len(candidate_findings)} candidate finding(s), "
            f"{len(rejected_hypotheses)} rejected hypothesis record(s), and "
            f"{len(coverage_gaps)} coverage gap(s)."
        )

    if coverage_gaps:
        return (
            f"Guide review found no candidate findings and recorded {len(coverage_gaps)} "
            f"coverage gap(s)."
        )

    return "Guide review completed with no candidate findings."


def collect_raw_chunk_ids(raw_output, known_chunk_ids):
    """Collect chunk ids referenced anywhere in a raw review output."""
    chunk_ids = []

    if not isinstance(raw_output, dict):
        return chunk_ids

    for finding in raw_output.get("candidate_findings", []):
        if not isinstance(finding, dict):
            continue

        for evidence in finding.get("evidence", []):
            if not isinstance(evidence, dict):
                continue
            chunk_id = normalize_text(evidence.get("chunk_id"))
            if chunk_id in known_chunk_ids:
                chunk_ids.append(chunk_id)

    for hypothesis in raw_output.get("rejected_hypotheses", []):
        if not isinstance(hypothesis, dict):
            continue

        for evidence in hypothesis.get("evidence", []):
            if not isinstance(evidence, dict):
                continue
            chunk_id = normalize_text(evidence.get("chunk_id"))
            if chunk_id in known_chunk_ids:
                chunk_ids.append(chunk_id)

    for gap in raw_output.get("coverage_gaps", []):
        if not isinstance(gap, dict):
            continue

        for chunk_id in gap.get("chunk_ids", []):
            normalized_chunk_id = normalize_text(chunk_id)
            if normalized_chunk_id in known_chunk_ids:
                chunk_ids.append(normalized_chunk_id)

    return normalize_string_list(chunk_ids)


def canonicalize_chunk_ids(values, known_chunk_ids):
    """Normalize a chunk-id list against the known chunk-id set."""
    return [
        chunk_id
        for chunk_id in normalize_string_list(values)
        if chunk_id in known_chunk_ids
    ]


def canonicalize_guide_output(
    raw_output,
    guide,
    context,
    system_map_path,
    default_routed_chunk_ids=None,
    default_reviewed_chunk_ids=None,
    default_review_depth="initial",
):
    """Canonicalize a guide output into the stable on-disk schema."""
    if not isinstance(raw_output, dict):
        raw_output = {}

    raw_input = raw_output.get("input", {}) if isinstance(raw_output.get("input"), dict) else {}
    evidence_chunk_ids = collect_raw_chunk_ids(raw_output, context["known_chunk_ids"])
    routed_chunk_ids = canonicalize_chunk_ids(
        raw_input.get("routed_chunk_ids", []),
        context["known_chunk_ids"],
    )
    reviewed_chunk_ids = canonicalize_chunk_ids(
        raw_input.get("reviewed_chunk_ids", []),
        context["known_chunk_ids"],
    )

    if not routed_chunk_ids:
        routed_chunk_ids = canonicalize_chunk_ids(
            default_routed_chunk_ids or evidence_chunk_ids,
            context["known_chunk_ids"],
        )

    if not reviewed_chunk_ids:
        reviewed_chunk_ids = canonicalize_chunk_ids(
            default_reviewed_chunk_ids or routed_chunk_ids or evidence_chunk_ids,
            context["known_chunk_ids"],
        )

    if not routed_chunk_ids and reviewed_chunk_ids:
        routed_chunk_ids = list(reviewed_chunk_ids)

    if not reviewed_chunk_ids and routed_chunk_ids:
        reviewed_chunk_ids = list(routed_chunk_ids)

    review_depth = normalize_text(raw_input.get("review_depth")) or default_review_depth
    if review_depth not in VALID_REVIEW_DEPTHS:
        review_depth = "expanded" if reviewed_chunk_ids != routed_chunk_ids else "initial"

    allowed_chunk_ids = set(reviewed_chunk_ids or routed_chunk_ids or context["known_chunk_ids"])
    allowed_paths = {
        path
        for chunk_id in allowed_chunk_ids
        for path in context["files_by_chunk"].get(chunk_id, set())
    }

    if not allowed_paths:
        allowed_chunk_ids = set(context["known_chunk_ids"])
        allowed_paths = set(context["known_paths"])

    normalized_result, problems = normalize_ai_review_result(
        raw_output,
        allowed_chunk_ids=allowed_chunk_ids,
        allowed_paths=allowed_paths,
        fallback_chunk_ids=reviewed_chunk_ids or routed_chunk_ids or sorted(context["known_chunk_ids"]),
    )
    candidate_findings = assign_finding_ids(
        guide["wstg_id"],
        normalized_result["candidate_findings"],
    )
    summary = build_guide_summary(
        candidate_findings=candidate_findings,
        rejected_hypotheses=normalized_result["rejected_hypotheses"],
        coverage_gaps=normalized_result["coverage_gaps"],
        problems=problems,
        synthesized_summary=normalized_result["summary"],
    )
    status = normalize_text(raw_output.get("status"))

    if status not in {"pass", "corrected", "needs_review"}:
        status = "needs_review" if problems else "pass"

    if problems:
        status = "needs_review"

    payload = {
        "status": status,
        "summary": summary,
        "guide": {
            "wstg_id": guide["wstg_id"],
            "title": guide["title"],
            "path": guide["relative_path"],
            "area": guide["area"],
            "support_paths": list(guide.get("support_paths", [])),
        },
        "input": {
            "root": str(context["root_path"]) if context["root_path"] else "",
            "system_map_path": str(Path(system_map_path).resolve()),
            "routed_chunk_ids": list(routed_chunk_ids),
            "reviewed_chunk_ids": list(reviewed_chunk_ids),
            "review_depth": review_depth,
        },
        "candidate_findings": candidate_findings,
        "rejected_hypotheses": normalized_result["rejected_hypotheses"],
        "coverage_gaps": normalized_result["coverage_gaps"],
    }
    payload["metrics"] = build_metrics(payload)
    return payload, problems


def build_metrics(payload):
    """Build deterministic metrics for one guide output."""
    routed_chunk_ids = payload.get("input", {}).get("routed_chunk_ids", [])
    reviewed_chunk_ids = payload.get("input", {}).get("reviewed_chunk_ids", [])

    return {
        "routed_chunk_count": len(routed_chunk_ids),
        "reviewed_chunk_count": len(reviewed_chunk_ids),
        "candidate_finding_count": len(payload.get("candidate_findings", [])),
        "rejected_hypothesis_count": len(payload.get("rejected_hypotheses", [])),
        "coverage_gap_count": len(payload.get("coverage_gaps", [])),
        "expansion_performed": payload.get("input", {}).get("review_depth") == "expanded",
    }


def filter_system_map_output(system_map_output, chunk_ids=None):
    """Filter system-map items to those supported by the selected chunks."""
    if not chunk_ids:
        return {
            "summary": system_map_output.get("summary", ""),
            "system_map": system_map_output.get("system_map", make_empty_system_map()),
            "coverage_gaps": system_map_output.get("coverage_gaps", []),
        }

    selected_chunk_ids = set(chunk_ids)
    filtered_map = {}

    for category, items in system_map_output.get("system_map", {}).items():
        filtered_items = []

        for item in items:
            if not isinstance(item, dict):
                continue

            evidence = item.get("evidence", [])
            if any(
                normalize_text(evidence_item.get("chunk_id")) in selected_chunk_ids
                for evidence_item in evidence
                if isinstance(evidence_item, dict)
            ):
                filtered_items.append(item)

        filtered_map[category] = filtered_items

    filtered_gaps = []
    for gap in system_map_output.get("coverage_gaps", []):
        if not isinstance(gap, dict):
            continue

        gap_chunk_ids = normalize_string_list(gap.get("chunk_ids", []))
        if not gap_chunk_ids or selected_chunk_ids.intersection(gap_chunk_ids):
            filtered_gaps.append(gap)

    return {
        "summary": system_map_output.get("summary", ""),
        "system_map": filtered_map,
        "coverage_gaps": filtered_gaps,
    }


def tokenize(text):
    """Tokenize free text into lowercase keywords."""
    return {
        token
        for token in TOKEN_PATTERN.findall(normalize_text(text).casefold())
        if token and token not in STOP_WORDS
    }


def lexical_score(guide_tokens, chunk):
    """Compute a simple lexical overlap score for routing fallback."""
    chunk_tokens = tokenize(
        " ".join(
            [
                chunk.get("id", ""),
                chunk.get("name", ""),
                chunk.get("reason", ""),
                " ".join(file_info.get("path", "") for file_info in chunk.get("files", [])),
            ]
        )
    )
    return len(guide_tokens.intersection(chunk_tokens))


def fallback_rank_chunks(guide, chunks):
    """Build a deterministic lexical ranking for chunk routing."""
    guide_tokens = tokenize(
        " ".join(
            [
                guide.get("wstg_id", ""),
                guide.get("title", ""),
                guide.get("markdown", ""),
                " ".join(guide.get("support_paths", [])),
            ]
        )
    )
    ranked = []

    for chunk in chunks:
        score = lexical_score(guide_tokens, chunk)

        if score >= 6:
            relevance = "high"
        elif score >= 2:
            relevance = "medium"
        else:
            relevance = "low"

        rationale = "lexical overlap fallback" if score else "deterministic fallback ordering"
        ranked.append(
            {
                "chunk_id": chunk["id"],
                "relevance": relevance,
                "rationale": rationale,
                "score": score,
            }
        )

    ranked.sort(
        key=lambda item: (
            -item["score"],
            item["chunk_id"].casefold(),
        )
    )

    return [
        {
            "chunk_id": item["chunk_id"],
            "relevance": item["relevance"],
            "rationale": item["rationale"],
        }
        for item in ranked
    ]


def normalize_routing_result(raw_result, allowed_chunk_ids):
    """Normalize the AI routing response."""
    problems = []
    summary = ""
    ranked_chunks = []
    seen = set()

    if not isinstance(raw_result, dict):
        problems.append("AI router did not return a JSON object.")
        return {"summary": summary, "ranked_chunks": ranked_chunks}, problems

    summary = normalize_text(raw_result.get("summary"))

    for item in raw_result.get("ranked_chunks", []):
        if not isinstance(item, dict):
            continue

        chunk_id = normalize_text(item.get("chunk_id"))
        relevance = normalize_text(item.get("relevance")).casefold()
        rationale = normalize_text(item.get("rationale"))

        if chunk_id not in allowed_chunk_ids or chunk_id in seen:
            continue

        if relevance not in {"high", "medium", "low"}:
            relevance = "low"

        if not rationale:
            rationale = "AI router did not provide a rationale."

        seen.add(chunk_id)
        ranked_chunks.append(
            {
                "chunk_id": chunk_id,
                "relevance": relevance,
                "rationale": rationale,
            }
        )

    return {
        "summary": summary,
        "ranked_chunks": ranked_chunks,
    }, problems


def select_routed_chunks(ranked_chunks):
    """Select the initial chunk set from the ranked routing list."""
    high = [item["chunk_id"] for item in ranked_chunks if item["relevance"] == "high"]
    medium = [item["chunk_id"] for item in ranked_chunks if item["relevance"] == "medium"]

    if high or medium:
        selected = high[:8]

        if len(selected) < 8:
            selected.extend(medium[: min(5, 8 - len(selected))])

        return normalize_string_list(selected)

    return normalize_string_list(
        [item["chunk_id"] for item in ranked_chunks[:4]]
    )


def route_guide_chunks(guide, support_markdown, system_map_output, chunks, ai_cmd):
    """Route one guide to the most relevant chunks."""
    chunk_manifest = [
        {
            "id": chunk["id"],
            "name": chunk["name"],
            "reason": chunk["reason"],
            "total_lines": chunk["total_lines"],
            "file_count": chunk["file_count"],
            "files": chunk["files"],
        }
        for chunk in chunks
    ]
    fallback_ranked = fallback_rank_chunks(guide, chunks)
    prompt = build_reviewer_routing_prompt(
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
        guide_markdown=guide["markdown"],
        support_markdown=support_markdown,
        system_map_json=json.dumps(filter_system_map_output(system_map_output), indent=2),
        chunk_manifest_json=json.dumps(chunk_manifest, indent=2),
    )
    raw_result = call_ai(prompt, cmd=ai_cmd)
    normalized_result, problems = normalize_routing_result(
        raw_result,
        allowed_chunk_ids={chunk["id"] for chunk in chunks},
    )
    ranked_chunks = list(normalized_result["ranked_chunks"])
    seen = {item["chunk_id"] for item in ranked_chunks}

    for item in fallback_ranked:
        if item["chunk_id"] in seen:
            continue
        ranked_chunks.append(item)

    selected_chunk_ids = select_routed_chunks(ranked_chunks)

    if not selected_chunk_ids:
        selected_chunk_ids = normalize_string_list(
            [item["chunk_id"] for item in fallback_ranked[:4]]
        )

    return {
        "summary": normalized_result["summary"],
        "ranked_chunks": ranked_chunks,
        "selected_chunk_ids": selected_chunk_ids,
        "problems": problems,
    }


def build_chunk_materials(root_path, chunks):
    """Read chunk contents once so guide workers can reuse them."""
    materials = {}
    problems = []

    for chunk in chunks:
        chunk_contents, readable_paths, read_issues = build_chunk_contents(root_path, chunk)
        problems.extend(read_issues)
        materials[chunk["id"]] = {
            "chunk": chunk,
            "chunk_contents": chunk_contents,
            "readable_paths": readable_paths,
            "issues": read_issues,
        }

    return materials, problems


def review_chunk_for_guide(guide, support_markdown, system_map_output, material, ai_cmd):
    """Review one chunk under one guide."""
    chunk = material["chunk"]
    prompt = build_reviewer_subtask_prompt(
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
        guide_markdown=guide["markdown"],
        support_markdown=support_markdown,
        system_map_json=json.dumps(
            filter_system_map_output(system_map_output, [chunk["id"]]),
            indent=2,
        ),
        chunk_json=json.dumps(chunk, indent=2),
        chunk_contents=material["chunk_contents"],
    )
    raw_result = call_ai(prompt, cmd=ai_cmd)
    normalized_result, problems = normalize_ai_review_result(
        raw_result=raw_result,
        allowed_chunk_ids={chunk["id"]},
        allowed_paths=set(material["readable_paths"]),
        fallback_chunk_ids=[chunk["id"]],
        default_chunk_id=chunk["id"],
    )
    coverage_gaps = list(normalized_result["coverage_gaps"])

    if material["issues"]:
        coverage_gaps.append(
            make_gap(
                f"Chunk {chunk['id']} had unreadable files during guide review.",
                [chunk["id"]],
                "input-unreadable",
            )
        )

    if problems:
        coverage_gaps.append(
            make_gap(
                f"Guide worker output for chunk {chunk['id']} was incomplete and was normalized conservatively.",
                [chunk["id"]],
                "ai-incomplete-output",
            )
        )

    return make_review_fragment(
        summary=normalized_result["summary"],
        candidate_findings=normalized_result["candidate_findings"],
        rejected_hypotheses=normalized_result["rejected_hypotheses"],
        coverage_gaps=coverage_gaps,
    ), problems


def needs_broader_context(coverage_gaps):
    """Return whether any coverage gap requests a broader expansion pass."""
    for gap in coverage_gaps:
        reason = normalize_text(gap.get("reason")).casefold()
        if reason == "broader-repository-context":
            return True

    return False


def synthesize_guide_review(guide, merged_fragment, reviewed_chunk_ids, context, ai_cmd):
    """Run the final synthesis pass over a deterministic merged guide fragment."""
    allowed_chunk_ids = set(reviewed_chunk_ids)
    allowed_paths = {
        path
        for chunk_id in reviewed_chunk_ids
        for path in context["files_by_chunk"].get(chunk_id, set())
    }
    prompt = build_reviewer_merge_prompt(
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
        merged_fragment_json=json.dumps(merged_fragment, indent=2),
    )
    raw_result = call_ai(prompt, cmd=ai_cmd)
    normalized_result, problems = normalize_ai_review_result(
        raw_result=raw_result,
        allowed_chunk_ids=allowed_chunk_ids,
        allowed_paths=allowed_paths,
        fallback_chunk_ids=reviewed_chunk_ids,
    )

    if problems:
        return merged_fragment, problems

    return normalized_result, []


def review_guide(guide, catalog, context, system_map_output, chunk_materials, system_map_path, ai_cmd):
    """Run the full review flow for one actionable guide."""
    support_records, support_markdown = load_support_bundle(catalog, guide)
    routing = route_guide_chunks(
        guide,
        support_markdown=support_markdown,
        system_map_output=system_map_output,
        chunks=context["chunks"],
        ai_cmd=ai_cmd,
    )
    problems = list(routing["problems"])
    routed_chunk_ids = list(routing["selected_chunk_ids"])
    reviewed_chunk_ids = list(routed_chunk_ids)
    fragments = []

    for chunk_id in reviewed_chunk_ids:
        fragment, fragment_problems = review_chunk_for_guide(
            guide,
            support_markdown=support_markdown,
            system_map_output=system_map_output,
            material=chunk_materials[chunk_id],
            ai_cmd=ai_cmd,
        )
        fragments.append(fragment)
        problems.extend(fragment_problems)

    merged_fragment = merge_review_fragments(fragments)
    review_depth = "initial"

    if needs_broader_context(merged_fragment["coverage_gaps"]):
        remaining_chunk_ids = [
            item["chunk_id"]
            for item in routing["ranked_chunks"]
            if item["chunk_id"] not in reviewed_chunk_ids
        ][:4]

        if remaining_chunk_ids:
            review_depth = "expanded"
            reviewed_chunk_ids.extend(remaining_chunk_ids)

            for chunk_id in remaining_chunk_ids:
                fragment, fragment_problems = review_chunk_for_guide(
                    guide,
                    support_markdown=support_markdown,
                    system_map_output=system_map_output,
                    material=chunk_materials[chunk_id],
                    ai_cmd=ai_cmd,
                )
                fragments.append(fragment)
                problems.extend(fragment_problems)

            merged_fragment = merge_review_fragments(fragments)

    synthesized_result, synthesis_problems = synthesize_guide_review(
        guide,
        merged_fragment=merged_fragment,
        reviewed_chunk_ids=reviewed_chunk_ids,
        context=context,
        ai_cmd=ai_cmd,
    )
    problems.extend(synthesis_problems)

    guide_output, canonicalization_problems = canonicalize_guide_output(
        raw_output={
            "status": "needs_review" if problems else "pass",
            "summary": synthesized_result["summary"],
            "input": {
                "routed_chunk_ids": routed_chunk_ids,
                "reviewed_chunk_ids": reviewed_chunk_ids,
                "review_depth": review_depth,
            },
            "candidate_findings": synthesized_result["candidate_findings"],
            "rejected_hypotheses": synthesized_result["rejected_hypotheses"],
            "coverage_gaps": synthesized_result["coverage_gaps"],
        },
        guide=guide,
        context=context,
        system_map_path=system_map_path,
        default_routed_chunk_ids=routed_chunk_ids,
        default_reviewed_chunk_ids=reviewed_chunk_ids,
        default_review_depth=review_depth,
    )
    problems.extend(canonicalization_problems)

    if problems:
        guide_output["status"] = "needs_review"
        guide_output["summary"] = build_guide_summary(
            candidate_findings=guide_output["candidate_findings"],
            rejected_hypotheses=guide_output["rejected_hypotheses"],
            coverage_gaps=guide_output["coverage_gaps"],
            problems=problems,
        )
        guide_output["metrics"] = build_metrics(guide_output)

    guide_output["guide"]["support_paths"] = [
        support_record["relative_path"] for support_record in support_records
    ]
    return guide_output, problems


def write_guide_output(output_dir, payload):
    """Write one per-guide output file."""
    outpath = Path(output_dir) / f"{payload['guide']['wstg_id']}.json"
    outpath.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return outpath


def build_index(output_dir, guide_outputs, catalog, root_path, system_map_path):
    """Build the aggregate guide-review index."""
    output_dir = Path(output_dir).resolve()
    root_path = Path(root_path).resolve() if root_path else output_dir.parent.resolve()
    guide_runs = []
    finding_catalog = []
    support_usage = {}
    unique_reviewed_chunks = set()
    unique_routed_chunks = set()
    guides_with_gaps = 0
    total_coverage_gaps = 0

    for output in sorted(guide_outputs, key=lambda item: item["guide"]["wstg_id"].casefold()):
        wstg_id = output["guide"]["wstg_id"]
        output_file = output_dir / f"{wstg_id}.json"
        relative_output = str(output_file.relative_to(root_path))
        reviewed_chunk_ids = list(output["input"]["reviewed_chunk_ids"])
        routed_chunk_ids = list(output["input"]["routed_chunk_ids"])
        guide_runs.append(
            {
                "wstg_id": wstg_id,
                "title": output["guide"]["title"],
                "path": output["guide"]["path"],
                "output_file": relative_output,
                "status": output["status"],
                "candidate_finding_count": len(output["candidate_findings"]),
                "rejected_hypothesis_count": len(output["rejected_hypotheses"]),
                "coverage_gap_count": len(output["coverage_gaps"]),
                "routed_chunk_ids": routed_chunk_ids,
                "reviewed_chunk_ids": reviewed_chunk_ids,
                "support_paths": list(output["guide"].get("support_paths", [])),
                "alias_paths": list(
                    sorted(
                        set(output["guide"].get("support_paths", [])).intersection(
                            {
                                item["alias_path"]
                                for item in catalog.get("alias_resolution", [])
                            }
                        )
                    )
                ),
            }
        )

        unique_reviewed_chunks.update(reviewed_chunk_ids)
        unique_routed_chunks.update(routed_chunk_ids)
        total_coverage_gaps += len(output["coverage_gaps"])

        if output["coverage_gaps"]:
            guides_with_gaps += 1

        for support_path in output["guide"].get("support_paths", []):
            support_usage.setdefault(support_path, set()).add(wstg_id)

        for finding in output["candidate_findings"]:
            finding_catalog.append(
                {
                    "finding_id": finding["finding_id"],
                    "wstg_id": wstg_id,
                    "title": finding["title"],
                    "certainty": finding["certainty"],
                    "output_file": relative_output,
                }
            )

    issues = list(catalog.get("issues", []))
    status = "needs_review" if issues or any(
        output["status"] == "needs_review" for output in guide_outputs
    ) else "pass"
    summary = (
        f"WSTG review completed for {len(guide_outputs)} guide(s) with "
        f"{len(finding_catalog)} candidate finding(s)."
    )

    if issues:
        summary = (
            f"{summary[:-1]} and {len(issues)} guide-catalog issue(s) that need review."
        )

    return {
        "status": status,
        "summary": summary,
        "input": {
            "root": str(root_path),
            "system_map_path": str(Path(system_map_path).resolve()),
            "guide_count": len(guide_outputs),
            "review_output_dir": str(output_dir),
        },
        "guide_runs": guide_runs,
        "finding_catalog": sorted(
            finding_catalog,
            key=lambda item: (
                item["wstg_id"].casefold(),
                item["title"].casefold(),
            ),
        ),
        "coverage_totals": {
            "guide_count_with_gaps": guides_with_gaps,
            "coverage_gap_count": total_coverage_gaps,
            "unique_reviewed_chunk_count": len(unique_reviewed_chunks),
            "unique_routed_chunk_count": len(unique_routed_chunks),
        },
        "support_doc_usage": [
            {
                "path": support_path,
                "used_by_wstg_ids": sorted(used_by),
            }
            for support_path, used_by in sorted(support_usage.items())
        ],
        "alias_resolution": list(catalog.get("alias_resolution", [])),
    }


def write_index(output_dir, index_payload):
    """Write the aggregate review index."""
    outpath = Path(output_dir) / DEFAULT_INDEX_FILE
    outpath.write_text(json.dumps(index_payload, indent=2), encoding="utf-8")
    return outpath


def run_reviewer(input_json_path, system_map_json_path, output_dir=None):
    """Run the WSTG-guided review stage."""
    input_path = Path(input_json_path).resolve()
    document, input_issues = load_repository_input(input_path)
    context = build_review_context(document or {})
    system_map_output, system_map_issues = load_system_map_output(system_map_json_path)
    catalog = load_review_guides()

    if context["root_path"] is None or not context["chunks"]:
        raise ValueError(
            "Reviewer input did not contain a resolved repository root and non-empty chunk list."
        )

    review_output_dir = (
        Path(output_dir).resolve()
        if output_dir
        else Path(context["root_path"]).resolve() / DEFAULT_OUTPUT_DIR
    )
    review_output_dir.mkdir(parents=True, exist_ok=True)

    ai_cmd = resolve_review_cmd()
    chunk_materials, material_issues = build_chunk_materials(context["root_path"], context["chunks"])
    shared_issues = list(input_issues) + list(system_map_issues) + list(material_issues)
    worker_count = determine_review_workers(len(catalog["test_cases"]))
    outputs = []

    def task(guide):
        guide_output, guide_problems = review_guide(
            guide=guide,
            catalog=catalog,
            context=context,
            system_map_output=system_map_output,
            chunk_materials=chunk_materials,
            system_map_path=system_map_json_path,
            ai_cmd=ai_cmd,
        )

        if shared_issues:
            guide_output["status"] = "needs_review"
            guide_output["summary"] = build_guide_summary(
                candidate_findings=guide_output["candidate_findings"],
                rejected_hypotheses=guide_output["rejected_hypotheses"],
                coverage_gaps=guide_output["coverage_gaps"],
                problems=guide_problems + shared_issues,
            )
            guide_output["metrics"] = build_metrics(guide_output)

        return guide_output

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_guide = {
            executor.submit(task, guide): guide
            for guide in catalog["test_cases"]
        }

        for future in as_completed(future_to_guide):
            guide = future_to_guide[future]

            try:
                guide_output = future.result()
            except Exception as exc:
                LOGGER.exception("Guide review failed for %s", guide["wstg_id"])
                guide_output, _ = canonicalize_guide_output(
                    raw_output={
                        "status": "needs_review",
                        "coverage_gaps": [
                            make_gap(
                                f"Guide worker failed before producing output: {exc}",
                                [],
                                "ai-incomplete-output",
                            )
                        ],
                    },
                    guide=guide,
                    context=context,
                    system_map_path=system_map_json_path,
                )

            outputs.append(guide_output)
            write_guide_output(review_output_dir, guide_output)

    index_payload = build_index(
        output_dir=review_output_dir,
        guide_outputs=outputs,
        catalog=catalog,
        root_path=context["root_path"],
        system_map_path=system_map_json_path,
    )
    write_index(review_output_dir, index_payload)
    return index_payload


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Run WSTG-guided review workers from a repository input and system map."
    )
    parser.add_argument("input_json", help="Path to the normalized repository input JSON.")
    parser.add_argument("system_map_json", help="Path to the validated system-map output JSON.")
    parser.add_argument(
        "output_dir",
        nargs="?",
        help="Optional explicit output directory. Defaults to <repo>/reviews/wstg.",
    )
    args = parser.parse_args()
    run_reviewer(args.input_json, args.system_map_json, args.output_dir)


if __name__ == "__main__":
    main()
