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


def build_validation_prompt(
    inventory_summary,
    manifest_json,
    audit_json,
    chunk_metadata_json,
    chunk_contents,
):
    """Build the AI prompt used to validate and correct chunk output."""
    return f"""Return ONLY JSON.
Task: validate and, if necessary, minimally correct a chunking job produced by chunker.py.
Goals:
- use the rebuilt repo inventory as ground truth
- review the current chunk plan against the manifest, chunk metadata, and full chunk contents
- flag missed files, duplicate assignments, oversized chunks, and clearly bad grouping
- keep changes minimal and preserve existing chunk ids and names where possible
- do not fully replan unless the current chunking is too broken to patch safely

Rules:
- Every file must be assigned exactly once in corrected_chunks if you return corrections.
- If the current output is acceptable, return status "pass" and an empty corrected_chunks list.
- If you make corrections, return the full corrected chunk plan in corrected_chunks.
- Prefer fixing only the affected chunks over replacing the whole plan.
- Return only JSON matching the schema below.

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
  "corrected_chunks":[
    {{
      "id":"chunk-0001",
      "name":"short-stable-name",
      "reason":"one sentence",
      "files":["a","b"]
    }}
  ]
}}

Allowed status values:
- "pass"
- "corrected"
- "needs_review"

Allowed severity values:
- "low"
- "medium"
- "high"

Rebuilt inventory summary (path<TAB>lines<TAB>topdir):
{inventory_summary}

Deterministic audit findings:
```json
{audit_json}
```

Current manifest:
```json
{manifest_json}
```

Current chunk metadata:
```json
{chunk_metadata_json}
```

Current chunk JSON files:
{chunk_contents}
"""
