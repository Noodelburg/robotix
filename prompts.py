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


def build_mapper_subtask_prompt(
    guide_path,
    guide_focus,
    guide_markdown,
    chunk_json,
    chunk_contents,
):
    """Build the AI prompt for a guide-driven mapper subtask."""
    return f"""Return ONLY JSON.
Task: use the provided OWASP WSTG information-gathering guide as the strategy for one repository-mapping subtask.
This subtask should map only the repository context that is supported by the guide and the provided chunk contents.

Primary focus categories for this guide:
{guide_focus}

Available categories:
- entrypoints
- trust_boundaries
- identity_and_privilege_zones
- data_stores
- external_integrations
- sensitive_operations

Rules:
- Treat the WSTG guide as a mapping methodology, not as an instruction to report findings.
- Only include entities supported by the provided chunk metadata and file contents.
- Prefer grounded, high-signal entities over speculative guesses.
- This mapper creates architectural context only. It must not identify vulnerabilities, findings, attack paths, missing controls, insecure behavior, or exploitability.
- Describe what exists and how it is connected, not whether it is safe or unsafe.
- For sensitive_operations, describe privileged or high-impact operations neutrally; do not explain how they could be abused.
- Every emitted item must include evidence with chunk_id, files, and rationale.
- Evidence files must be repo-relative paths from the chunk metadata.
- Use the guide's strategy to decide what to look for in the code. Adapt web-testing instructions into a source-based mapping lens.
- If the guide is only partially applicable to source-based analysis, return whatever grounded context it supports and use coverage_gaps for the rest.
- If the chunk does not support an item in a category, return an empty list for that category.
- You may return coverage gaps for areas that appear relevant but remain unclear from this chunk alone.
- Do not invent line numbers, services, data stores, privileges, or integrations not visible in the material.
- Use neutral, architectural language in names, summaries, and evidence rationales.

JSON schema:
{{
  "summary":"one sentence",
  "system_map":{{
    "entrypoints":[
      {{
        "name":"admin API",
        "kind":"http",
        "summary":"what enters here",
        "inputs":["request body","headers"],
        "evidence":[
          {{
            "chunk_id":"chunk-0001",
            "files":["src/routes/admin.py"],
            "rationale":"route registration and handler logic"
          }}
        ]
      }}
    ],
    "trust_boundaries":[
      {{
        "name":"public request to app server",
        "source_zone":"untrusted client",
        "destination_zone":"application",
        "summary":"boundary description",
        "evidence":[
          {{
            "chunk_id":"chunk-0001",
            "files":["src/routes/admin.py"],
            "rationale":"request handlers accept external input"
          }}
        ]
      }}
    ],
    "identity_and_privilege_zones":[
      {{
        "name":"admin users",
        "actors":["admin"],
        "privileges":["manage tenants"],
        "summary":"role or privilege zone",
        "evidence":[
          {{
            "chunk_id":"chunk-0001",
            "files":["src/authz.py"],
            "rationale":"authorization checks reference admin role"
          }}
        ]
      }}
    ],
    "data_stores":[
      {{
        "name":"primary postgres",
        "kind":"sql",
        "summary":"stored data and purpose",
        "data_types":["accounts","tokens"],
        "evidence":[
          {{
            "chunk_id":"chunk-0001",
            "files":["src/models.py"],
            "rationale":"database models and queries show persisted data"
          }}
        ]
      }}
    ],
    "external_integrations":[
      {{
        "name":"Stripe API",
        "kind":"http",
        "direction":"outbound",
        "summary":"integration purpose",
        "evidence":[
          {{
            "chunk_id":"chunk-0001",
            "files":["src/billing.py"],
            "rationale":"outbound client calls to Stripe"
          }}
        ]
      }}
    ],
    "sensitive_operations":[
      {{
        "name":"tenant deletion",
        "kind":"admin-action",
        "required_privilege":"admin",
        "summary":"why the operation is sensitive",
        "evidence":[
          {{
            "chunk_id":"chunk-0001",
            "files":["src/admin.py"],
            "rationale":"handler performs destructive tenant management"
          }}
        ]
      }}
    ]
  }},
  "coverage_gaps":[
    {{
      "category":"entrypoints",
      "summary":"what remains unclear from this chunk",
      "chunk_ids":["chunk-0001"]
    }}
  ]
}}

WSTG guide path:
`{guide_path}`

WSTG guide excerpt:
```md
{guide_markdown}
```

Chunk metadata:
```json
{chunk_json}
```

Chunk contents:
{chunk_contents}
"""


def build_mapper_merge_prompt(merged_map_json, coverage_gaps_json):
    """Build the AI prompt for repository-wide map consolidation."""
    return f"""Return ONLY JSON.
Task: consolidate a repository-wide system map for downstream review context.

You are given a deterministic merged map assembled from chunk-local outputs.
Your job is to improve naming consistency and collapse duplicates while staying evidence-first.

Rules:
- Do not invent new entities, evidence, privileges, data stores, or integrations.
- Only merge or rename entities that are already present in the input.
- Preserve or combine evidence from the input items you merge.
- Keep all six categories present even if some are empty.
- Keep the output architectural and contextual only. Do not introduce vulnerability findings, abuse cases, impact claims, or control-gap analysis.
- Every emitted item must include evidence with chunk_id, files, and rationale.
- Coverage gaps should be preserved, deduplicated, or clarified, not discarded without reason.
- Use neutral, descriptive language in names, summaries, and rationales.

JSON schema:
{{
  "summary":"one sentence",
  "system_map":{{
    "entrypoints":[],
    "trust_boundaries":[],
    "identity_and_privilege_zones":[],
    "data_stores":[],
    "external_integrations":[],
    "sensitive_operations":[]
  }},
  "coverage_gaps":[
    {{
      "category":"entrypoints",
      "summary":"what remains unclear",
      "chunk_ids":["chunk-0001"]
    }}
  ]
}}

Deterministic merged system map:
```json
{merged_map_json}
```

Coverage gaps:
```json
{coverage_gaps_json}
```
"""


def build_mapper_validation_prompt(
    input_json,
    audit_json,
    current_output_json,
    evidence_bundle,
):
    """Build the AI prompt for system-map validation and correction."""
    return f"""Return ONLY JSON.
Task: validate and, if necessary, minimally correct a system-map output produced by mapper.py.

Goals:
- use the mapper input JSON as ground truth for valid chunk ids and file paths
- review the current system-map output against the deterministic audit findings
- preserve grounded entities and evidence wherever possible
- remove or repair unsupported, malformed, duplicate, or mis-grounded entries
- keep the output contextual only, not vulnerability-oriented
- keep corrections minimal and avoid fully regenerating the map unless the current output is too broken to patch safely

Rules:
- Do not invent new entities, privileges, integrations, or evidence.
- Remove or rewrite finding-like, exploit-oriented, or vulnerability-oriented language so the output stays architectural and preparatory only.
- Every retained item must include evidence with chunk_id, files, and rationale.
- Evidence files must belong to the referenced chunk in the input JSON.
- Keep all six system_map categories present, even if empty.
- Use coverage_gaps for uncertainty instead of guessing.
- If the current output is acceptable, return status "pass" and corrected_output as null.
- If you make corrections, return the full corrected system-map payload in corrected_output.
- Return only JSON matching the schema below.

JSON schema:
{{
  "status":"pass",
  "summary":"one sentence",
  "issues":[
    {{
      "category":"entrypoints",
      "entity_name":"Admin API",
      "message":"one sentence"
    }}
  ],
  "corrected_output": {{
    "summary":"one sentence",
    "system_map": {{
      "entrypoints": [],
      "trust_boundaries": [],
      "identity_and_privilege_zones": [],
      "data_stores": [],
      "external_integrations": [],
      "sensitive_operations": []
    }},
    "coverage_gaps":[
      {{
        "category":"entrypoints",
        "summary":"what remains unclear",
        "chunk_ids":["chunk-0001"]
      }}
    ]
  }}
}}

Allowed status values:
- "pass"
- "corrected"
- "needs_review"

Mapper input JSON:
```json
{input_json}
```

Deterministic audit findings:
```json
{audit_json}
```

Current system-map output:
```json
{current_output_json}
```

Evidence file bundle:
{evidence_bundle}
"""
