# Simple Source Review Toolchain

This is a much smaller, Python-first source review flow that lives alongside the
larger `toolchain/` scaffold.

It is designed to do one thing well:

1. review a repository's source code for simple security-focused patterns
2. record structured findings
3. generate human-readable test specs from those findings
4. generate curl confirmation templates when a finding looks HTTP/API-related

## How This Differs From `toolchain/`

The main `toolchain/` directory is a broader scaffold built around a richer
orchestrator/worker/validator model and Copilot-oriented repository structure.

This `simple_toolchain/` version is intentionally smaller:

- Python-first instead of shell-first
- script-driven instead of Copilot-agent-driven
- focused on source review plus test generation
- no hooks, skills, or policy layers
- no writes into the target repository by default

## Who This Is For

Use this if you want:

- a compact starting point
- readable Python code
- a repository reviewer that works on arbitrary repo paths
- structured findings and generated test ideas without the full scaffold

## What It Looks For

The worker uses deterministic heuristic checks for:

- dangerous shell execution
- raw SQL or query-string construction
- path traversal or unsafe file path construction
- outbound URL fetch / SSRF-like sinks
- weak auth or auth-missing route patterns when obvious from context
- debug or error leakage markers
- hardcoded secrets and token-like literals
- unsafe deserialization markers

This is heuristic review, not deep semantic analysis.

## CLI Usage

Run it with:

```bash
python simple_toolchain/run_review.py --repo <path-to-target-repo>
```

Optional arguments:

- `--output-root` default: `simple_toolchain/runs`
- `--run-id` optional explicit run ID
- `--max-files` default: `250`
- `--max-file-bytes` default: `200000`

Example:

```bash
python simple_toolchain/run_review.py --repo . --run-id demo-run
```

## Output Layout

Each run writes to:

```text
simple_toolchain/runs/<run-id>/
  manifest.json
  source-index.json
  findings.json
  findings.md
  tests/
    FND-001.test.md
    FND-001-confirm.sh   # only for HTTP/API-confirmable findings
  logs/
    orchestrator.log
    worker.log
```

## What "Generated Tests" Means Here

This simplified toolchain does not try to guess and write framework-specific
unit tests into the target repository.

Instead, it generates:

- a Markdown test spec for every finding
- a curl confirmation template when the finding looks like it may be verified
  through an HTTP/API interaction

That keeps the output portable across languages and repositories.

## Limitations

- heuristic, not full semantic understanding
- security-focused only
- no writes into the target repo by default
- curl confirmation files may need manual adaptation
- line numbers and route inference are best-effort
