# Sink patterns

This file lists the kinds of risky sinks that should steer payload generation
for injection-oriented testing.

- SQL or NoSQL raw queries
- shell execution
- file path concatenation
- outbound URL fetches
- template rendering
