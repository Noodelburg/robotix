#!/usr/bin/env python3
"""Guide catalog helpers for WSTG review workers."""

import re
from pathlib import Path


WSTG_ROOT = Path(__file__).resolve().parent / "wstg"
GUIDE_AREA_GLOB = "[0-1][0-9]-*"
AREA_ID_PREFIXES = {
    "02-Configuration_and_Deployment_Management_Testing": "CONF",
    "03-Identity_Management_Testing": "IDNT",
    "04-Authentication_Testing": "ATHN",
    "05-Authorization_Testing": "ATHZ",
    "06-Session_Management_Testing": "SESS",
    "07-Input_Validation_Testing": "INPV",
    "08-Testing_for_Error_Handling": "ERRH",
    "09-Testing_for_Weak_Cryptography": "CRYP",
    "10-Business_Logic_Testing": "BUSL",
    "11-Client-side_Testing": "CLNT",
    "12-API_Testing": "APIT",
}
SUPPORT_RELATIVE_PATHS = {
    "wstg/10-Business_Logic_Testing/00-Introduction_to_Business_Logic.md",
    "wstg/12-API_Testing/00-API_Testing_Overview.md",
}
MERGED_ALIAS_TARGETS = {
    "WSTG-IDNT-05": "WSTG-IDNT-04",
    "WSTG-ATHN-01": "WSTG-CRYP-03",
    "WSTG-INPV-03": "WSTG-CONF-06",
    "WSTG-ERRH-02": "WSTG-ERRH-01",
}
WSTG_ID_PATTERN = re.compile(r"\|\s*(WSTG-[A-Z]+-\d+)\s*\|")
MERGED_TARGET_PATTERN = re.compile(r"\[merged\]:\s*#\s*\(([^)]+)\)")
FILE_PREFIX_PATTERN = re.compile(r"^([0-9]+(?:\.[0-9]+)?)")


def normalize_text(value):
    """Normalize a value into a stripped string."""
    return str(value or "").strip()


def extract_title(markdown, fallback_name=""):
    """Extract the markdown title."""
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()

    return normalize_text(fallback_name)


def extract_wstg_id(markdown):
    """Extract a WSTG identifier from a markdown guide."""
    match = WSTG_ID_PATTERN.search(markdown)
    return match.group(1) if match else ""


def extract_merged_target(markdown):
    """Extract a canonical merged target identifier."""
    match = MERGED_TARGET_PATTERN.search(markdown)
    return match.group(1).strip() if match else ""


def trim_review_markdown(markdown):
    """Keep the sections that are most useful for source-guided review."""
    sections = []

    for line in markdown.splitlines():
        if line.strip() == "## References":
            break
        sections.append(line)

    trimmed = "\n".join(sections).strip()
    return trimmed or markdown.strip()


def slugify_fragment(text):
    """Build a deterministic ID fragment from free text."""
    tokens = re.findall(r"[A-Za-z0-9]+", normalize_text(text).upper())
    return "_".join(tokens[:6]) if tokens else "GUIDE"


def extract_file_prefix(relative_path):
    """Extract the leading numeric prefix from a guide filename."""
    match = FILE_PREFIX_PATTERN.match(Path(relative_path).name)
    return match.group(1) if match else ""


def derive_fallback_wstg_id(relative_path, title):
    """Derive a stable fallback WSTG id for sub-guides without an explicit id."""
    parts = Path(relative_path).parts
    area = parts[1] if len(parts) > 1 else ""
    family = AREA_ID_PREFIXES.get(area, "EXT")
    file_prefix = extract_file_prefix(relative_path)

    if file_prefix:
        return f"WSTG-{family}-{file_prefix}"

    return f"WSTG-{family}-{slugify_fragment(title or Path(relative_path).stem)}"


def make_unique_wstg_id(candidate, relative_path, title, seen_ids):
    """Ensure the chosen guide id is unique within the actionable catalog."""
    base_candidate = candidate or derive_fallback_wstg_id(relative_path, title)

    if base_candidate not in seen_ids:
        return base_candidate

    suffix = slugify_fragment(title or Path(relative_path).stem)
    candidate_with_suffix = f"{base_candidate}-{suffix}"

    if candidate_with_suffix not in seen_ids:
        return candidate_with_suffix

    counter = 2
    while True:
        numbered_candidate = f"{candidate_with_suffix}-{counter}"
        if numbered_candidate not in seen_ids:
            return numbered_candidate
        counter += 1


def is_in_review_scope(relative_path):
    """Return whether a guide path is in the 02-* through 12-* review scope."""
    parts = Path(relative_path).parts
    if len(parts) < 2 or parts[0] != "wstg":
        return False

    area = parts[1]
    prefix = area[:2]

    return prefix.isdigit() and 2 <= int(prefix) <= 12


def classify_guide(relative_path, markdown, wstg_id):
    """Classify a guide as a test case, support doc, or merged alias."""
    file_name = Path(relative_path).name

    if file_name == "README.md" or relative_path in SUPPORT_RELATIVE_PATHS:
        return "support"

    if wstg_id in MERGED_ALIAS_TARGETS or extract_merged_target(markdown):
        return "merged_alias"

    return "test_case"


def load_review_guides(root=None):
    """Load actionable WSTG guides and attach support metadata."""
    workspace_root = Path(__file__).resolve().parent
    guide_root = Path(root or WSTG_ROOT)
    issues = []
    all_guides = []
    support_by_area = {}
    test_cases_by_id = {}
    seen_actionable_ids = set()
    alias_resolution = []

    for guide_path in sorted(guide_root.glob(f"{GUIDE_AREA_GLOB}/*.md")):
        relative_path = str(guide_path.relative_to(workspace_root))

        if not is_in_review_scope(relative_path):
            continue

        try:
            raw_markdown = guide_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            issues.append(f"Failed to read review guide {guide_path.name}: {exc}")
            continue

        markdown = trim_review_markdown(raw_markdown)
        source_wstg_id = extract_wstg_id(raw_markdown)
        title = extract_title(raw_markdown, guide_path.stem)
        merged_target = extract_merged_target(raw_markdown) or MERGED_ALIAS_TARGETS.get(
            source_wstg_id,
            "",
        )
        area = guide_path.parent.name
        classification = classify_guide(relative_path, raw_markdown, source_wstg_id)
        wstg_id = source_wstg_id

        if classification == "test_case":
            wstg_id = make_unique_wstg_id(
                source_wstg_id,
                relative_path,
                title,
                seen_actionable_ids,
            )
            seen_actionable_ids.add(wstg_id)

        record = {
            "title": title,
            "wstg_id": wstg_id,
            "source_wstg_id": source_wstg_id,
            "path": str(guide_path),
            "relative_path": relative_path,
            "area": area,
            "classification": classification,
            "markdown": markdown,
            "merged_target_wstg_id": merged_target,
            "support_paths": [],
            "alias_paths": [],
        }
        all_guides.append(record)

        if classification == "support":
            support_by_area.setdefault(area, []).append(record)
        elif classification == "test_case":
            test_cases_by_id[wstg_id] = record

    for test_case in test_cases_by_id.values():
        test_case["support_paths"] = sorted(
            support_doc["relative_path"]
            for support_doc in support_by_area.get(test_case["area"], [])
        )

    for guide in all_guides:
        if guide["classification"] != "merged_alias":
            continue

        target_wstg_id = guide["merged_target_wstg_id"]
        target = test_cases_by_id.get(target_wstg_id)

        if target is None:
            issues.append(
                f"Merged alias {guide['relative_path']} points to unknown guide {target_wstg_id}."
            )
            continue

        target["support_paths"] = sorted(
            set(target["support_paths"] + [guide["relative_path"]])
        )
        target["alias_paths"] = sorted(
            set(target.get("alias_paths", []) + [guide["relative_path"]])
        )
        alias_resolution.append(
            {
                "alias_wstg_id": guide["wstg_id"],
                "alias_path": guide["relative_path"],
                "target_wstg_id": target_wstg_id,
                "target_path": target["relative_path"],
            }
        )

    support_docs = [guide for guide in all_guides if guide["classification"] == "support"]
    merged_aliases = [
        guide for guide in all_guides if guide["classification"] == "merged_alias"
    ]
    test_cases = sorted(
        test_cases_by_id.values(),
        key=lambda guide: guide["wstg_id"].casefold(),
    )
    guides_by_path = {guide["relative_path"]: guide for guide in all_guides}

    return {
        "test_cases": test_cases,
        "support_docs": support_docs,
        "merged_aliases": merged_aliases,
        "guides_by_path": guides_by_path,
        "alias_resolution": sorted(
            alias_resolution,
            key=lambda item: (
                item["target_wstg_id"].casefold(),
                item["alias_wstg_id"].casefold(),
            ),
        ),
        "issues": issues,
    }


def load_support_bundle(catalog, guide):
    """Return supporting guide records and combined markdown for a guide."""
    support_records = [
        catalog["guides_by_path"][relative_path]
        for relative_path in guide.get("support_paths", [])
        if relative_path in catalog["guides_by_path"]
    ]
    sections = []

    for support_record in support_records:
        sections.append(f"=== SUPPORT START: {support_record['relative_path']} ===")
        sections.append(support_record["markdown"])
        sections.append("=== SUPPORT END ===")

    return support_records, "\n".join(sections).strip()
