"""Prompt builders for poc.py."""


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
