# Repository Guide

This document explains what each major directory and file category is for.

## Why This Guide Exists

Some files in this repo are executable. Some are AI instructions. Some are templates. Some are configuration. Some are JSON files that cannot safely contain inline comments.

This guide ties all of that together so you can understand the repo as a whole.

## `.devcontainer/`

Purpose:

- define the preferred runtime environment for the repo

Key contents:

- `devcontainer.json`: main devcontainer definition
- `Dockerfile`: base image and installed tools
- `analysis/devcontainer.json`: lighter profile intended for source analysis
- `active-test/devcontainer.json`: profile intended for active probe workflows

Why it matters:

- the shell scripts assume a Linux-like environment
- this is the easiest way to get a consistent setup

## `.github/copilot-instructions.md`

Purpose:

- always-on repository instructions for Copilot behavior

What it encodes:

- where artifacts must be written
- why read-only discovery comes before active testing
- why findings require evidence

## `.github/agents/`

Purpose:

- role-specific prompt files for the major actors in the workflow

What an agent is:

- an agent is a reusable instruction set for a specific role, such as orchestrator or validator

Current agents:

- `test-orchestrator`: plans and coordinates the run
- `code-surface-mapper`: inventories code paths and risky surfaces
- `security-hypothesis`: turns evidence into candidate weaknesses
- `config-review`: inspects configuration and dependency artifacts
- `exploitability-runner`: turns hypotheses into active probes
- `robustness-runner`: explores malformed-input and boundary variants
- `worker-validator`: validates individual worker outputs
- `orchestrator-validator`: validates the combined campaign result

## `.github/skills/`

Purpose:

- reusable instruction bundles for repeated behaviors

What a skill is:

- a skill is narrower than an agent
- it teaches a recurring pattern, such as how to collect evidence or build a payload pack

Current skill families:

- `common-evidence`: what makes a finding credible
- `curl-payload-pack`: how to structure reproducible HTTP test payloads
- `authz-probing`: authorization-focused probing patterns
- `injection-probing`: sink-driven injection patterns
- `robustness-probing`: malformed input and parser stress patterns

Supporting skill docs:

- these include checklists, reference notes, and short helper documents used by the skill family

## `.github/hooks/`

Purpose:

- define policy and audit checks around tool usage

Hook types in this repo:

- session-start hook: injects run discipline at the start of a session
- pre-tool hook: enforces policy before a tool runs
- post-tool hook: records audit data after a tool runs

Why it matters:

- this is where the repo tries to keep active testing inside approved boundaries

## `.github/copilot/`

Purpose:

- hold Copilot CLI configuration examples

Important note:

- these files are JSON and are intentionally left without inline comments
- they are explained here instead of being annotated directly

Files:

- `settings.json`: example trusted folders and allowed/denied URLs
- `settings.local.example.json`: local override example

## `toolchain/config/`

Purpose:

- define the policy and environment assumptions the scripts rely on

Files:

- `policy.yaml`: main policy, denied command patterns, approved write roots, and redaction patterns
- `targets.yaml`: example approved targets for active testing
- `severity-map.yaml`: category-to-severity normalization map
- `curl-defaults.sh`: shared curl-related runtime defaults
- `env-allowlist.txt`: host allowlist used by policy checks
- `sensitive-paths.txt`: path patterns treated as sensitive by policy checks
- `copilot-config.template.json`: template Copilot config copied into isolated `COPILOT_HOME`

Important note about comments:

- YAML and shell files support comments, so they are annotated inline
- JSON and plain text files are explained here because inline comments would either break the format or be ambiguous for the scripts consuming them

## `toolchain/templates/`

Purpose:

- provide repeatable starting files for run artifacts

Files:

- `run-manifest.template.json`: starter metadata for a run
- `worker-task.template.md`: starter task shape for workers
- `finding.template.json`: starter machine-readable finding shape
- `final-report.template.md`: starter human-readable final report shape

Why templates matter:

- they keep runs consistent
- they make it easier for orchestrators, workers, and validators to speak through shared file contracts

## `toolchain/scripts/`

Purpose:

- implement the current helper workflow

Main lifecycle scripts:

- `bootstrap-copilot-home.sh`
- `create-run.sh`
- `run-orchestrator.sh`
- `run-worker.sh`
- `run-validator.sh`
- `run-campaign.sh`

Execution and support scripts:

- `execute-payload-pack.sh`
- `policy-check.sh`
- `audit-log.sh`
- `redact-artifacts.sh`
- `summarize-findings.py`

Why these are heavily commented:

- they are the most "code-like" layer of the repo
- a beginner needs to understand how paths, environment variables, and generated artifacts fit together

## `toolchain/runs/`

Purpose:

- hold per-run generated output

This is the system of record for a run.

Typical contents:

- manifest
- system profile
- hypotheses
- tasks
- payloads
- evidence
- findings
- validation
- reports
- logs

## `docs/`

Purpose:

- explain the repo at different levels of depth

Suggested reading order:

1. `README.md`
2. `getting-started.md`
3. `usage-guide.md`
4. `repository-guide.md`
5. `troubleshooting.md`
6. `technical-reference.md`

## Why Some Files Are Not Commented Inline

Some important files are JSON or plain-text lists.

Examples:

- `.github/copilot/settings.json`
- `toolchain/config/copilot-config.template.json`
- `toolchain/templates/run-manifest.template.json`
- `toolchain/templates/finding.template.json`
- `toolchain/config/env-allowlist.txt`
- `toolchain/config/sensitive-paths.txt`

These are explained in documentation instead of being commented inline because:

- JSON comments would make the files invalid or less portable
- plain-text lists are consumed directly by shell scripts that do not currently ignore comment syntax
