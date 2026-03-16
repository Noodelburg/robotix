# curl usage guidelines

This file captures the basic rules for producing curl-based payloads that are
reproducible and safe to review later.

- Use environment variables for secrets and tokens.
- Make requests reproducible and text-first.
- Capture response headers, body, and metadata for every request.
