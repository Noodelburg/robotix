#!/usr/bin/env python3
"""Standalone repository mapper."""

import argparse
import json
import logging
import re
import shlex
import subprocess
from pathlib import Path

from prompts import (
    build_mapper_chunk_prompt,
    build_mapper_merge_prompt,
)


CMD = "copilot -p"
DEFAULT_OUTPUT_FILE = "repository-understanding.json"
CATEGORIES = (
    "entrypoints",
    "trust_boundaries",
    "identity_and_privilege_zones",
    "data_stores",
    "external_integrations",
    "sensitive_operations",
)
CATEGORY_FIELDS = {
    "entrypoints": {
        "kind": "",
        "inputs": [],
    },
    "trust_boundaries": {
        "source_zone": "",
        "destination_zone": "",
    },
    "identity_and_privilege_zones": {
        "actors": [],
        "privileges": [],
    },
    "data_stores": {
        "kind": "",
        "data_types": [],
    },
    "external_integrations": {
        "kind": "",
        "direction": "",
    },
    "sensitive_operations": {
        "kind": "",
        "required_privilege": "",
    },
}
CATEGORY_REQUIRED_NON_EMPTY_FIELDS = {
    "entrypoints": ("kind",),
    "trust_boundaries": ("source_zone", "destination_zone"),
    "data_stores": ("kind",),
    "external_integrations": ("kind", "direction"),
    "sensitive_operations": ("kind", "required_privilege"),
}
CATEGORY_ALLOWED_VALUES = {
    "entrypoints": {
        "kind": {"http", "cli", "worker", "job", "webhook"},
    },
    "data_stores": {
        "kind": {"sql", "nosql", "cache", "filesystem", "object-store"},
    },
    "external_integrations": {
        "kind": {"http", "sdk", "queue", "oauth", "email", "cloud"},
        "direction": {"outbound", "inbound", "bidirectional"},
    },
    "sensitive_operations": {
        "kind": {"auth", "data-write", "file-write", "secret-use", "admin-action"},
    },
}
FINDING_LIKE_PATTERNS = (
    re.compile(r"\bvulnerab(?:ility|ilities|le)\b", re.I),
    re.compile(r"\bexploit(?:able|ability|ation)?\b", re.I),
    re.compile(r"\bweakness(?:es)?\b", re.I),
    re.compile(r"\b(?:security )?finding(?:s)?\b", re.I),
    re.compile(r"\b(?:security )?issue(?:s)?\b", re.I),
    re.compile(r"\battack(?: path| paths|er|ers)?\b", re.I),
    re.compile(r"\bcontrol gap(?:s)?\b", re.I),
    re.compile(r"\bunauthori[sz]ed\b", re.I),
    re.compile(r"\bprivilege escalation\b", re.I),
    re.compile(r"\bbypass\b", re.I),
    re.compile(r"\binjection\b", re.I),
    re.compile(r"\b(?:sqli|xss|csrf|ssrf|rce)\b", re.I),
    re.compile(r"\bpath traversal\b", re.I),
    re.compile(r"\bcommand injection\b", re.I),
    re.compile(r"\bdeseriali[sz](?:ation|e)\b", re.I),
    re.compile(r"\bdata leak(?:age)?\b", re.I),
    re.compile(r"\bexfiltrat(?:e|ion)\b", re.I),
    re.compile(r"\binsecure\b", re.I),
    re.compile(r"\bunsafe\b", re.I),
    re.compile(r"\bmalicious\b", re.I),
    re.compile(r"\brequest-controlled\b", re.I),
    re.compile(r"\bunsanitized\b", re.I),
    re.compile(r"\bunvalidated\b", re.I),
)

LOGGER = logging.getLogger(__name__)


def make_empty_system_map():
    """Return an empty repository-understanding map."""
    return {category: [] for category in CATEGORIES}


def normalize_text(value):
    """Normalize a value into a stripped string."""
    return str(value or "").strip()


def normalize_string_list(values):
    """Normalize a list of strings while keeping stable order."""
    if not isinstance(values, list):
        return []

    normalized = []
    seen = set()

    for value in values:
        text = normalize_text(value)
        key = text.casefold()

        if not text or key in seen:
            continue

        seen.add(key)
        normalized.append(text)

    return normalized


def parse_int(value, default=0):
    """Parse an integer value and fall back safely."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_path_list(values, allowed_paths):
    """Normalize repo-relative path lists against the allowed path set."""
    if not isinstance(values, list):
        return []

    normalized = []
    seen = set()

    for value in values:
        path = normalize_text(value)

        if not path or path not in allowed_paths or path in seen:
            continue

        seen.add(path)
        normalized.append(path)

    return normalized


def find_finding_like_terms(text):
    """Return finding-like keywords present in text."""
    normalized_text = normalize_text(text)
    matches = []
    seen = set()

    if not normalized_text:
        return matches

    for pattern in FINDING_LIKE_PATTERNS:
        match = pattern.search(normalized_text)

        if not match:
            continue

        term = match.group(0).lower()
        if term in seen:
            continue

        seen.add(term)
        matches.append(term)

    return matches


def dedupe_evidence(evidence_items):
    """Deduplicate evidence entries with stable ordering."""
    deduped = []
    seen = set()

    for evidence in evidence_items:
        chunk_id = normalize_text(evidence.get("chunk_id"))
        files = tuple(normalize_string_list(evidence.get("files", [])))
        rationale = normalize_text(evidence.get("rationale"))
        key = (chunk_id, files, rationale)

        if not chunk_id or not files or not rationale or key in seen:
            continue

        seen.add(key)
        deduped.append(
            {
                "chunk_id": chunk_id,
                "files": list(files),
                "rationale": rationale,
            }
        )

    return deduped


def dedupe_coverage_gaps(coverage_gaps):
    """Deduplicate coverage gaps with stable ordering."""
    deduped = []
    seen = set()

    for gap in coverage_gaps:
        category = normalize_text(gap.get("category"))
        summary = normalize_text(gap.get("summary"))
        chunk_ids = tuple(normalize_string_list(gap.get("chunk_ids", [])))
        key = (category, summary, chunk_ids)

        if not category or not summary or key in seen:
            continue

        seen.add(key)
        deduped.append(
            {
                "category": category,
                "summary": summary,
                "chunk_ids": list(chunk_ids),
            }
        )

    return sorted(
        deduped,
        key=lambda gap: (
            gap["category"].casefold(),
            gap["summary"].casefold(),
            tuple(chunk_id.casefold() for chunk_id in gap["chunk_ids"]),
        ),
    )


def merge_string_field(current_value, incoming_value):
    """Merge string fields conservatively."""
    current_text = normalize_text(current_value)
    incoming_text = normalize_text(incoming_value)

    if not current_text:
        return incoming_text
    if not incoming_text:
        return current_text
    if current_text.casefold() == incoming_text.casefold():
        return current_text
    if len(incoming_text) > len(current_text):
        return incoming_text
    return current_text


def make_gap(category, summary, chunk_ids):
    """Create a normalized coverage gap."""
    return {
        "category": normalize_text(category),
        "summary": normalize_text(summary),
        "chunk_ids": normalize_string_list(chunk_ids),
    }


def call_ai(prompt: str):
    """Call Copilot CLI and return parsed JSON output."""
    try:
        cmd = shlex.split(CMD)
        result = subprocess.run(cmd + [prompt], capture_output=True, text=True)
        output = (result.stdout or result.stderr).strip()
        match = re.search(r"\{.*\}", output, re.S)

        if not match:
            LOGGER.error("No JSON in AI response:\n%s", output)
            return None

        return json.loads(match.group(0))

    except Exception as exc:
        LOGGER.error("call_ai failed: %s", exc)
        return None


def normalize_input_chunk(raw_chunk, index):
    """Normalize a chunk object from the upstream input document."""
    issues = []

    if not isinstance(raw_chunk, dict):
        issues.append(f"Chunk at index {index} is not a JSON object.")
        return None, issues

    chunk_id = normalize_text(raw_chunk.get("id"))
    if not chunk_id:
        issues.append(f"Chunk at index {index} is missing id.")
        return None, issues

    name = normalize_text(raw_chunk.get("name")) or chunk_id
    reason = normalize_text(raw_chunk.get("reason"))

    raw_files = raw_chunk.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        issues.append(f"Chunk {chunk_id} is missing a non-empty files list.")
        return None, issues

    normalized_files = []
    seen_paths = set()

    for file_index, raw_file in enumerate(raw_files, 1):
        if not isinstance(raw_file, dict):
            issues.append(
                f"Chunk {chunk_id} file entry {file_index} is not a JSON object."
            )
            continue

        path = normalize_text(raw_file.get("path"))
        lines = max(parse_int(raw_file.get("lines"), 0), 0)

        if not path:
            issues.append(f"Chunk {chunk_id} file entry {file_index} is missing path.")
            continue

        if path in seen_paths:
            issues.append(f"Chunk {chunk_id} lists the same file more than once: {path}")
            continue

        seen_paths.add(path)
        normalized_files.append({"path": path, "lines": lines})

    if not normalized_files:
        issues.append(f"Chunk {chunk_id} has no usable file entries.")
        return None, issues

    computed_total_lines = sum(file_info["lines"] for file_info in normalized_files)
    total_lines = parse_int(raw_chunk.get("total_lines"), computed_total_lines)
    file_count = parse_int(raw_chunk.get("file_count"), len(normalized_files))

    if total_lines != computed_total_lines:
        issues.append(
            f"Chunk {chunk_id} total_lines did not match file line totals; using input value {total_lines}."
        )

    if file_count != len(normalized_files):
        issues.append(
            f"Chunk {chunk_id} file_count did not match the files list length."
        )

    return (
        {
            "id": chunk_id,
            "name": name,
            "reason": reason,
            "total_lines": total_lines,
            "file_count": file_count,
            "files": normalized_files,
        },
        issues,
    )


def resolve_root_path(root_value, input_json_path: Path):
    """Resolve the repository root from the input wrapper."""
    root_text = normalize_text(root_value)
    if not root_text:
        return None

    root_path = Path(root_text)
    if not root_path.is_absolute():
        root_path = (input_json_path.parent / root_path).resolve()

    return root_path


def load_repository_input(input_json_path):
    """Load and validate the repository-understanding input wrapper."""
    issues = []

    try:
        document = json.loads(input_json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(f"Failed to read input JSON: {exc}")
        return None, issues

    if not isinstance(document, dict):
        issues.append("Input JSON must be an object.")
        return None, issues

    root_path = resolve_root_path(document.get("root"), input_json_path)
    if root_path is None:
        issues.append("Input JSON is missing root.")

    raw_chunks = document.get("chunks")
    if not isinstance(raw_chunks, list) or not raw_chunks:
        issues.append("Input JSON is missing a non-empty chunks array.")
        return {
            "root_path": root_path,
            "chunks": [],
        }, issues

    chunks = []
    seen_chunk_ids = set()

    for index, raw_chunk in enumerate(raw_chunks, 1):
        chunk, chunk_issues = normalize_input_chunk(raw_chunk, index)
        issues.extend(chunk_issues)

        if chunk is None:
            continue

        chunk_id = chunk["id"]
        if chunk_id in seen_chunk_ids:
            issues.append(f"Duplicate chunk id found in input: {chunk_id}")
            continue

        seen_chunk_ids.add(chunk_id)
        chunks.append(chunk)

    if not chunks:
        issues.append("Input JSON did not contain any usable chunks.")

    return {
        "root_path": root_path,
        "chunks": chunks,
    }, issues


def build_chunk_contents(root_path: Path, chunk):
    """Read all readable files for a chunk and assemble a prompt document."""
    sections = []
    readable_paths = []
    issues = []

    for file_info in chunk["files"]:
        relative_path = file_info["path"]
        file_path = root_path / relative_path

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            issues.append(
                f"Chunk {chunk['id']} references unreadable file {relative_path}: {exc}"
            )
            continue

        readable_paths.append(relative_path)
        sections.append(f"=== FILE START: {relative_path} ===\n{content}")
        sections.append("=== FILE END ===")

    return "\n".join(sections), readable_paths, issues


def normalize_evidence(
    raw_evidence,
    allowed_chunk_ids,
    allowed_paths,
    default_chunk_id=None,
):
    """Normalize and validate evidence references."""
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


def normalize_category_items(
    category,
    raw_items,
    allowed_chunk_ids,
    allowed_paths,
    default_chunk_id,
    problems,
):
    """Normalize a category's AI-produced items into the fixed schema."""
    if not isinstance(raw_items, list):
        problems.append(f"{category} was not a list.")
        return []

    normalized_items = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        normalized_item = {
            "name": normalize_text(item.get("name")),
            "summary": normalize_text(item.get("summary")),
            "evidence": normalize_evidence(
                item.get("evidence", []),
                allowed_chunk_ids=allowed_chunk_ids,
                allowed_paths=allowed_paths,
                default_chunk_id=default_chunk_id,
            ),
        }

        for field_name, default_value in CATEGORY_FIELDS[category].items():
            raw_value = item.get(field_name, default_value)

            if isinstance(default_value, list):
                normalized_item[field_name] = normalize_string_list(raw_value)
            else:
                normalized_item[field_name] = normalize_text(raw_value)

        if not normalized_item["name"] or not normalized_item["summary"]:
            problems.append(f"Dropped {category} item with missing name or summary.")
            continue

        missing_required_fields = []
        for field_name in CATEGORY_REQUIRED_NON_EMPTY_FIELDS.get(category, ()):
            value = normalized_item.get(field_name)

            if isinstance(value, list):
                is_missing = not value
            else:
                is_missing = not normalize_text(value)

            if is_missing:
                missing_required_fields.append(field_name)

        if missing_required_fields:
            problems.append(
                f"Dropped {category} item {normalized_item['name']} with missing required field(s): "
                f"{', '.join(missing_required_fields)}."
            )
            continue

        invalid_enum_fields = []
        for field_name, allowed_values in CATEGORY_ALLOWED_VALUES.get(category, {}).items():
            field_value = normalize_text(normalized_item.get(field_name))

            if field_value and field_value not in allowed_values:
                invalid_enum_fields.append(f"{field_name}={field_value}")

        if invalid_enum_fields:
            problems.append(
                f"Dropped {category} item {normalized_item['name']} with unsupported field value(s): "
                f"{', '.join(invalid_enum_fields)}."
            )
            continue

        if not normalized_item["evidence"]:
            problems.append(f"Dropped {category} item {normalized_item['name']} without usable evidence.")
            continue

        finding_like_terms = []
        finding_like_terms.extend(find_finding_like_terms(normalized_item["name"]))
        finding_like_terms.extend(find_finding_like_terms(normalized_item["summary"]))

        for evidence in normalized_item["evidence"]:
            finding_like_terms.extend(find_finding_like_terms(evidence.get("rationale")))

        if finding_like_terms:
            problems.append(
                f"Dropped {category} item {normalized_item['name']} because it looked like a vulnerability finding "
                f"instead of neutral repository context ({', '.join(sorted(set(finding_like_terms)))})."
            )
            continue

        normalized_items.append(normalized_item)

    return sorted(normalized_items, key=lambda item: item["name"].casefold())


def normalize_coverage_gaps(raw_gaps, allowed_chunk_ids, fallback_chunk_ids):
    """Normalize coverage gaps returned by AI."""
    if not isinstance(raw_gaps, list):
        return []

    normalized = []

    for gap in raw_gaps:
        if not isinstance(gap, dict):
            continue

        category = normalize_text(gap.get("category"))
        summary = normalize_text(gap.get("summary"))
        chunk_ids = normalize_string_list(gap.get("chunk_ids", []))

        if not chunk_ids:
            chunk_ids = normalize_string_list(fallback_chunk_ids)

        filtered_chunk_ids = [
            chunk_id for chunk_id in chunk_ids if chunk_id in allowed_chunk_ids
        ]

        if not category or not summary or not filtered_chunk_ids:
            continue

        if find_finding_like_terms(summary):
            continue

        normalized.append(
            {
                "category": category,
                "summary": summary,
                "chunk_ids": filtered_chunk_ids,
            }
        )

    return dedupe_coverage_gaps(normalized)


def normalize_ai_repository_map(
    raw_result,
    allowed_chunk_ids,
    allowed_paths,
    fallback_chunk_ids=None,
    default_chunk_id=None,
):
    """Normalize an AI-produced repository map or fragment."""
    problems = []
    summary = ""
    system_map = make_empty_system_map()
    coverage_gaps = []

    if not isinstance(raw_result, dict):
        problems.append("AI did not return a JSON object.")
        return {
            "summary": summary,
            "system_map": system_map,
            "coverage_gaps": coverage_gaps,
        }, problems

    summary = normalize_text(raw_result.get("summary"))
    if find_finding_like_terms(summary):
        problems.append("AI summary looked like a vulnerability finding instead of neutral repository context.")
        summary = ""
    raw_system_map = raw_result.get("system_map")

    if not isinstance(raw_system_map, dict):
        if any(category in raw_result for category in CATEGORIES):
            raw_system_map = raw_result
        else:
            raw_system_map = {}
            problems.append("AI response did not contain system_map.")

    for category in CATEGORIES:
        system_map[category] = normalize_category_items(
            category=category,
            raw_items=raw_system_map.get(category, []),
            allowed_chunk_ids=allowed_chunk_ids,
            allowed_paths=allowed_paths,
            default_chunk_id=default_chunk_id,
            problems=problems,
        )

    coverage_gaps = normalize_coverage_gaps(
        raw_result.get("coverage_gaps", []),
        allowed_chunk_ids=allowed_chunk_ids,
        fallback_chunk_ids=fallback_chunk_ids or [],
    )

    return {
        "summary": summary,
        "system_map": system_map,
        "coverage_gaps": coverage_gaps,
    }, problems


def merge_items(category, current_item, incoming_item):
    """Merge two normalized category items."""
    merged_item = {
        "name": current_item.get("name", ""),
        "summary": merge_string_field(
            current_item.get("summary", ""),
            incoming_item.get("summary", ""),
        ),
        "evidence": dedupe_evidence(
            current_item.get("evidence", []) + incoming_item.get("evidence", [])
        ),
    }

    for field_name, default_value in CATEGORY_FIELDS[category].items():
        current_value = current_item.get(field_name, default_value)
        incoming_value = incoming_item.get(field_name, default_value)

        if isinstance(default_value, list):
            merged_item[field_name] = normalize_string_list(
                list(current_value) + list(incoming_value)
            )
        else:
            merged_item[field_name] = merge_string_field(current_value, incoming_value)

    return merged_item


def merge_key(item):
    """Build a conservative dedupe key for deterministic merging."""
    return normalize_text(item.get("name")).casefold()


def merge_system_maps(fragments):
    """Deterministically merge normalized chunk-level system maps."""
    merged_items = {category: {} for category in CATEGORIES}
    coverage_gaps = []

    for fragment in fragments:
        coverage_gaps.extend(fragment.get("coverage_gaps", []))
        system_map = fragment.get("system_map", {})

        for category in CATEGORIES:
            category_items = merged_items[category]

            for item in system_map.get(category, []):
                key = merge_key(item)

                if key in category_items:
                    category_items[key] = merge_items(category, category_items[key], item)
                else:
                    category_items[key] = item

    return (
        {
            category: sorted(
                merged_items[category].values(),
                key=lambda candidate: candidate["name"].casefold(),
            )
            for category in CATEGORIES
        },
        dedupe_coverage_gaps(coverage_gaps),
    )


def collect_chunk_fragment(root_path: Path, chunk):
    """Generate a normalized chunk-level repository understanding fragment."""
    problems = []
    coverage_gaps = []
    chunk_contents, readable_paths, read_issues = build_chunk_contents(root_path, chunk)
    problems.extend(read_issues)

    if read_issues:
        coverage_gaps.append(
            make_gap(
                "input",
                f"Chunk {chunk['id']} had unreadable or missing files.",
                [chunk["id"]],
            )
        )

    if not readable_paths:
        problems.append(f"Chunk {chunk['id']} had no readable files to analyze.")
        return {
            "summary": "",
            "system_map": make_empty_system_map(),
            "coverage_gaps": dedupe_coverage_gaps(coverage_gaps),
        }, problems

    prompt = build_mapper_chunk_prompt(
        chunk_json=json.dumps(chunk, indent=2),
        chunk_contents=chunk_contents,
    )
    raw_result = call_ai(prompt)
    normalized_result, normalization_problems = normalize_ai_repository_map(
        raw_result=raw_result,
        allowed_chunk_ids={chunk["id"]},
        allowed_paths=set(readable_paths),
        fallback_chunk_ids=[chunk["id"]],
        default_chunk_id=chunk["id"],
    )
    problems.extend(normalization_problems)
    coverage_gaps.extend(normalized_result["coverage_gaps"])

    if normalization_problems:
        coverage_gaps.append(
            make_gap(
                "system_map",
                f"Chunk {chunk['id']} produced incomplete AI output and may need review.",
                [chunk["id"]],
            )
        )

    return {
        "summary": normalized_result["summary"],
        "system_map": normalized_result["system_map"],
        "coverage_gaps": dedupe_coverage_gaps(coverage_gaps),
    }, problems


def synthesize_repository_map(merged_map, coverage_gaps, allowed_chunk_ids, allowed_paths):
    """Run the final synthesis pass over the deterministic merged map."""
    prompt = build_mapper_merge_prompt(
        merged_map_json=json.dumps(merged_map, indent=2),
        coverage_gaps_json=json.dumps(coverage_gaps, indent=2),
    )
    raw_result = call_ai(prompt)
    normalized_result, problems = normalize_ai_repository_map(
        raw_result=raw_result,
        allowed_chunk_ids=allowed_chunk_ids,
        allowed_paths=allowed_paths,
        fallback_chunk_ids=sorted(allowed_chunk_ids),
    )

    if problems:
        return {
            "summary": "",
            "system_map": merged_map,
            "coverage_gaps": coverage_gaps,
        }, problems

    final_coverage_gaps = dedupe_coverage_gaps(
        coverage_gaps + normalized_result["coverage_gaps"]
    )
    return {
        "summary": normalized_result["summary"],
        "system_map": normalized_result["system_map"],
        "coverage_gaps": final_coverage_gaps,
    }, []


def build_final_summary(chunk_count, coverage_gaps, problems, synthesized_summary=""):
    """Build the final top-level summary string."""
    if problems:
        return (
            f"Repository understanding completed with {len(problems)} issue(s) "
            f"across {chunk_count} chunk(s)."
        )

    if synthesized_summary:
        return synthesized_summary

    if coverage_gaps:
        return (
            f"Repository understanding completed with {len(coverage_gaps)} coverage gap(s) "
            f"across {chunk_count} chunk(s)."
        )

    return f"Repository understanding completed successfully across {chunk_count} chunk(s)."


def build_output(status, summary, root_path, chunks, system_map, coverage_gaps):
    """Assemble the final repository-understanding output payload."""
    unique_paths = sorted(
        {
            file_info["path"]
            for chunk in chunks
            for file_info in chunk.get("files", [])
        }
    )

    return {
        "status": status,
        "summary": summary,
        "input": {
            "root": str(root_path) if root_path else "",
            "chunk_count": len(chunks),
            "source_file_count": len(unique_paths),
        },
        "system_map": system_map,
        "coverage_gaps": dedupe_coverage_gaps(coverage_gaps),
    }


def run_mapper(input_json_path, output_json_path=None):
    """Run the repository mapper from a single input JSON file."""
    input_path = Path(input_json_path).resolve()
    output_path = (
        Path(output_json_path).resolve()
        if output_json_path
        else input_path.parent / DEFAULT_OUTPUT_FILE
    )

    document, input_issues = load_repository_input(input_path)
    root_path = document.get("root_path") if document else None
    chunks = document.get("chunks", []) if document else []
    problems = list(input_issues)
    coverage_gaps = []

    if input_issues:
        coverage_gaps.append(
            make_gap(
                "input",
                "The repository-understanding input document had validation issues.",
                [chunk["id"] for chunk in chunks],
            )
        )

    if root_path is None or not isinstance(root_path, Path):
        problems.append("Repository root could not be resolved from input.")
    elif not root_path.exists():
        problems.append(f"Repository root does not exist: {root_path}")

    fragments = []

    if root_path and root_path.exists():
        for chunk in chunks:
            fragment, fragment_problems = collect_chunk_fragment(root_path, chunk)
            fragments.append(fragment)
            problems.extend(fragment_problems)
            coverage_gaps.extend(fragment.get("coverage_gaps", []))

    merged_map, merged_gaps = merge_system_maps(fragments)
    coverage_gaps.extend(merged_gaps)

    all_allowed_chunk_ids = {chunk["id"] for chunk in chunks}
    all_allowed_paths = {
        file_info["path"]
        for chunk in chunks
        for file_info in chunk["files"]
    }

    synthesized_summary = ""

    if fragments and all_allowed_chunk_ids and all_allowed_paths:
        synthesized_result, synthesis_problems = synthesize_repository_map(
            merged_map=merged_map,
            coverage_gaps=dedupe_coverage_gaps(coverage_gaps),
            allowed_chunk_ids=all_allowed_chunk_ids,
            allowed_paths=all_allowed_paths,
        )
        merged_map = synthesized_result["system_map"]
        coverage_gaps = synthesized_result["coverage_gaps"]
        synthesized_summary = synthesized_result["summary"]
        problems.extend(synthesis_problems)

        if synthesis_problems:
            coverage_gaps.append(
                make_gap(
                    "system_map",
                    "The final repository synthesis was incomplete and fell back to the deterministic merge.",
                    sorted(all_allowed_chunk_ids),
                )
            )

    status = "needs_review" if problems else "pass"
    summary = build_final_summary(
        chunk_count=len(chunks),
        coverage_gaps=coverage_gaps,
        problems=problems,
        synthesized_summary=synthesized_summary,
    )
    payload = build_output(
        status=status,
        summary=summary,
        root_path=root_path,
        chunks=chunks,
        system_map=merged_map,
        coverage_gaps=coverage_gaps,
    )
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Generate a repository-understanding system map from chunk JSON input."
    )
    parser.add_argument("input_json", help="Path to the repository-understanding input JSON file.")
    parser.add_argument(
        "output_json",
        nargs="?",
        help="Optional explicit output path. Defaults to repository-understanding.json next to the input file.",
    )
    args = parser.parse_args()
    run_mapper(args.input_json, args.output_json)


if __name__ == "__main__":
    main()
