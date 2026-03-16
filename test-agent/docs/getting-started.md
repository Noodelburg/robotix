# Getting Started

This guide is for someone who is new to this repository and wants to understand the basics before changing anything.

## What This Toolchain Is

The toolchain is a structured workflow for AI-assisted testing.

Instead of asking an AI to randomly probe an application, it tries to work in a safer order:

1. inspect code and configuration
2. identify likely risks
3. turn those risks into controlled tests
4. collect evidence
5. validate the evidence before trusting the result

## Terms You Will See Everywhere

### Devcontainer

A devcontainer is the preferred runtime for this repo. It gives you a Linux-like environment with the tools the shell scripts expect.

### Copilot CLI

This is the AI execution environment the repo is designed around. The repository includes instructions, agents, skills, and hooks intended to shape how Copilot behaves.

### Run

A run is one complete execution workspace for a testing session. Every run gets its own directory under `toolchain/runs/<run-id>/`.

### Run manifest

The manifest is the root metadata file for a run. It records the run ID, target environment, allowed protocols, required outputs, and related scope.

### Task file

A task file is a Markdown file that tells a worker what to do. The orchestrator creates these files.

### Payload pack

A payload pack is the bundle of files used to express how a security hypothesis should be tested. It usually includes a hypothesis description, one or more request scripts, and any body/header files needed to reproduce the probe.

### Validator

A validator checks whether a worker's claim is supported by evidence. In this repo, validators are separate roles so the same component that generates a claim is not the only one deciding whether it is trustworthy.

## What Environment Should You Use?

Use the devcontainer if you can.

Why:

- the scripts are bash-oriented
- the repository expects Linux-style tooling
- some Windows host setups do not provide working `bash` or `python3`

If you try to run the repo directly on a host without the expected tools, you may see missing-command errors or shell compatibility problems.

## Your First Read Path

If you are starting from zero, use this order:

1. Read [README.md](C:\Users\attil\Desktop\test-agent\README.md).
2. Skim [docs/repository-guide.md](C:\Users\attil\Desktop\test-agent\docs\repository-guide.md).
3. Review [toolchain/config/policy.yaml](C:\Users\attil\Desktop\test-agent\toolchain\config\policy.yaml).
4. Review [toolchain/config/targets.yaml](C:\Users\attil\Desktop\test-agent\toolchain\config\targets.yaml).
5. Follow the steps in [docs/usage-guide.md](C:\Users\attil\Desktop\test-agent\docs\usage-guide.md).

## First Run Walkthrough

### Step 1: Bootstrap isolated Copilot state

Run:

```bash
toolchain/scripts/bootstrap-copilot-home.sh
```

What it does:

- creates `.toolchain-copilot-home` in the repo
- copies the Copilot config template into that directory
- prints the `COPILOT_HOME` path

Why it matters:

- it keeps the toolchain's Copilot settings separate from a developer's personal setup

### Step 2: Create a run

Run:

```bash
toolchain/scripts/create-run.sh
```

What it does:

- creates a new run directory under `toolchain/runs/`
- writes a starter manifest
- writes starter files for system profile and hypotheses

What files appear:

```text
toolchain/runs/<run-id>/
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

### Step 3: Create starter tasks

Run:

```bash
toolchain/scripts/run-orchestrator.sh <run-id> read-only-plan
```

What it does:

- creates starter task files for the read-only phase
- writes an orchestrator session log

At the MVP stage, this script is acting as a deterministic bootstrap planner.

### Step 4: Prepare worker artifacts

Run:

```bash
toolchain/scripts/run-worker.sh <run-id> toolchain/runs/<run-id>/tasks/WK-001-surface-map.task.md
toolchain/scripts/run-worker.sh <run-id> toolchain/runs/<run-id>/tasks/WK-010-hypothesis-generation.task.md
```

What it does:

- creates a log file for each task
- creates a starter execution report
- creates an empty findings JSON file

This is still scaffold behavior today. The script is preparing the files that a real agent-driven worker execution would later fill in.

### Step 5: Understand what is still missing

At the current stage, the repo prepares the structure of a campaign, but it does not fully automate every phase.

Specifically:

- workers are not yet invoked directly by the helper runner scripts
- validators are not yet automatically driven through the helper runner scripts
- example targets need real customization before you do meaningful testing

## What To Read Next

- [docs/usage-guide.md](C:\Users\attil\Desktop\test-agent\docs\usage-guide.md) for command-by-command usage
- [docs/repository-guide.md](C:\Users\attil\Desktop\test-agent\docs\repository-guide.md) for file and directory meanings
- [docs/troubleshooting.md](C:\Users\attil\Desktop\test-agent\docs\troubleshooting.md) if your environment does not behave as expected
