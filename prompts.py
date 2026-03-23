"""Prompt builders for the chunking workflow."""


def build_chunk_plan_prompt(items, max_lines):
    """Build the codebase chunking prompt from repo inventory metadata."""
    inventory = "\n".join(
        f'{item["path"]}\t{item["lines"]}\t{item["dir"]}'
        for item in items
    )

    return f"""Return ONLY JSON.
Task: partition this codebase into review chunks for deep code/security review.
Goals:
- chunks should be coherent by subsystem
- every file assigned exactly once
- each chunk should stay roughly below {max_lines} total lines unless one file alone exceeds it
- prefer few related files per chunk over many unrelated ones
- deterministic stable names

JSON schema:
{{
  "chunks":[
    {{
      "id":"chunk-0001",
      "name":"short-stable-name",
      "reason":"one sentence",
      "files":["a","b"]
    }}
  ]
}}

Files (path<TAB>lines<TAB>topdir):
{inventory}
"""


def build_validation_prompt(manifest, chunks):
    """Build the AI prompt used to validate chunking output."""
    return f"""Return ONLY JSON.
Task: validate a codebase chunking job for deep review.
Goals:
- check whether the manifest and chunk metadata are internally consistent
- flag meaningful issues with chunk coherence, naming, or suspicious sizing
- prefer concrete findings over vague criticism
- if the job looks good, return an empty issues list and status "pass"

JSON schema:
{{
  "status":"pass",
  "summary":"one sentence",
  "issues":[
    {{
      "chunk_id":"chunk-0001",
      "severity":"low",
      "message":"one sentence"
    }}
  ],
  "recommendations":["short suggestion"]
}}

Allowed status values:
- "pass"
- "needs_review"
- "fail"

Allowed severity values:
- "low"
- "medium"
- "high"

Manifest:
```json
{manifest}
```

Chunk metadata:
```json
{chunks}
```
"""
