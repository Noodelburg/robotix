# White-box security testing toolchain instructions

This file is the repository-wide baseline guidance for Copilot. Think of it as
the always-on rule set that applies no matter which specific agent or skill is used.

- Treat this repository as a security-first, white-box, code-first testing toolchain.
- Read the run manifest before creating tasks or reports for a run.
- Write generated run artifacts only under `toolchain/runs/<run-id>/`.
- Prefer read-only discovery before active testing.
- Only generate active probes for approved targets.
- Use payload packs and the execution wrapper for HTTP exploitability testing.
- Every finding must include evidence, expected secure behavior, observed behavior, and remediation guidance.
- Redact secrets, tokens, and sensitive values before final reporting.
- Validators can downgrade, reject, or mark findings as needing human review.
