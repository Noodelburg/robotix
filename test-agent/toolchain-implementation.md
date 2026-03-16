# Technical implementation details for the CoPilot security-first white-box testing toolchain

## 1. Implementation intent

This document turns the design into a concrete implementation approach that is compatible with Copilot CLI, a devcontainer-based execution model, and a white-box, code-first security workflow where exploitability is explored through generated payloads executed with `curl` and related command-line tools.

The implementation goal is not to create a fully autonomous black box. It is to create a controlled, reproducible, policy-constrained test harness around Copilot CLI so that AI workers can inspect code, write focused test artifacts, execute approved probes, and leave a defensible audit trail.

## 2. Technical design decisions

### 2.1 Copilot CLI is the execution substrate
Use Copilot CLI for orchestration and worker execution rather than inventing a separate agent runtime. The toolchain should rely on the current Copilot CLI features that matter most for this use case:

- custom agents for role specialization
- skills for repeatable instructions and helper resources
- hooks for policy enforcement and auditing
- programmatic prompt execution for deterministic worker runs
- permission flags for tools, files, and URLs
- session sharing for run logs and artifact traceability

### 2.2 The filesystem is the system state
The orchestrator should not keep important state only in model context. State should live in run files under a deterministic directory structure. Every major action should be resumable by reading the run directory.

### 2.3 The workflow is staged
Implement the run in stages:

1. run initialization
2. read-only source discovery
3. hypothesis generation
4. active payload generation
5. active payload execution
6. validation
7. final synthesis

A worker should never be allowed to jump directly from vague suspicion to final accepted finding.

### 2.4 Active testing is generated from code findings
The system should not begin with broad fuzzing. The first active probe should exist because code review, configuration review, or dependency review produced a concrete hypothesis.

### 2.5 White-box first, not scanner first
The implementation should behave like a white-box testing harness. Internal artifacts such as middleware, guards, schemas, raw query sinks, file handlers, retry policies, and service clients are the main inputs. Runtime requests are generated from those internal observations, which keeps the active phase focused and makes every payload explainable.

## 3. Repository layout

A practical repository layout is shown below.

```text
.devcontainer/
  devcontainer.json
  Dockerfile
  analysis/devcontainer.json              # optional read-only profile
  active-test/devcontainer.json           # optional active probe profile

.github/
  copilot/
    settings.json
    settings.local.example.json
  copilot-instructions.md
  agents/
    test-orchestrator.agent.md
    code-surface-mapper.agent.md
    security-hypothesis.agent.md
    config-review.agent.md
    exploitability-runner.agent.md
    robustness-runner.agent.md
    worker-validator.agent.md
    orchestrator-validator.agent.md
  hooks/
    10-session-start.json
    20-pretool-policy.json
    30-posttool-audit.json
  skills/
    common-evidence/
      SKILL.md
      evidence-rules.md
      severity-rubric.md
    curl-payload-pack/
      SKILL.md
      payload-template.md
      curl-usage-guidelines.md
    authz-probing/
      SKILL.md
      idor-checklist.md
    injection-probing/
      SKILL.md
      sink-patterns.md
    robustness-probing/
      SKILL.md
      malformed-input-patterns.md

toolchain/
  config/
    policy.yaml
    targets.yaml
    severity-map.yaml
    env-allowlist.txt
    sensitive-paths.txt
    curl-defaults.sh
    copilot-config.template.json
  templates/
    run-manifest.template.json
    worker-task.template.md
    finding.template.json
    final-report.template.md
  scripts/
    bootstrap-copilot-home.sh
    create-run.sh
    run-orchestrator.sh
    run-worker.sh
    run-validator.sh
    run-campaign.sh
    policy-check.sh
    audit-log.sh
    redact-artifacts.sh
    execute-payload-pack.sh
    summarize-findings.py
  runs/
    .gitkeep
```

## 4. Devcontainer design

### 4.1 Base requirements
The devcontainer should include at least:

- Copilot CLI
- `bash`
- `curl`
- `jq`
- `git`
- `ripgrep`
- `python3`
- language-specific build and test tooling for the target repository

Optional but useful tools include `yq`, `openssl`, `httpie`, `grpcurl`, and `websocat` when the target stack requires them.

### 4.2 Security posture of the devcontainer
The devcontainer should be hardened for AI-driven testing:

- run as a non-root user
- default to a restricted network policy
- avoid mounting host secrets directly into the repository tree
- avoid granting Docker socket or cloud credentials unless required
- keep test credentials separate from source files

### 4.3 Two-profile option
If the platform allows multiple devcontainer definitions, use two profiles:

- **analysis profile**: source access, read-only external access, no active target probing
- **active-test profile**: source access plus allowlisted network access to test targets

This reduces the blast radius of routine code review runs.

## 5. Copilot CLI bootstrap and isolation

### 5.1 Use an isolated Copilot home
Set `COPILOT_HOME` inside the devcontainer so the toolchain does not rely on a developer's personal global Copilot state.

Example bootstrap behavior:

```bash
export COPILOT_HOME="$PWD/.toolchain-copilot-home"
mkdir -p "$COPILOT_HOME"
cp toolchain/config/copilot-config.template.json "$COPILOT_HOME/config.json"
```

Why this matters:

- approvals become local to the toolchain environment
- logs stay with the test run
- trusted folders and URL rules are explicit
- the behavior is reproducible in CI or shared devcontainers

### 5.2 Recommended Copilot config template
Use the isolated Copilot config to define safe defaults such as:

```json
{
  "trusted_folders": ["/workspaces/project"],
  "allowed_urls": [
    "https://staging.example.com",
    "https://api.staging.example.com"
  ],
  "denied_urls": [
    "https://prod.example.com",
    "https://*.prod.example.com"
  ]
}
```

Do not commit real target URLs or secrets if the repository is shared. Commit a template and materialize environment-specific values during setup.

### 5.3 Do not rely on content exclusion for CLI security
Copilot content exclusion should not be treated as a protection mechanism for this toolchain because current GitHub documentation says content exclusion does not support Copilot CLI or Copilot coding agent. That means the implementation must keep secrets and excluded content out of the working tree or otherwise outside the trusted path rather than expecting CLI-side policy to hide them.

Practical rule:

- keep secrets outside the repository
- inject them at runtime
- deny reads of known sensitive paths in hooks
- use `--secret-env-vars` in all programmatic runs

## 6. Repository-level Copilot customization

## 6.1 Repository instructions
Create `.github/copilot-instructions.md` with the permanent operating rules for the toolchain, for example:

- this repository contains a white-box security testing toolchain
- all active tests must be scoped to approved targets only
- no production write actions
- every finding requires evidence
- write all generated artifacts under `toolchain/runs/<run-id>/`
- use payload packs and `curl` wrappers for HTTP exploitability testing
- redact secrets and tokens from outputs
- validators may reject unsupported claims

This file is the always-on repository context.

## 6.2 Custom agents
Use custom agents in `.github/agents/` to encode stable worker roles.

### Recommended agents

- `test-orchestrator`
- `code-surface-mapper`
- `security-hypothesis`
- `config-review`
- `exploitability-runner`
- `robustness-runner`
- `worker-validator`
- `orchestrator-validator`

### Example orchestrator agent

```md
---
name: test-orchestrator
description: Plans and coordinates code-first security and robustness test campaigns. Use this agent when a run must be decomposed into worker tasks and later synthesized into a validated final report.
tools: [read, search, edit, execute, agent]
user-invocable: true
---

You are the orchestrator for the CoPilot security-first testing toolchain.

Rules:
1. Read the run manifest first.
2. Build a white-box, code-first plan before authoring any active probe tasks.
3. Create worker task files under toolchain/runs/<run-id>/tasks/.
4. Do not mark a finding as validated until validator artifacts exist.
5. Prefer read-only analysis first, then active exploitability testing, then robustness expansion.
6. All artifacts must be written into the run directory.
```

### Example exploitability agent

```md
---
name: exploitability-runner
description: Converts validated security hypotheses into payload packs and executes focused exploitability checks with curl or protocol-equivalent CLI tools against approved test targets.
tools: [read, search, edit, execute]
user-invocable: false
---

You verify exploitability of white-box hypotheses, not just possibility.

Rules:
1. Read the assigned task file and any referenced hypotheses.
2. Generate payload packs before execution.
3. Use curl-first for HTTP and HTTPS.
4. Record exact commands, headers, bodies, and outputs.
5. Stop if the task would exceed the policy, rate limits, or target allowlist.
6. Write both a human-readable execution report and machine-readable findings.
```

## 6.3 Skills
Use skills for reusable operational behavior rather than duplicating instructions across agents.

### Recommended skills

#### `common-evidence`
Defines evidence thresholds, artifact naming, confidence rules, and validation requirements.

#### `curl-payload-pack`
Explains how to convert a hypothesis into:

- a request definition
- body files
- header files
- expected secure behavior
- expected vulnerable behavior
- a safe execution wrapper

#### `authz-probing`
Provides patterns for IDOR, privilege escalation, missing ownership checks, role confusion, and resource enumeration.

#### `injection-probing`
Provides payload families for SQLi, NoSQLi, command injection, traversal, SSRF, header injection, and template abuse based on observed sinks.

#### `robustness-probing`
Provides boundary-value and malformed-input strategies driven by parser and validator behavior discovered in code.

### Example skill

```md
---
name: curl-payload-pack
description: Generate reproducible payload packs and execute curl-based exploitability tests when a task requires validation of an HTTP or HTTPS security hypothesis.
---

When this skill applies:
- the task references a route, handler, or API endpoint
- a hypothesis includes an HTTP-facing exploit path
- the worker must prove or reject exploitability with reproducible commands

Required outputs:
- payloads/<finding-id>/hypothesis.md
- payloads/<finding-id>/request-01.sh
- payloads/<finding-id>/body-01.json (if needed)
- evidence/<finding-id>/request-01/meta.json
- evidence/<finding-id>/request-01/headers.txt
- evidence/<finding-id>/request-01/body.txt

Execution rules:
1. Use curl unless another CLI protocol tool is explicitly required.
2. Use environment variables for tokens and secrets.
3. Record the exact command form in the payload pack.
4. Store the response and execution metadata.
5. Redact secrets before final reporting.
```

## 7. Hooks and policy enforcement

Hooks are the main enforcement layer that keeps Copilot CLI policy-compliant.

## 7.1 Session-start hook
Use a session-start prompt hook to automatically inject short operating guidance into every session.

Example intent:

- remind the agent that this is a code-first test run
- remind it to read the run manifest first
- remind it to write only under the run directory
- remind it not to target non-allowlisted URLs

Example configuration:

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "type": "prompt",
        "prompt": "Read toolchain/config/policy.yaml and the assigned run manifest before doing anything else. All active probes must target only approved test environments and all artifacts must be written under toolchain/runs/."
      }
    ]
  }
}
```

## 7.2 Pre-tool policy hook
Use a `preToolUse` command hook to enforce the most important rules.

The hook should deny:

- shell commands that are clearly destructive
- writes outside the run directory and explicitly allowed locations
- reads of known secret paths
- `curl` requests to non-allowlisted hosts
- infrastructure mutation commands
- network tools not approved for the current worker

Example hook configuration:

```json
{
  "version": 1,
  "hooks": {
    "preToolUse": [
      {
        "type": "command",
        "bash": "toolchain/scripts/policy-check.sh",
        "timeoutSec": 30
      }
    ]
  }
}
```

Example behavior inside `policy-check.sh`:

- if the tool is `bash`, inspect the requested command
- deny `rm -rf`, `sudo`, `terraform apply`, `kubectl delete`, `aws`, `gcloud`, and similar unless a policy file explicitly permits them
- if the command is `curl`, extract the URL and compare it to `toolchain/config/env-allowlist.txt`
- if the tool is `edit` or `write`, deny writes outside `toolchain/runs/`, `.github/agents/`, `.github/skills/`, and other explicitly approved paths

## 7.3 Post-tool audit hook
Use `postToolUse` to append structured audit entries for every tool execution.

Suggested fields:

- timestamp
- worker name
- run ID
- tool name
- result type
- task ID
- target hostname if applicable
- artifact path if written

These logs are essential for incident review and debugging the toolchain itself.

## 7.4 Optional agent-stop checks
If the installed Copilot CLI version supports it in your environment, add end-of-turn checks that force continuation when required output files are missing. This is useful for making sure workers do not stop before writing the required report and finding files.

## 8. Run directory and file contracts

## 8.1 Run directory
Each run should have a unique directory.

Example:

```text
toolchain/runs/RUN-2026-03-14T120501Z/
  00-manifest.json
  01-system-profile.md
  02-hypotheses.json
  tasks/
    WK-001-surface.task.md
    WK-010-authz-hypothesis.task.md
    WK-020-authz-exploit.task.md
    WK-030-robustness.task.md
  payloads/
    FND-AUTHZ-001/
  evidence/
    FND-AUTHZ-001/
  findings/
    WK-020-authz-exploit.findings.json
  validation/
    WK-020-authz-exploit.validation.md
  reports/
    WK-020-authz-exploit.execution.md
    final-report.md
  logs/
    WK-020-authz-exploit.session.md
    audit.jsonl
```

## 8.2 Run manifest
Suggested `00-manifest.json` fields:

```json
{
  "run_id": "RUN-2026-03-14T120501Z",
  "campaign_type": "security-robustness",
  "mode": "code-first",
  "target_env": "staging",
  "target_base_urls": ["https://api.staging.example.com"],
  "repo_root": ".",
  "active_testing_allowed": true,
  "allowed_protocols": ["https"],
  "allowed_request_rate": "2rps",
  "forbidden_hosts": ["prod.example.com"],
  "test_accounts": ["user-a", "admin-a"],
  "required_outputs": [
    "01-system-profile.md",
    "02-hypotheses.json",
    "reports/final-report.md"
  ]
}
```

## 8.3 Worker task file contract
Use Markdown with YAML frontmatter so both humans and agents can read it easily.

Example `WK-020-authz-exploit.task.md`:

```md
---
run_id: RUN-2026-03-14T120501Z
task_id: WK-020
worker: exploitability-runner
category: authorization
active_testing: true
related_hypotheses:
  - HYP-AUTHZ-003
target_base_url: https://api.staging.example.com
allowed_methods: [GET, POST]
max_request_rate: 2rps
required_outputs:
  - reports/WK-020-authz-exploit.execution.md
  - findings/WK-020-authz-exploit.findings.json
  - validation/WK-020-authz-exploit.validation.md
---

Objective:
Verify whether the order details endpoint allows access to objects owned by a different account.

Code evidence:
- src/orders/controller.ts:88-121
- src/authz/resourceGuard.ts:14-36

Instructions:
1. Generate payload packs for same-user and different-user object access.
2. Execute requests with curl using synthetic tokens.
3. Capture headers, body, status, and execution metadata.
4. Validate whether access control is enforced consistently.
5. Do not exceed the configured rate limit.
```

## 8.4 Findings contract
Use machine-readable findings so validators and later automation can reason over them.

Example `findings/WK-020-authz-exploit.findings.json`:

```json
[
  {
    "finding_id": "FND-AUTHZ-001",
    "title": "Order details endpoint returns another user's order",
    "category": "broken-authorization",
    "severity": "critical",
    "confidence": "high",
    "status": "candidate",
    "cwe": ["CWE-639", "CWE-285"],
    "affected_routes": ["GET /api/orders/{id}"],
    "code_locations": ["src/orders/controller.ts:88-121"],
    "hypothesis_id": "HYP-AUTHZ-003",
    "payload_pack": "payloads/FND-AUTHZ-001/",
    "evidence_paths": [
      "evidence/FND-AUTHZ-001/request-01/meta.json",
      "evidence/FND-AUTHZ-001/request-01/body.txt"
    ],
    "expected_secure_behavior": "return 403 or 404",
    "observed_behavior": "returned 200 with another user's order data",
    "impact": "horizontal privilege escalation and data exposure",
    "suggested_fix": "enforce ownership check in the order details handler or guard layer"
  }
]
```

Validators should update status values to something like `validated`, `rejected`, or `needs-human-review`.

## 9. Payload-pack format

Payload packs are the bridge between code findings and active exploit testing.

Recommended structure:

```text
payloads/FND-AUTHZ-001/
  hypothesis.md
  env.example
  request-01.sh
  request-02.sh
  body-01.json
  expectations.md
```

### `hypothesis.md`
Contains:

- concise weakness statement
- code references
- preconditions
- why the payload should work if the hypothesis is true
- safety note

### `request-01.sh`
Contains a reproducible `curl` invocation using environment variables, never hard-coded secrets.

Example:

```bash
#!/usr/bin/env bash
set -euo pipefail

curl -sS \
  -X GET \
  "$TARGET_BASE_URL/api/orders/$FOREIGN_ORDER_ID" \
  -H "Authorization: Bearer $USER_A_TOKEN" \
  -H "Accept: application/json" \
  "$@"
```

### `expectations.md`
Contains two sections:

- expected secure behavior
- expected vulnerable behavior

This helps validators determine whether the execution result really supports the claim.

## 10. Standard curl execution wrapper

Do not let each worker improvise how requests are executed and captured. Provide a wrapper such as `toolchain/scripts/execute-payload-pack.sh`.

Example execution pattern:

```bash
#!/usr/bin/env bash
set -euo pipefail

RUN_ID="$1"
FINDING_ID="$2"
REQUEST_SCRIPT="$3"
OUT_DIR="toolchain/runs/$RUN_ID/evidence/$FINDING_ID/$(basename "$REQUEST_SCRIPT" .sh)"

mkdir -p "$OUT_DIR"

START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

bash "$REQUEST_SCRIPT" \
  -D "$OUT_DIR/headers.txt" \
  -o "$OUT_DIR/body.txt" \
  -w '{"http_code":%{http_code},"time_total":%{time_total},"size_download":%{size_download},"url_effective":"%{url_effective}"}' \
  > "$OUT_DIR/meta.json"

printf '%s\n' "$START_TS" > "$OUT_DIR/started_at.txt"
```

In practice you may wrap `curl` slightly differently, but the important point is consistent evidence capture.

## 11. Programmatic Copilot CLI execution

## 11.1 Orchestrator run
A programmatic orchestrator run can look like this:

```bash
copilot \
  --agent test-orchestrator \
  --prompt "@toolchain/runs/$RUN_ID/00-manifest.json Create the read-only worker task files for this run." \
  --share "toolchain/runs/$RUN_ID/logs/orchestrator-plan.session.md" \
  --secret-env-vars "USER_A_TOKEN,ADMIN_A_TOKEN" \
  --allow-tool "read" \
  --allow-tool "search" \
  --allow-tool "write(toolchain/runs/**)" \
  --deny-tool "shell" \
  --disable-builtin-mcps
```

This keeps the first phase read-only except for writing run artifacts.

## 11.2 Read-only worker run

```bash
copilot \
  --agent code-surface-mapper \
  --prompt "@toolchain/runs/$RUN_ID/tasks/WK-001-surface.task.md" \
  --share "toolchain/runs/$RUN_ID/logs/WK-001-surface.session.md" \
  --allow-tool "read" \
  --allow-tool "search" \
  --allow-tool "write(toolchain/runs/**)" \
  --deny-tool "shell" \
  --disable-builtin-mcps
```

## 11.3 Active exploitability worker run

```bash
copilot \
  --agent exploitability-runner \
  --prompt "@toolchain/runs/$RUN_ID/tasks/WK-020-authz-exploit.task.md" \
  --share "toolchain/runs/$RUN_ID/logs/WK-020-authz-exploit.session.md" \
  --secret-env-vars "USER_A_TOKEN,ADMIN_A_TOKEN" \
  --allow-tool "read" \
  --allow-tool "search" \
  --allow-tool "write(toolchain/runs/**)" \
  --allow-tool "shell(curl:*)" \
  --deny-tool "shell(rm:*)" \
  --deny-tool "shell(sudo:*)" \
  --deny-tool "shell(terraform:*)" \
  --deny-tool "shell(kubectl:*)" \
  --deny-tool "url(https://prod.example.com)" \
  --disable-builtin-mcps \
  --autopilot
```

This gives the exploit worker enough power to run focused `curl` requests while still restricting unrelated shell activity.

## 11.4 Validator run

```bash
copilot \
  --agent worker-validator \
  --prompt "Validate @toolchain/runs/$RUN_ID/tasks/WK-020-authz-exploit.task.md against @toolchain/runs/$RUN_ID/reports/WK-020-authz-exploit.execution.md and @toolchain/runs/$RUN_ID/findings/WK-020-authz-exploit.findings.json. Update the validation artifact and correct unsupported severity claims." \
  --share "toolchain/runs/$RUN_ID/logs/WK-020-validator.session.md" \
  --allow-tool "read" \
  --allow-tool "search" \
  --allow-tool "write(toolchain/runs/**)" \
  --deny-tool "shell" \
  --disable-builtin-mcps
```

## 12. Campaign runner

Provide a single campaign script such as `toolchain/scripts/run-campaign.sh`.

Pseudo-flow:

```bash
create-run
bootstrap-copilot-home
run-orchestrator read-only-plan
run read-only workers in parallel
run-orchestrator active-plan
run active workers in parallel
run worker validators
run orchestrator validator
summarize findings
render final report
```

### Parallelism
Use shell-level orchestration for deterministic parallel runs. For example, invoke workers with `xargs -P` or a small Python runner. Keep `/fleet` as an optional interactive accelerator, not the backbone of the formal pipeline.

Reason:

- external orchestration is easier to audit
- worker boundaries remain explicit
- retries are simpler
- per-worker permissions stay narrow

## 13. Read-only versus active worker split

The implementation should explicitly classify each worker.

### Read-only workers
Allowed tools:

- read
- search
- write under run directory

Not allowed:

- shell execution
- external URLs unless specifically approved for docs or package metadata

### Active workers
Allowed tools:

- read
- search
- write under run directory
- limited shell patterns such as `curl`, `jq`, and approved wrapper scripts

Not allowed:

- unrestricted shell
- cloud CLIs
- infra mutation commands
- writes outside run directory unless explicitly part of setup

This split is one of the biggest practical safety improvements in the whole design.

## 14. Validation logic

Validators should use explicit acceptance criteria.

### 14.1 Minimum evidence for a validated security finding
Require all of the following:

- route or component identification
- code or config reference
- payload pack path
- exact executed request or command
- captured response or observed behavior
- impact explanation
- remediation direction

### 14.2 Rules for severity
A suggested policy:

- `critical`: exploit proven and impact is account takeover, privilege escalation, major data exposure, or equivalent
- `high`: exploit likely proven with substantial impact but narrower scope
- `medium`: issue is plausible and important but exploit proof or impact is partial
- `low`: confirmed weakness with limited impact
- `informational`: observation or hardening note

### 14.3 Candidate versus validated
Keep the distinction explicit.

- `candidate`: worker believes the issue exists
- `validated`: validator confirms evidence and severity
- `rejected`: evidence does not support the claim
- `needs-human-review`: evidence exists but business impact or risk classification needs manual judgment

## 15. Security controls specific to exploitability testing

Because the user explicitly wants generated payloads to explore exploitability, the implementation must control how that power is used.

### 15.1 Approved targets only
Store the allowed hosts and base URLs in `toolchain/config/targets.yaml` or `env-allowlist.txt`. The pre-tool hook should deny any `curl` request to a hostname outside that list.

### 15.2 Test identities only
Use synthetic accounts and tokens. Never store real credentials in payload files.

### 15.3 Rate limits per task
Include rate limits in the task contract and make the execution wrapper enforce them.

### 15.4 Safe cleanup
If a payload creates resources, include a cleanup script or cleanup instructions in the payload pack.

### 15.5 No implicit escalation to destructive tests
Commands or payloads that could damage data, exhaust resources, or alter infrastructure should require a separate policy mode. The default campaign should stop before those actions.

## 16. Reporting model

The final report should have both human and machine outputs.

### Human-readable final report
Include:

- run scope
- tested target
- methodology summary
- major validated findings
- candidate findings still requiring human follow-up
- robustness observations
- remediation priorities
- retest recommendations
- overall readiness or gate recommendation

### Machine-readable summary
Include:

- counts by severity
- counts by category
- validator outcomes
- duplicate clusters
- unresolved contradictions
- retest backlog items

## 17. Metrics and quality feedback

Track metrics so the toolchain can improve over time.

Suggested metrics:

- number of hypotheses generated
- hypothesis-to-payload conversion rate
- payload-to-validated-finding conversion rate
- false-positive rejection rate
- median time to validate a finding
- categories producing most value
- repeated regressions across runs

These metrics should feed back into agent instructions and skills.

## 18. Rollout plan

### Phase 1: MVP
- read-only mapping
- hypothesis generation
- `curl`-based exploitability testing for HTTP APIs
- worker validators
- final report generation

### Phase 2: robustness expansion
- malformed input libraries
- concurrency and timeout probes
- resilience checks tied to code-discovered weak points

### Phase 3: shift-left
- PR-triggered read-only review
- branch environment exploit retests
- automatic regression packs for previously fixed findings

## 19. Summary

The implementation should be a **structured Copilot CLI toolchain**, not just a prompt collection.

Its defining technical characteristics are:

- isolated Copilot configuration in the devcontainer
- repository-native custom agents, skills, hooks, and instructions
- deterministic run directories and file contracts
- staged execution from source discovery to exploitability to validation
- `curl`-first payload execution for HTTP-facing findings
- strong policy enforcement around shell commands, paths, URLs, and secrets

That combination gives you a practical, auditable, security-first testing system that can grow from deployed-application hardening into a broader SDLC testing capability.

## Suggested references for implementation

- [GitHub Copilot CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)
- [Custom agents configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- [Creating and using custom agents for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli)
- [Creating agent skills for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills)
- [Hooks configuration](https://docs.github.com/en/copilot/reference/hooks-configuration)
- [Configure GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/configure-copilot-cli)
- [Introduction to dev containers](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/adding-a-dev-container-configuration/introduction-to-dev-containers)
