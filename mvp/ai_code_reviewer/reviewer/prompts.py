"""Prompt text for code review requests.

Keeping prompts in one module makes them easy to tweak without touching
provider or CLI code.
"""

SYSTEM_PROMPT = """You are a careful senior code reviewer.
Review only the provided diff.
Focus on bugs, correctness, security, and maintainability.
Ignore style-only nits.
Only report meaningful issues.
Do not invent file names, line numbers, or code that is not present in the diff.
Return JSON that matches the requested schema."""


def build_review_prompt(diff_text: str) -> str:
    """Build the user-facing review prompt."""
    return f"""Review this git diff and return a short JSON review report.

Rules:
- Report only meaningful issues.
- Prefer high-signal findings over long lists.
- If there are no important problems, return an empty findings list.
- Base every finding on the diff only.

Diff:
```diff
{diff_text}
```"""

