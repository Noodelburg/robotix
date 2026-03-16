# CoPilot security-first white-box testing toolchain

## Purpose

This document expands the original CoPilot testing-toolchain concept into a security-first, robustness-focused, white-box AI testing system designed to run with Copilot CLI inside a devcontainer that has access to the source code and approved test environments.

The key design choice is that the toolchain is **white box and code first**. It does not start with broad black-box scanning. It starts by reading source code, configuration, API contracts, dependency manifests, deployment descriptors, and existing tests to understand the real attack surface. From that understanding it generates focused hypotheses about weaknesses, turns those hypotheses into test payloads, and then validates exploitability against an approved target by executing reproducible command-line requests, primarily with `curl` and protocol-equivalent tools when HTTP is not enough.

The MVP still supports testing an already deployed application, but it does so from a source-aware position rather than as a generic scanner. That keeps the system more precise, more explainable, and more useful for remediation.

## Design goals

### 1. Security is the primary concern
The toolchain should preferentially discover vulnerabilities that create real business risk: broken authentication, broken authorization, injection flaws, data leakage, insecure configuration, insecure dependencies, unsafe file handling, SSRF, path traversal, weak session handling, unsafe error handling, and missing rate or abuse controls.

### 2. Robustness is tested where the code indicates weakness
The system should probe boundary conditions, malformed input handling, retry logic, timeout behavior, concurrency stress points, dependency failure handling, and data-shape mismatches. Robustness testing should be driven by code findings and architectural signals, not by random noise alone.

### 3. Evidence must outrank model confidence
A finding is not valuable because an LLM believes it is likely. A finding is valuable when the system can point to code locations, explain the hypothesis, show the generated payload, record the exact command used, preserve the response or behavior, and then survive validation.

### 4. Safe by default
The toolchain must assume that the AI itself can create risk. Its execution model therefore needs containment, least privilege, path and URL allowlists, strong logging, redaction, and human approval for any action that is high impact, destructive, or outside the allowed test envelope.

### 5. Modular and shift-left ready
Although the MVP targets already deployed applications, the same architecture should be reusable earlier in the lifecycle for pull requests, branch testing, pre-release hardening, and regression retesting.

## Core principles

### White-box by design
The toolchain assumes access to internal code, configuration, deployment descriptors, API contracts, and existing tests. Those internal artifacts are the primary source of truth for planning the campaign. Runtime probing exists to confirm or reject white-box hypotheses, not to replace them.

### Code first, runtime proven
The workflow begins with code and configuration analysis. Runtime probing is a second step that attempts to prove or disprove exploitability. This avoids wasting time on irrelevant payloads and makes every active test traceable back to a reason in the code.

### Separation of duties
The system preserves and strengthens the original three-role model:

- **Orchestrator**: plans the run, owns state, creates task files, decides which workers should run, and synthesizes the campaign result.
- **Workers**: execute bounded tasks and produce artifacts.
- **Validators**: challenge both worker output and orchestrator conclusions before a finding becomes accepted.

This keeps generation, execution, and acceptance decoupled.

### Deterministic artifacts
Every phase writes named files into a run-specific workspace. That provides continuity between agent calls, creates an audit trail, and allows the orchestrator to be reinvoked after workers finish.

### Two-pass operation
The toolchain should operate in at least two major passes:

1. **Read-only discovery pass**
   - read source and config
   - map routes, sinks, trust boundaries, and risky code paths
   - generate vulnerability and robustness hypotheses

2. **Active exploitability pass**
   - turn prioritized hypotheses into payload packs
   - execute requests against an approved test target
   - expand promising signals into robustness and abuse probes

This structure keeps active testing focused and safer.

## Operating context

The intended execution environment is a devcontainer with:

- access to the source repository
- access to an approved test or staging environment
- access to synthetic or test credentials only
- access to command-line tools required to inspect code and execute payloads
- Copilot CLI configured with repository-specific instructions, skills, agents, and hooks

The default assumption should be **non-production targets only** for active exploitability testing. If production is ever in scope, it should be limited to explicitly approved read-only checks or highly controlled probes with a separate approval path.

## High-level architecture

## 1. The orchestrator

The orchestrator remains the central LLM component, but its responsibilities are expanded and clarified.

### Responsibilities

- read the run scope, policy, and target definition
- maintain the run state in files
- create worker instruction files with predetermined names and locations
- decide which workers are read-only and which are allowed to execute active payloads
- replan after each stage
- merge findings, remove duplicates, and escalate conflicts to validators
- produce the final risk picture and remediation report

### What the orchestrator should not do

- it should not self-approve unsupported findings
- it should not directly run unrestricted destructive testing
- it should not skip validation because a result "looks convincing"

### Orchestrator output

At a minimum, the orchestrator should produce:

- a run manifest
- a system profile and attack-surface summary
- a task plan
- worker task files
- a prioritized hypothesis list
- a final consolidated report
- a release or readiness gate recommendation

## 2. Workers

Workers are specialized agents that receive a task file, create a short execution plan, execute the work, and leave behind evidence.

Each worker must produce at least:

- one file describing what it did, what it decided, and what it could not prove
- one result file containing findings, test outcomes, or structured output

For security and robustness work, a worker will usually also produce an evidence directory and, where relevant, a payload pack.

### Recommended worker families

#### A. Code surface mapper
Builds a code-first inventory of:

- routes and endpoints
- request handlers and middleware
- authn and authz checks
- data parsers and validators
- file upload paths
- outbound HTTP clients
- database access and raw query sinks
- shell execution points
- template rendering or deserialization points
- retry, timeout, and circuit-breaker logic

This worker is foundational because the rest of the campaign should depend on its map.

#### B. Security hypothesis worker
Uses the surface map plus code inspection to generate concrete hypotheses such as:

- missing authorization on a specific route
- unsafe path concatenation in file download logic
- SQL or command injection risk in a raw sink
- weak token validation in middleware
- secrets or PII leakage in error paths
- missing input-size limits for an upload endpoint

Each hypothesis should include a suspected component, impact statement, candidate payload family, and recommended active probe.

#### C. Dependency and configuration worker
Reviews:

- dependency manifests and lockfiles
- container and infrastructure config
- environment configuration patterns
- security headers and transport settings
- feature flags that change test posture

This worker should focus on exploitable or high-impact misconfiguration rather than producing long lists of low-value observations.

#### D. Exploitability worker
This is the most important active worker in the MVP. It takes prioritized hypotheses and turns them into executable payloads.

Its core job is to:

- generate reproducible payload packs
- execute them using `curl` and similar command-line tools
- collect exact requests and responses
- determine whether the observed behavior confirms, weakens, or rejects the hypothesis

This worker should be tightly constrained to allowed hosts, allowed credentials, allowed request rates, and approved test data.

#### E. Robustness worker
This worker extends successful or suspicious exploitability probes into robustness-oriented checks such as:

- malformed JSON or invalid encodings
- duplicate headers or duplicate parameters
- very large bodies
- boundary values
- missing required fields
- wrong-type fields
- concurrency bursts within safe rate limits
- dependency timeout and retry edge cases

The goal is not random fuzzing for its own sake. The goal is to test how the system behaves when stressed exactly where the code suggests fragility.

#### F. Resilience and recovery worker
This worker focuses on service behavior under adverse but realistic conditions:

- partial downstream failure
- timeout propagation
- retry storms
- stale cache handling
- error-message hygiene
- graceful degradation versus unsafe fallback behavior

#### G. Data exposure worker
Focuses on whether errors, logs, debug modes, or API responses leak:

- stack traces
- credentials or secret material
- internal hostnames or topology
- PII and regulated data
- object identifiers that enable IDOR exploration

## 3. Validators

Validation is not optional. The validator layer should include both worker-level validators and an orchestrator validator.

### Worker validators
A worker validator checks whether a worker:

- followed the task scope
- obeyed the policy guardrails
- produced required artifacts
- collected enough evidence
- overstated or understated severity
- confused a code smell with proven exploitability

### Orchestrator validator
The orchestrator validator checks whether the combined campaign:

- contains duplicate findings under different names
- promotes unvalidated worker output to final findings
- misses contradictions between workers
- lacks sufficient evidence for high-severity claims
- makes unsupported release-gating conclusions

## The code-first exploitability workflow

This is the central behavioral model of the toolchain.

### Step 1: Discover from code
The toolchain reads source code, config, OpenAPI files, infrastructure descriptors, and test assets. It extracts real routes, handlers, guards, sinks, inputs, outputs, and trust boundaries.

### Step 2: Form hypotheses
The orchestrator and read-only workers identify likely weaknesses and sort them by risk and plausibility.

### Step 3: Generate payload packs
For each prioritized hypothesis, the toolchain writes a payload pack that includes:

- the hypothesis statement
- required preconditions
- one or more request definitions
- request bodies and headers
- expected secure behavior
- expected vulnerable behavior
- cleanup notes if test data is created

### Step 4: Execute with `curl` and similar CLI tools
Payload execution should be command-line first. For HTTP and HTTPS this means `curl` should be the default. Equivalent CLI tools may be used for non-HTTP interfaces, but the mindset remains the same: minimal, scripted, reproducible, text-first probes.

### Step 5: Expand from interesting signals
If a probe reveals a likely weakness, the robustness worker can branch from it and test variants such as altered object IDs, malformed content types, oversized payloads, repeated requests, or timing-sensitive behavior.

### Step 6: Validate before acceptance
No active test result becomes a final accepted finding until a validator confirms that the claim, evidence, and severity match.

## Safety model

Security testing creates two kinds of risk: risk to the target system, and risk from the AI agent itself.

The toolchain therefore needs explicit guardrails.

### Scope and target controls

- active testing is restricted to allowlisted environments
- production is excluded by default for active probes
- credentials must be synthetic or test-only
- rate limits must be part of every active task
- test data creation must be tracked and cleaned up where possible

### Command and filesystem controls

- workers should only write inside the run workspace and approved report locations
- active workers should use narrow command allowlists
- destructive shell commands and infrastructure mutation commands should be denied by policy
- access to sensitive local files should be denied unless explicitly approved

### Data handling controls

- secrets should not be stored in the repository
- sensitive values should be injected at runtime and redacted in logs
- raw evidence should be sanitized before final reporting

### Decision controls

- high-impact tests require a separate approval level
- critical and high findings require stronger evidence thresholds
- validators can reject or downgrade any result

## Artifact model

Every run should have a dedicated workspace containing at least the following categories of files:

- manifest and scope
- system profile and attack-surface map
- task files
- worker execution logs
- payload definitions
- evidence captures
- structured findings
- validation results
- final report and gate decision

This artifact-first design allows:

- rerunning a single worker without replaying the entire campaign
- validating conclusions after the fact
- building metrics over repeated runs
- integrating later with CI, pull requests, or issue creation

## Quality bar for a finding

A finding should ideally include all of the following:

- affected component or route
- code location or configuration location
- hypothesis statement
- exact payload used
- exact command executed
- observed result
- expected secure result
- impact statement
- remediation guidance
- confidence and severity
- validator disposition

A code smell without exploit evidence can still be kept as a candidate observation, but it should not be presented as a validated vulnerability.

## Recommended lifecycle of a run

1. initialize run scope and policy
2. build source-aware surface map
3. generate and prioritize hypotheses
4. create worker task files
5. execute read-only workers
6. re-evaluate and create active exploitability tasks
7. execute `curl`-based probes
8. expand into robustness tests where justified
9. run worker validators
10. run orchestrator validator
11. generate final report and retest backlog

## Why this design is a better version of the original proposal

The original proposal correctly identified orchestrator, worker, and validator roles. This expanded design keeps those roles intact but makes them operationally stronger by:

- making the system code first rather than prompt first
- separating read-only discovery from active exploitability testing
- making `curl`-style payload execution a first-class artifact-producing phase
- introducing explicit evidence requirements
- adding policy and safety guardrails around the AI itself
- treating validators as mandatory decision-makers, not decorative reviewers

## Future evolution

After the MVP, the same architecture can be extended to:

- pull-request security review
- pre-merge regression testing
- scheduled hardening campaigns
- automatic retesting of previously fixed findings
- environment-specific policy bundles
- domain-specific workers for mobile, desktop, event-driven, or LLM-powered applications

## Summary

The testing toolchain should be understood as a **security-first, white-box, code-first, evidence-driven AI test system**.

It uses Copilot CLI as the execution substrate, a devcontainer as the containment boundary, the repository and its internal design artifacts as the primary source of truth, and `curl`-style payload execution as the main method for proving exploitability. The orchestrator plans and coordinates, workers inspect and probe, validators challenge and accept or reject, and the final result is a reproducible body of evidence about the security and robustness of the system under test.

## Suggested references for implementation

- [GitHub Copilot documentation](https://docs.github.com/en/copilot)
- [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli)
- [Creating and using custom agents for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli)
- [Creating agent skills for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-skills)
- [Hooks configuration](https://docs.github.com/en/copilot/reference/hooks-configuration)
- [Introduction to dev containers](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/adding-a-dev-container-configuration/introduction-to-dev-containers)
