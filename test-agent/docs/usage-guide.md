# Usage Guide

This guide explains how to use each current helper script and what output to expect.

## Important Context

Most scripts in this repo are designed for a Linux-like shell environment. If your host machine is missing `bash` or `python3`, use the devcontainer instead.

## Standard Flow

The safest way to think about the current workflow is:

1. bootstrap isolated Copilot configuration
2. create a run
3. create task files
4. prepare worker artifacts
5. optionally execute or refine those tasks with real Copilot agent runs
6. validate and summarize

## `bootstrap-copilot-home.sh`

Path: [toolchain/scripts/bootstrap-copilot-home.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\bootstrap-copilot-home.sh)

Purpose:

- create an isolated `COPILOT_HOME`
- copy the template Copilot config into it

Usage:

```bash
toolchain/scripts/bootstrap-copilot-home.sh
```

Output:

- prints the `COPILOT_HOME` path

## `create-run.sh`

Path: [toolchain/scripts/create-run.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\create-run.sh)

Purpose:

- create a new run workspace
- create the standard directory layout
- write starter manifest/profile/hypothesis artifacts

Usage:

```bash
toolchain/scripts/create-run.sh
toolchain/scripts/create-run.sh RUN-EXAMPLE-001
```

Output:

- prints the run ID

Files created:

- `00-manifest.json`
- `01-system-profile.md`
- `02-hypotheses.json`
- `tasks/`, `payloads/`, `evidence/`, `findings/`, `validation/`, `reports/`, `logs/`

## `run-orchestrator.sh`

Path: [toolchain/scripts/run-orchestrator.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\run-orchestrator.sh)

Purpose:

- create starter task files for a run phase
- write an orchestrator session log

Usage:

```bash
toolchain/scripts/run-orchestrator.sh <run-id> read-only-plan
toolchain/scripts/run-orchestrator.sh <run-id> active-plan
```

Current read-only outputs:

- `WK-001-surface-map.task.md`
- `WK-010-hypothesis-generation.task.md`

Current active outputs:

- `WK-020-exploitability.task.md`
- `WK-030-robustness.task.md`

## `run-worker.sh`

Path: [toolchain/scripts/run-worker.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\run-worker.sh)

Purpose:

- prepare output files for a worker task

Usage:

```bash
toolchain/scripts/run-worker.sh <run-id> <task-file>
```

Example:

```bash
toolchain/scripts/run-worker.sh RUN-2026-03-14T120501Z toolchain/runs/RUN-2026-03-14T120501Z/tasks/WK-001-surface-map.task.md
```

What it creates:

- `logs/<task>.session.md`
- `reports/<task>.execution.md`
- `findings/<task>.findings.json`

Important:

- this does not yet run a real Copilot worker
- it prepares the files a later worker run would fill in

## `run-validator.sh`

Path: [toolchain/scripts/run-validator.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\run-validator.sh)

Purpose:

- prepare a validation artifact for a task

Usage:

```bash
toolchain/scripts/run-validator.sh <run-id> <task-slug>
```

Example:

```bash
toolchain/scripts/run-validator.sh RUN-2026-03-14T120501Z WK-020-exploitability
```

What it creates:

- `validation/<task-slug>.validation.md`

## `run-campaign.sh`

Path: [toolchain/scripts/run-campaign.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\run-campaign.sh)

Purpose:

- run the current MVP bootstrap flow end to end

Usage:

```bash
toolchain/scripts/run-campaign.sh
toolchain/scripts/run-campaign.sh RUN-EXAMPLE-001
```

What it currently does:

1. creates a run
2. bootstraps isolated Copilot config
3. creates read-only tasks
4. prepares worker artifacts for those tasks
5. writes a starter final report

## `execute-payload-pack.sh`

Path: [toolchain/scripts/execute-payload-pack.sh](C:\Users\attil\Desktop\test-agent\toolchain\scripts\execute-payload-pack.sh)

Purpose:

- execute a request script from a payload pack
- capture response headers, body, and normalized metadata

Usage:

```bash
toolchain/scripts/execute-payload-pack.sh <run-id> <finding-id> <request-script>
```

Outputs:

- `evidence/<finding-id>/<request-name>/headers.txt`
- `evidence/<finding-id>/<request-name>/body.txt`
- `evidence/<finding-id>/<request-name>/meta.json`

## `summarize-findings.py`

Path: [toolchain/scripts/summarize-findings.py](C:\Users\attil\Desktop\test-agent\toolchain\scripts\summarize-findings.py)

Purpose:

- scan the run's findings JSON files
- aggregate counts by severity, status, and category
- write a machine-readable summary

Usage:

```bash
python3 toolchain/scripts/summarize-findings.py toolchain/runs/<run-id>
```

Output:

- `reports/summary.json`

## Supporting Scripts

### `policy-check.sh`

Used by the pre-tool hook to deny obvious unsafe behavior, especially:

- destructive shell commands
- non-allowlisted curl hosts
- reads of sensitive paths

### `audit-log.sh`

Used by the post-tool hook to append tool execution records into `logs/audit.jsonl`.

### `redact-artifacts.sh`

Used to scrub common token and secret patterns from text artifacts before final sharing.

## Recommended Learning Order

If you are unfamiliar with the repo, learn the scripts in this order:

1. `create-run.sh`
2. `run-orchestrator.sh`
3. `run-worker.sh`
4. `run-campaign.sh`
5. `execute-payload-pack.sh`
6. `policy-check.sh`
7. `summarize-findings.py`
