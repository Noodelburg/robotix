# Troubleshooting

This guide covers the most likely beginner issues with the current scaffold.

## `bash` is missing or does not work

What it means:

- your host machine is not providing the Linux-like shell environment the scripts expect

What to do:

- open the repository in the devcontainer
- rerun the commands there instead of from the host shell

## `python3` is missing

What it means:

- helper scripts such as `summarize-findings.py`, `audit-log.sh`, `redact-artifacts.sh`, and `execute-payload-pack.sh` rely on Python

What to do:

- use the devcontainer
- or install a compatible Python runtime in the environment where you are executing the scripts

## A policy check denies a command

What it means:

- `policy-check.sh` believes the command is unsafe or outside the current allowlist

Common causes:

- a `curl` target host is not in `env-allowlist.txt`
- the command contains a denied shell pattern
- the action references a sensitive path pattern

What to inspect:

- [toolchain/config/policy.yaml](C:\Users\attil\Desktop\test-agent\toolchain\config\policy.yaml)
- [toolchain/config/env-allowlist.txt](C:\Users\attil\Desktop\test-agent\toolchain\config\env-allowlist.txt)
- [toolchain/config/sensitive-paths.txt](C:\Users\attil\Desktop\test-agent\toolchain\config\sensitive-paths.txt)

## I ran `run-worker.sh` and it did not actually run an agent

That is expected today.

What the script currently does:

- prepares session, report, and findings artifacts

What it does not yet do:

- invoke a real Copilot worker automatically

This repo is currently an MVP scaffold, so some runner scripts create the structure of a workflow rather than fully driving the whole workflow.

## I see placeholder data in reports

That is also expected in the current scaffold.

Examples:

- "pending discovery"
- empty hypotheses arrays
- empty findings files
- "replace with validator output" notes

These are starter values meant to be replaced later by a real orchestrator/worker/validator execution path.

## I do not know whether I should edit targets or policy

Use this rule:

- edit `targets.yaml` when the approved environments themselves are changing
- edit `policy.yaml` when the rules or enforcement behavior are changing

If you are unsure, start by reading [docs/repository-guide.md](C:\Users\attil\Desktop\test-agent\docs\repository-guide.md).

## How do I inspect what a run produced?

Go to:

```text
toolchain/runs/<run-id>/
```

Check these first:

- `00-manifest.json`
- `tasks/`
- `reports/`
- `findings/`
- `validation/`
- `logs/`

## The README says use the devcontainer. Do I really need to?

If your host already has a compatible bash/Python environment, maybe not.

But for a beginner, the safest answer is yes, because:

- the scripts were written with a Linux-like environment in mind
- the repo's preferred runtime is the devcontainer
- it avoids a lot of environment-specific confusion
