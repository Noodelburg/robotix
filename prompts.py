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


def build_reviewer_routing_prompt(
    guide_json,
    guide_markdown,
    support_markdown,
    system_map_json,
    chunk_manifest_json,
):
    """Build the AI prompt for guide-to-chunk routing."""
    return f"""Return ONLY JSON.
Task: rank repository chunks for a WSTG-guided security review worker.

Goals:
- route this guide to the chunks most likely to contain relevant code paths
- use the guide text, support docs, system-map context, and chunk metadata together
- rank by review relevance only; do not report vulnerabilities or findings here

Rules:
- Only use chunk ids that appear in the provided chunk manifest.
- Prefer chunks with matching entrypoints, trust boundaries, privileged operations, or data flows.
- Use the system map to focus the review, not to invent facts beyond the manifest.
- Rank the most relevant chunks first and keep rationales short and grounded.
- Return only JSON matching the schema below.

JSON schema:
{{
  "summary":"one sentence",
  "ranked_chunks":[
    {{
      "chunk_id":"chunk-0001",
      "relevance":"high",
      "rationale":"one sentence"
    }}
  ]
}}

Allowed relevance values:
- "high"
- "medium"
- "low"

Guide metadata:
```json
{guide_json}
```

Guide markdown:
```md
{guide_markdown}
```

Support markdown:
```md
{support_markdown}
```

System-map context:
```json
{system_map_json}
```

Chunk manifest:
```json
{chunk_manifest_json}
```
"""


def build_reviewer_subtask_prompt(
    guide_json,
    guide_markdown,
    support_markdown,
    system_map_json,
    chunk_json,
    chunk_contents,
):
    """Build the AI prompt for one WSTG-guided review chunk pass."""
    return f"""Return ONLY JSON.
Task: review the provided repository chunk through the lens of the supplied OWASP WSTG test case.

Goals:
- produce evidence-backed candidate findings only
- keep certainty limited to suspected, plausible, or high-confidence
- explain each finding as a code-grounded attack path hypothesis
- record grounded rejected hypotheses when the chunk appears relevant but does not support a real issue

Rules:
- Treat the WSTG guide as the review methodology for this worker.
- Only use facts grounded in the chunk contents, chunk metadata, support docs, and system-map context.
- Do not claim a finding is confirmed, validation-ready, exploited, or reproducible in a live environment.
- Do not invent files, code paths, protections, or impacts that are not supported by the provided material.
- Every candidate finding must include evidence and at least one counter-evidence note.
- Use `broader-repository-context` as the coverage-gap reason only when more chunks are needed before this guide can be judged well.
- Use rejected_hypotheses when the guide seems relevant but the chunk shows a plausible control or the suspected path is not grounded here.
- Return only JSON matching the schema below.

JSON schema:
{{
  "summary":"one sentence",
  "candidate_findings":[
    {{
      "title":"Mass assignment in profile update handler",
      "certainty":"plausible",
      "weakness_summary":"one paragraph",
      "attack_path": {{
        "entrypoint":"profile update endpoint",
        "controllable_input":"request body fields",
        "control_gap":"handler binds arbitrary request fields into a persisted model without an allowlist",
        "sensitive_sink_or_boundary":"user privilege fields persisted to the account record",
        "impact":"a caller may be able to set internal-only account fields",
        "assumptions":["the updated model fields are persisted as shown"]
      }},
      "evidence":[
        {{
          "chunk_id":"chunk-0001",
          "files":["src/profile.py"],
          "rationale":"handler receives external fields and passes the bound model to persistence"
        }}
      ],
      "counter_evidence":[
        "The chunk does not show a field allowlist before persistence.",
        "A serializer outside this chunk may still restrict writable fields."
      ],
      "remediation_direction":"restrict writable fields to an explicit server-side allowlist before persistence"
    }}
  ],
  "rejected_hypotheses":[
    {{
      "title":"Direct object reference in invoice handler",
      "reason":"the chunk shows a user-scoped repository call before the object is returned",
      "evidence":[
        {{
          "chunk_id":"chunk-0001",
          "files":["src/invoices.py"],
          "rationale":"query filters on both invoice id and current user id"
        }}
      ]
    }}
  ],
  "coverage_gaps":[
    {{
      "summary":"authorization policy may be implemented in a different chunk",
      "chunk_ids":["chunk-0001"],
      "reason":"broader-repository-context"
    }}
  ]
}}

Allowed certainty values:
- "suspected"
- "plausible"
- "high-confidence"

Guide metadata:
```json
{guide_json}
```

Guide markdown:
```md
{guide_markdown}
```

Support markdown:
```md
{support_markdown}
```

Relevant system-map context:
```json
{system_map_json}
```

Chunk metadata:
```json
{chunk_json}
```

Chunk contents:
{chunk_contents}
"""


def build_reviewer_merge_prompt(
    guide_json,
    merged_fragment_json,
):
    """Build the AI prompt for guide-level review consolidation."""
    return f"""Return ONLY JSON.
Task: consolidate a guide-level WSTG review result from deterministic chunk-local fragments.

Goals:
- merge duplicates conservatively
- improve naming consistency and final summary quality
- preserve evidence and counter-evidence
- stay candidate-only and evidence-first

Rules:
- Do not invent new findings, evidence, files, or attack-path details.
- Only merge or rewrite items that are already present in the deterministic input.
- Keep certainty values limited to suspected, plausible, or high-confidence.
- Preserve coverage gaps unless they are duplicates or clearly redundant.
- Return only JSON matching the schema below.

JSON schema:
{{
  "summary":"one sentence",
  "candidate_findings":[],
  "rejected_hypotheses":[],
  "coverage_gaps":[]
}}

Guide metadata:
```json
{guide_json}
```

Deterministic merged review fragment:
```json
{merged_fragment_json}
```
"""


def build_reviewer_validation_prompt(
    guide_json,
    input_json,
    audit_json,
    current_output_json,
    evidence_bundle_json,
):
    """Build the AI prompt for review-output validation and correction."""
    return f"""Return ONLY JSON.
Task: validate and, if necessary, minimally correct one WSTG review output.

Goals:
- use the validated repository input and guide metadata as ground truth
- preserve grounded findings and evidence where possible
- remove or repair malformed, duplicate, or unsupported entries
- keep the output candidate-only and within the expected schema

Rules:
- Do not invent new findings, files, evidence, or chunk ids.
- Keep guide metadata and input metadata aligned with the provided guide and repository input.
- Every retained candidate finding must have a valid certainty, a complete attack_path, grounded evidence, at least one counter_evidence note, and remediation_direction.
- Evidence files must belong to the referenced chunk in the repository input.
- If the current output is acceptable, return status "pass" and corrected_output as null.
- If you make corrections, return the full corrected guide output in corrected_output.
- Return only JSON matching the schema below.

JSON schema:
{{
  "status":"pass",
  "summary":"one sentence",
  "issues":[
    {{
      "category":"candidate_findings",
      "message":"one sentence"
    }}
  ],
  "corrected_output": {{
    "status":"pass",
    "summary":"one sentence",
    "guide": {{
      "wstg_id":"WSTG-INPV-20",
      "title":"Testing for Mass Assignment",
      "path":"wstg/07-Input_Validation_Testing/20-Testing_for_Mass_Assignment.md",
      "area":"07-Input_Validation_Testing",
      "support_paths":[]
    }},
    "input": {{
      "root":"/repo",
      "system_map_path":"/repo/system-map.json",
      "routed_chunk_ids":["chunk-0001"],
      "reviewed_chunk_ids":["chunk-0001"],
      "review_depth":"initial"
    }},
    "candidate_findings":[],
    "rejected_hypotheses":[],
    "coverage_gaps":[],
    "metrics": {{
      "routed_chunk_count":1,
      "reviewed_chunk_count":1,
      "candidate_finding_count":0,
      "rejected_hypothesis_count":0,
      "coverage_gap_count":0,
      "expansion_performed":false
    }}
  }}
}}

Allowed status values:
- "pass"
- "corrected"
- "needs_review"

Guide metadata:
```json
{guide_json}
```

Validated repository input:
```json
{input_json}
```

Deterministic audit findings:
```json
{audit_json}
```

Current guide output:
```json
{current_output_json}
```

Evidence bundle:
```json
{evidence_bundle_json}
```
"""
