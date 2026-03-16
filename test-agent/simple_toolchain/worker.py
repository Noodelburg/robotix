"""Worker logic for the simplified source-review flow."""

from __future__ import annotations

from typing import List

from models import Finding, SourceFile
from patterns import LINE_RULES, has_auth_hint, infer_route_hint, looks_like_route_handler


def review_batch(files: List[SourceFile]) -> List[Finding]:
    """Review a batch of source files and emit normalized findings."""

    findings: List[Finding] = []
    for source_file in files:
        findings.extend(_scan_line_rules(source_file))
        findings.extend(_scan_auth_routes(source_file))
    return findings


def _scan_line_rules(source_file: SourceFile) -> List[Finding]:
    """Apply simple line-based regex heuristics to a single file."""

    findings: List[Finding] = []
    for line_number, line in enumerate(source_file.text.splitlines(), start=1):
        for rule in LINE_RULES:
            if rule.regex.search(line):
                evidence = line.strip()[:240]
                findings.append(
                    Finding(
                        category=rule.category,
                        title=rule.title,
                        severity=rule.severity,
                        file_path=source_file.path,
                        line_number=line_number,
                        evidence=evidence,
                        reasoning=rule.reasoning,
                        suggested_test=rule.suggested_test,
                        curl_confirmable=rule.curl_confirmable,
                        route_hint=infer_route_hint(line),
                    )
                )
    return findings


def _scan_auth_routes(source_file: SourceFile) -> List[Finding]:
    """Look for obvious route handlers that appear to lack nearby auth hints."""

    findings: List[Finding] = []
    lines = source_file.text.splitlines()
    for index, line in enumerate(lines):
        if not looks_like_route_handler(line):
            continue

        route_hint = infer_route_hint(line)
        if not route_hint:
            continue
        if not any(token in route_hint.lower() for token in ("/admin", "/internal", "/api")):
            continue

        context_start = max(0, index - 2)
        context_end = min(len(lines), index + 3)
        context = "\n".join(lines[context_start:context_end])
        if has_auth_hint(context):
            continue

        findings.append(
            Finding(
                category="weak-auth-or-missing-auth",
                title="Route looks sensitive but lacks obvious nearby auth checks",
                severity="high",
                file_path=source_file.path,
                line_number=index + 1,
                evidence=line.strip()[:240],
                reasoning="The route name suggests an API, admin, or internal path, but nearby code does not show obvious authentication or authorization markers.",
                suggested_test="Attempt unauthenticated and low-privilege access to this route and confirm whether authorization is consistently enforced.",
                curl_confirmable=True,
                route_hint=route_hint,
            )
        )
    return findings
