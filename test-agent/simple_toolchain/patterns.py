"""Heuristic pattern rules for the simplified security review worker."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Pattern


@dataclass(frozen=True)
class LinePatternRule:
    """A readable line-based pattern rule for worker checks."""

    category: str
    title: str
    severity: str
    regex: Pattern[str]
    reasoning: str
    suggested_test: str
    curl_confirmable: bool = False


LINE_RULES: List[LinePatternRule] = [
    LinePatternRule(
        category="dangerous-shell-execution",
        title="Possible dangerous shell execution sink",
        severity="high",
        regex=re.compile(
            r"(os\.system\(|subprocess\.(run|Popen|call).*(shell\s*=\s*True)|Runtime\.getRuntime\(\)\.exec\(|ProcessBuilder\(|exec\()"
        ),
        reasoning="The code appears to execute shell or process commands directly.",
        suggested_test="Attempt command injection payloads through any user-controlled inputs that reach this execution path.",
    ),
    LinePatternRule(
        category="raw-sql-construction",
        title="Possible raw SQL string construction",
        severity="high",
        regex=re.compile(
            r"((SELECT|INSERT|UPDATE|DELETE).*(\+|%s|\{.+\}|f['\"]).*|query\s*=.*(SELECT|INSERT|UPDATE|DELETE).*(\+|\{))",
            re.IGNORECASE,
        ),
        reasoning="The code appears to build a SQL statement dynamically instead of using safe parameter binding.",
        suggested_test="Attempt SQL injection style input through parameters that may reach this query-building path.",
    ),
    LinePatternRule(
        category="unsafe-file-path-construction",
        title="Possible unsafe file path construction",
        severity="high",
        regex=re.compile(
            r"((open|readFile|writeFile|sendFile|File\(|Paths\.get\().*(req\.|request\.|params|query|body|input|filename|path))",
            re.IGNORECASE,
        ),
        reasoning="The code appears to use user-influenced path values in file operations.",
        suggested_test="Attempt path traversal inputs such as ../ and encoded traversal sequences against this file-handling path.",
        curl_confirmable=True,
    ),
    LinePatternRule(
        category="ssrf-like-url-fetch",
        title="Possible user-influenced outbound URL fetch",
        severity="high",
        regex=re.compile(
            r"((requests\.(get|post)|axios\.(get|post)|fetch\(|httpx\.(get|post)|urllib\.request|http\.Get\(|RestTemplate).*(req\.|request\.|params|query|body|url))",
            re.IGNORECASE,
        ),
        reasoning="The code appears to fetch an outbound URL using user-influenced input.",
        suggested_test="Attempt SSRF-style inputs using internal-looking URLs, localhost, metadata endpoints, or alternate schemes if relevant.",
        curl_confirmable=True,
    ),
    LinePatternRule(
        category="debug-or-error-leakage",
        title="Possible debug or verbose error leakage",
        severity="medium",
        regex=re.compile(
            r"(debug\s*=\s*true|DEBUG\s*=\s*True|traceback|printStackTrace|console\.log\(err|stack trace|errorhandler\()",
            re.IGNORECASE,
        ),
        reasoning="The code appears to expose debug behavior or verbose error details that may leak internals.",
        suggested_test="Trigger an error condition and inspect whether stack traces, internal paths, or sensitive context are exposed.",
        curl_confirmable=True,
    ),
    LinePatternRule(
        category="hardcoded-secret",
        title="Possible hardcoded secret or token",
        severity="high",
        regex=re.compile(
            r"((api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}['\"])",
            re.IGNORECASE,
        ),
        reasoning="The code appears to contain a secret-like literal directly in source or config.",
        suggested_test="Review whether the secret is real, whether it is active, and whether the surrounding path can be exercised with secret rotation or invalid-secret conditions.",
    ),
    LinePatternRule(
        category="unsafe-deserialization",
        title="Possible unsafe deserialization sink",
        severity="high",
        regex=re.compile(
            r"(pickle\.loads\(|yaml\.load\(|marshal\.loads\(|ObjectInputStream|BinaryFormatter|jsonpickle\.decode\(|eval\()",
            re.IGNORECASE,
        ),
        reasoning="The code appears to deserialize or evaluate untrusted input using a risky API.",
        suggested_test="Attempt crafted serialized or expression-like input and confirm whether the code safely rejects it.",
    ),
]


ROUTE_PATTERN = re.compile(
    r'(?P<route>/(api|admin|internal|v\d+)[^"\'\s)]*)',
    re.IGNORECASE,
)


ROUTE_LINE_PATTERN = re.compile(
    r"(app\.(get|post|put|delete|patch)|router\.(get|post|put|delete|patch)|@RequestMapping|@GetMapping|@PostMapping|http\.HandleFunc)",
    re.IGNORECASE,
)


AUTH_HINT_PATTERN = re.compile(
    r"(auth|authorize|authentication|jwt|token|middleware|guard|permission|role)",
    re.IGNORECASE,
)


def infer_route_hint(text: str) -> Optional[str]:
    """Try to extract a route-looking path from a code snippet."""

    route_match = ROUTE_PATTERN.search(text)
    if route_match:
        return route_match.group("route")
    return None


def looks_like_route_handler(line: str) -> bool:
    """Return True when a line resembles a route registration or mapping."""

    return bool(ROUTE_LINE_PATTERN.search(line))


def has_auth_hint(text: str) -> bool:
    """Return True when a line or nearby context contains auth-related language."""

    return bool(AUTH_HINT_PATTERN.search(text))
