---
name: curl-payload-pack
description: Generate reproducible payload packs and execute curl-based exploitability tests.
---

How this skill is used: attach it when a hypothesis needs to become a
reproducible HTTP-focused payload pack and evidence capture flow.

Use this skill when a hypothesis maps to an HTTP or HTTPS interface.

Required outputs:
- `payloads/<finding-id>/hypothesis.md`
- `payloads/<finding-id>/request-01.sh`
- request body or header files if needed
- evidence files captured through the execution wrapper
