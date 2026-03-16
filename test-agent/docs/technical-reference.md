# Technical Reference

This document is the maintainer-focused companion to the beginner docs.

If you are new to the repository, start with:

- [README.md](C:\Users\attil\Desktop\test-agent\README.md)
- [docs/getting-started.md](C:\Users\attil\Desktop\test-agent\docs\getting-started.md)
- [docs/usage-guide.md](C:\Users\attil\Desktop\test-agent\docs\usage-guide.md)

This reference explains how the repository is organized, how the current implementation behaves, and what maintainers should understand before extending it.

## 1. Architecture overview

The repository is organized around four layers:

1. runtime environment
2. Copilot customization
3. execution contracts
4. policy and evidence controls

The canonical visual overview lives in the `Architecture overview` section of [README.md](C:\Users\attil\Desktop\test-agent\README.md). This keeps the technical reference focused on contracts and implementation details instead of repeating diagrams here.

## 2. Runtime environment

### Devcontainer files

- [.devcontainer/devcontainer.json](C:\Users\attil\Desktop\test-agent\.devcontainer\devcontainer.json)
- [.devcontainer/Dockerfile](C:\Users\attil\Desktop\test-agent\.devcontainer\Dockerfile)
- [.devcontainer/analysis/devcontainer.json](C:\Users\attil\Desktop\test-agent\.devcontainer\analysis\devcontainer.json)
- [.devcontainer/active-test/devcontainer.json](C:\Users\attil\Desktop\test-agent\.devcontainer\active-test\devcontainer.json)

The base container installs a minimal Linux toolchain suitable for the scripts in this repo. The analysis and active-test definitions are currently light wrappers, but they establish the intended split between source analysis and active target probing.

## 3. Copilot customization layer

### Repository instructions

[.github/copilot-instructions.md](C:\Users\attil\Desktop\test-agent\.github\copilot-instructions.md) defines always-on rules:

- write run artifacts under `toolchain/runs`
- prefer read-only discovery before active testing
- only target approved environments
- require evidence for findings
- redact sensitive values

### Agents

The custom agent files under [.github/agents](C:\Users\attil\Desktop\test-agent\.github\agents) split responsibilities across orchestrator, discovery, exploitability, robustness, and validation roles.

| Agent | Purpose |
| --- | --- |
| `test-orchestrator` | plans campaign phases and creates worker tasks |
| `code-surface-mapper` | maps handlers, routes, sinks, and trust boundaries |
| `security-hypothesis` | turns source evidence into testable hypotheses |
| `config-review` | reviews dependencies and runtime/deployment config |
| `exploitability-runner` | generates payloads and runs active checks |
| `robustness-runner` | extends suspicious signals into resilience probes |
| `worker-validator` | validates task outputs and severity claims |
| `orchestrator-validator` | validates campaign-wide conclusions |

### Skills

The skills under [.github/skills](C:\Users\attil\Desktop\test-agent\.github\skills) are the reusable instruction layer. They intentionally avoid duplicating full agent prompts and instead provide focused guidance for evidence, payload construction, authorization testing, injection testing, and malformed-input probing.

## 4. Configuration layer

### Policy and allowlists

- [toolchain/config/policy.yaml](C:\Users\attil\Desktop\test-agent\toolchain\config\policy.yaml)
- [toolchain/config/env-allowlist.txt](C:\Users\attil\Desktop\test-agent\toolchain\config\env-allowlist.txt)
- [toolchain/config/sensitive-paths.txt](C:\Users\attil\Desktop\test-agent\toolchain\config\sensitive-paths.txt)

These files express the intended security boundary. They tell the toolchain where it may write, which command patterns are forbidden, which hosts are approved for active probes, and which local paths should be treated as sensitive.

### Target and severity configuration

- [toolchain/config/targets.yaml](C:\Users\attil\Desktop\test-agent\toolchain\config\targets.yaml)
- [toolchain/config/severity-map.yaml](C:\Users\attil\Desktop\test-agent\toolchain\config\severity-map.yaml)
- [toolchain/config/curl-defaults.sh](C:\Users\attil\Desktop\test-agent\toolchain\config\curl-defaults.sh)
- [toolchain/config/copilot-config.template.json](C:\Users\attil\Desktop\test-agent\toolchain\config\copilot-config.template.json)

`targets.yaml` captures approved environments. `severity-map.yaml` provides a normalization layer for reporting. `curl-defaults.sh` centralizes request defaults, and the Copilot config template is intended for an isolated toolchain-specific Copilot home.

## 5. Template contracts

The repository uses file templates to keep runs deterministic and machine-readable.

- [toolchain/templates/run-manifest.template.json](C:\Users\attil\Desktop\test-agent\toolchain\templates\run-manifest.template.json)
- [toolchain/templates/worker-task.template.md](C:\Users\attil\Desktop\test-agent\toolchain\templates\worker-task.template.md)
- [toolchain/templates/finding.template.json](C:\Users\attil\Desktop\test-agent\toolchain\templates\finding.template.json)
- [toolchain/templates/final-report.template.md](C:\Users\attil\Desktop\test-agent\toolchain\templates\final-report.template.md)

### Contract expectations

The most important contract details are:

- the manifest is the root of truth for a run
- tasks use Markdown with YAML frontmatter
- findings are machine-readable JSON arrays
- reports remain human-readable Markdown
- validation output is explicit and separate from worker findings

## 6. Script behavior

### `bootstrap-copilot-home.sh`

[toolchain/scripts/bootstrap-copilot-home.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\bootstrap-copilot-home.sh) creates an isolated `COPILOT_HOME` and copies the template config into it. This keeps the toolchain independent from a developer's personal Copilot state.

### `create-run.sh`

[toolchain/scripts/create-run.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\create-run.sh) generates the run directory tree and writes:

- `00-manifest.json`
- `01-system-profile.md`
- `02-hypotheses.json`

It also creates all standard artifact directories under the run.

### `run-orchestrator.sh`

[toolchain/scripts/run-orchestrator.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\run-orchestrator.sh) writes starter task files based on the requested phase.

Current phase behavior:

- `read-only-plan` creates `WK-001-surface-map.task.md` and `WK-010-hypothesis-generation.task.md`
- `active-plan` creates `WK-020-exploitability.task.md` and `WK-030-robustness.task.md`

This script currently serves as a bootstrap planner. In a fully wired environment, a Copilot CLI orchestrator agent would refine or replace these tasks.

### `run-worker.sh`

[toolchain/scripts/run-worker.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\run-worker.sh) creates:

- a worker session log
- a matching execution report
- an empty findings JSON file

It does not yet execute Copilot CLI directly. Instead, it prepares deterministic artifacts that a worker run can fill in.

### `run-validator.sh`

[toolchain/scripts/run-validator.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\run-validator.sh) creates a validation record for a task slug. Like the worker runner, it is a contract-preserving placeholder for later integration.

### `run-campaign.sh`

[toolchain/scripts/run-campaign.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\run-campaign.sh) wires the current MVP together:

1. creates a run
2. bootstraps the Copilot home
3. plans the read-only phase
4. prepares artifacts for the two read-only tasks
5. writes an initialized final report

### `policy-check.sh`

[toolchain/scripts/policy-check.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\policy-check.sh) is the main enforcement script referenced by the pre-tool hook.

It currently checks:

- forbidden shell fragments such as `rm -rf`, `sudo`, `terraform apply`, and `kubectl delete`
- `curl` targets against the host allowlist
- read attempts against configured sensitive path patterns

### `audit-log.sh`

[toolchain/scripts/audit-log.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\audit-log.sh) appends structured JSON lines to `logs/audit.jsonl` when the surrounding environment exports the expected Copilot hook variables.

### `redact-artifacts.sh`

[toolchain/scripts/redact-artifacts.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\redact-artifacts.sh) recursively redacts bearer tokens and common secret-like environment assignments in text files.

### `execute-payload-pack.sh`

[toolchain/scripts/execute-payload-pack.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\execute-payload-pack.sh) is the most execution-oriented script in the repo. It:

1. loads shared curl defaults
2. creates an evidence directory for the request
3. executes the request script with response capture flags
4. writes response headers and body
5. creates a normalized `meta.json`

The payload execution path is captured in the architectural overview in [README.md](C:\Users\attil\Desktop\test-agent\README.md).

### `summarize-findings.py`

[toolchain/scripts/summarize-findings.py](C:\Users\attil\Desktop\test-agent\toolchain\scripts\summarize-findings.py) scans the run's `findings/` directory, aggregates counts by severity, status, and category, and writes `reports/summary.json`.

## 7. Hook model

The hook JSON files under [.github/hooks](C:\Users\attil\Desktop\test-agent\.github\hooks) map directly to the policy and audit approach:

- `10-session-start.json` injects run discipline at session start
- `20-pretool-policy.json` calls the policy enforcement script
- `30-posttool-audit.json` calls the audit logger

The hook and policy flow is also represented in the architectural overview in [README.md](C:\Users\attil\Desktop\test-agent\README.md).

## 8. Run directory design

Each run lives in `toolchain/runs/<run-id>/`.

A complete run is intended to look like this:

```text
toolchain/runs/RUN-.../
  00-manifest.json
  01-system-profile.md
  02-hypotheses.json
  tasks/
  payloads/
  evidence/
  findings/
  validation/
  reports/
  logs/
```

### Why this matters

- runs are resumable
- artifacts survive across agent calls
- validators can inspect worker output after the fact
- final reporting can be regenerated from disk state

## 9. End-to-end execution model

The repository is intentionally staged rather than autonomous. In the current repo, the initialization and task preparation steps are implemented directly in scripts. The deeper analysis, active execution by Copilot workers, and validator reasoning are represented as explicit contracts and placeholders so they can be wired into a real Copilot CLI environment later.

## 10. Current limitations

Maintainers should be aware of the present boundaries:

- the repository is an MVP scaffold, not a finished autonomous product
- the worker and validator runner scripts prepare artifacts but do not yet invoke Copilot CLI directly
- the scripts assume a Linux-like runtime with `bash` and `python3`
- the target definitions and allowlists are examples and must be customized before real use
- the policy model is intentionally conservative and string-pattern based

## 11. Recommended extension points

The most natural next enhancements are:

1. wire `run-worker.sh` and `run-validator.sh` to real Copilot CLI invocations
2. replace example target URLs with environment-specific configuration materialization
3. enrich payload pack generation for more vulnerability classes
4. make validators update finding status automatically
5. add CI entrypoints and regression retest workflows

## 12. Related source documents

- [docs/getting-started.md](C:\Users\attil\Desktop\test-agent\docs\getting-started.md)
- [docs/usage-guide.md](C:\Users\attil\Desktop\test-agent\docs\usage-guide.md)
- [docs/repository-guide.md](C:\Users\attil\Desktop\test-agent\docs\repository-guide.md)
- [docs/troubleshooting.md](C:\Users\attil\Desktop\test-agent\docs\troubleshooting.md)
- [toolchain-overview.md](C:\Users\attil\Desktop\test-agent\toolchain-overview.md)
- [toolchain-implementation.md](C:\Users\attil\Desktop\test-agent\toolchain-implementation.md)
- [README.md](C:\Users\attil\Desktop\test-agent\README.md)
