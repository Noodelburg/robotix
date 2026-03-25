Requirements Specification
AI-Assisted Security Review System with Worker-Validation Orchestrator
1. Purpose

The system shall perform authorized, high-level application security review over a target codebase using AI workers coordinated by a central orchestration layer.

The system shall be designed to maximize:

review coverage
finding quality
false-positive resistance
safe validation of suspected issues
repeatability of results

The system shall not treat “AI pentesting” as unrestricted autonomous exploitation.
The system shall treat the activity as security review first and controlled validation second.

2. Scope

The system shall:

ingest an in-scope codebase
partition the codebase into reviewable units
review those units through multiple worker passes
correlate local observations into end-to-end attack paths
challenge weak findings
safely validate strong findings through controlled PoC steps
produce actionable security reports
support post-fix revalidation

The system shall use the existing chunking and chunk-validation capability as the canonical preparation stage for downstream review.

3. Core Architectural Principle
3.1 Separation of concerns

The system shall separate:

review
correlation
skeptical challenge
validation
reporting
worker testing
3.2 Orchestrator role

The orchestrator shall be a test orchestrator.

The orchestrator shall not be the main reviewer.
Its primary responsibility shall be to:

assign review work
evaluate worker output quality
compare worker conclusions
detect weak or unsafe worker behavior
decide whether findings are ready for deeper validation
track coverage, confidence, and unresolved gaps
3.3 Validation principle

The system shall treat every security finding as a hypothesis until it is:

disproven
confirmed
or escalated for human review
4. Goals

The system shall achieve the following business and security goals:

G1. Coverage

Review all in-scope code through a structured, repeatable process rather than a single-pass scan.

G2. Quality

Prefer fewer, well-supported findings over many shallow or speculative findings.

G3. Traceability

Maintain traceability from:

code chunk
to worker output
to correlated finding
to validation outcome
to final report entry
G4. Safe confirmation

Confirm serious findings through controlled PoCs only when justified and authorized.

G5. Worker accountability

Continuously test whether workers are:

producing grounded outputs
hallucinating
missing obvious evidence
overstating impact
violating safety constraints
5. Non-Goals

The system shall not:

perform uncontrolled exploitation
run validation in production environments
prioritize “attack creativity” over evidence quality
auto-confirm issues based on a single weak signal
report speculative findings as confirmed
replace human review for high-severity or ambiguous cases
6. System Roles

The system shall support the following logical roles.

6.1 Chunk preparation

Uses the existing chunker and chunk validator to produce reviewable, validated chunks.

6.2 Repository understanding worker

Builds a high-level system map:

entrypoints
trust boundaries
identity and privilege zones
data stores
external integrations
sensitive operations
6.3 Local review worker

Reviews assigned chunks for likely weaknesses and produces candidate findings.

6.4 Thematic review worker

Re-reviews chunks through a specific lens, such as:

authorization
input handling
data exposure
file access
secrets
business logic abuse
multi-tenant isolation
6.5 Correlation worker

Connects observations across chunks into end-to-end attack paths.

6.6 Skeptic worker

Attempts to disprove or weaken findings by searching for:

hidden controls
unreachable paths
compensating protections
context that reduces impact
duplicate or overstated findings
6.7 Validation-planning worker

Designs a minimal, safe way to check whether a strong candidate issue is real.

6.8 PoC-validation worker

Executes controlled validation steps in an approved environment.

6.9 Reporting worker

Transforms validated results into developer-facing findings and remediation guidance.

6.10 Test orchestrator

Validates all workers, their outputs, and the overall review process.

7. Worker Behavior Requirements

Every review-oriented worker shall behave like a disciplined security reviewer.

WR-1 Trust-boundary thinking

Workers shall reason in terms of:

untrusted input
privileged actions
sensitive data
state changes
cross-boundary interactions
WR-2 Attack-path thinking

Workers shall prefer attack paths over isolated code smells.

Each candidate finding should describe, at minimum:

entrypoint
controllable input
relevant control gap
sensitive operation or boundary
expected impact
assumptions
WR-3 Evidence-first reasoning

Workers shall provide evidence for why a finding may be real.

WR-4 Self-challenge

Workers shall actively search for reasons the finding may be false.

WR-5 Confidence discipline

Workers shall clearly distinguish between:

suspicion
plausible issue
high-confidence issue
confirmed issue
WR-6 No premature exploitation

Workers shall not move directly from suspicion to exploit behavior.

8. Orchestrator Requirements

The orchestrator shall be a worker-validation and quality-control layer.

OR-1 Task assignment

The orchestrator shall assign chunks or system areas to workers based on:

risk
review phase
uncovered areas
previous worker performance
OR-2 Output validation

The orchestrator shall check worker output for:

schema completeness
evidence completeness
chunk relevance
duplication
contradiction with known facts
unsupported impact claims
unsafe suggestions
OR-3 Multi-worker comparison

The orchestrator shall compare outputs from different workers reviewing the same or related areas.

OR-4 Disagreement handling

When workers disagree, the orchestrator shall:

preserve both positions
request targeted re-review
route the issue to a skeptic worker
or escalate to human review
OR-5 Worker scoring

The orchestrator shall maintain quality signals for each worker, including:

evidence quality
consistency
precision proxy
duplication rate
challenge survival rate
safety compliance
contribution to coverage
OR-6 Worker trust management

The orchestrator shall be able to:

down-rank noisy workers
quarantine unsafe workers
require second opinions for low-trust workers
increase scrutiny on workers with unstable outputs
OR-7 Coverage management

The orchestrator shall track:

reviewed chunks
high-risk areas reviewed
areas reviewed only once
unresolved coverage gaps
findings awaiting challenge or validation
OR-8 Stage gating

The orchestrator shall control promotion of findings between stages and block progression when required evidence is missing.

OR-9 Auditability

The orchestrator shall preserve a review trail showing:

which worker reviewed what
what the worker concluded
how the output was tested
why it was accepted, rejected, or escalated
9. Review Process Requirements

The system shall execute review as a staged process.

RP-1 System understanding pass

The first pass shall build a system map before deep issue hunting begins.

RP-2 Broad local pass

The second pass shall review all chunks for broad suspicious patterns.

RP-3 Focused thematic passes

The system shall perform additional passes using specific security lenses.

RP-4 Cross-chunk correlation

The system shall connect findings across modules, services, helpers, and boundaries.

RP-5 Skeptic pass

All serious candidate findings shall be challenged by an independent skeptical pass.

RP-6 Validation-readiness decision

Only findings that survive challenge and contain sufficient evidence shall move to validation planning.

RP-7 Controlled validation

Only validation-ready findings shall move into PoC confirmation.

RP-8 Post-fix retest

After remediation, the system shall re-check the original path and adjacent related paths.

10. Finding Lifecycle Requirements

Each finding shall exist in an explicit state model.

Required states:

suspected
plausible
high-confidence
validation-ready
confirmed
disproven
needs human review
fixed pending retest
closed
FL-1 Evidence preservation

The system shall preserve the evidence that caused a finding to enter each state.

FL-2 State discipline

The system shall not label a finding “confirmed” without passing through validation or explicit human confirmation.

FL-3 Duplicate management

The system shall merge duplicates while preserving lineage from all contributing workers.

FL-4 Confidence transparency

The system shall expose why confidence changed over time.

11. PoC and Validation Requirements
PV-1 Gated validation

PoC generation shall be a gated function, not a default reviewer behavior.

PV-2 Preconditions

A finding shall only be eligible for validation when:

the attack path is coherent
the suspected impact is meaningful
the environment is authorized
safety constraints are satisfied
the skeptic stage did not invalidate the issue
PV-3 Minimal proof model

Validation shall proceed in escalating but limited steps:

reachability proof
control proof
benign impact proof
stop
PV-4 Non-destructive behavior

Validation shall be:

minimally invasive
reversible where possible
non-destructive
limited to approved environments and data
PV-5 Stop condition

Once reality has been safely established, the system shall stop rather than pursue maximal exploitation.

PV-6 Validation result types

Validation shall end with one of:

confirmed
not reproducible
inconclusive
blocked by safety constraints
needs human validation
PV-7 Safety logging

All validation attempts shall be logged with:

purpose
finding reference
scope
environment
expected proof condition
outcome
12. Worker-Testing Requirements

Because the orchestrator is a test orchestrator, it shall continuously validate worker quality.

WT-1 Structured evaluation

Every worker output shall be evaluated against a fixed quality rubric.

WT-2 Groundedness checks

The orchestrator shall verify that worker claims are grounded in assigned material and known system context.

WT-3 Challenge-response testing

The orchestrator shall test whether workers can defend findings against skeptical prompts.

WT-4 Noise detection

The orchestrator shall identify workers that:

repeatedly produce weak findings
overstate severity
ignore contrary evidence
fail to follow scope rules
WT-5 Coverage contribution measurement

The orchestrator shall measure whether a worker adds real coverage or merely repeats prior work.

WT-6 Regression testing

The orchestrator shall support replay of previously reviewed cases to test whether workers remain stable over time.

WT-7 Seeded evaluation

The system should support benchmark or seeded review tasks to estimate whether workers detect known classes of issues.

13. Reporting Requirements

The final reporting layer shall separate findings by certainty.

Required report sections:

confirmed findings
high-confidence findings not yet validated
plausible findings needing human review
disproven findings
coverage gaps
validation outcomes
post-fix retest outcomes

Each reported finding shall include:

title
affected area
attack path summary
evidence summary
impact summary
confidence state
validation status
remediation direction
retest requirement

The report shall avoid mixing “possible” and “confirmed” issues in the same category.

14. Safety and Governance Requirements
SG-1 Authorized use only

The system shall operate only on explicitly authorized targets.

SG-2 Environment isolation

Validation shall be restricted to approved, isolated environments.

SG-3 Human escalation

High-severity, ambiguous, or unusually sensitive cases shall be escalated for human review.

SG-4 Policy enforcement

The orchestrator shall block workers from bypassing scope, safety, or approval rules.

SG-5 Least privilege

Workers and validation steps shall use the least privilege necessary for the task.

SG-6 Data minimization

The system shall retain only the evidence and artifacts required for traceability and review.

15. Non-Functional Requirements
NFR-1 Repeatability

The same target and same review stage should produce materially similar results.

NFR-2 Explainability

A reviewer or developer shall be able to understand why a finding exists and how it was classified.

NFR-3 Modularity

Workers shall be replaceable without redesigning the full system.

NFR-4 Auditability

All stage transitions, worker outputs, and validation actions shall be reviewable later.

NFR-5 Scalability

The system shall support codebases larger than a single review window by relying on chunked and correlated analysis.

NFR-6 Fault tolerance

Failure of an individual worker shall not invalidate the full review run.

16. Acceptance Criteria

The system shall be considered acceptable when all of the following are true:

All in-scope code is chunked and validated before review begins.
Every high-risk subsystem is reviewed in more than one way, such as broad review plus thematic review.
Every serious finding has evidence, an attack-path explanation, and a skeptic challenge result.
No finding is marked confirmed without controlled validation or human confirmation.
The orchestrator can reject or down-rank weak worker output.
The system can clearly show which areas were reviewed, which remain uncertain, and why.
PoC activity is limited to approved environments and produces a bounded, non-destructive proof.
Post-fix retesting can verify that confirmed issues are actually closed.
17. Short version of the target architecture

At a high level, the system should work like this:

chunker prepares the work -> workers review and challenge the code -> correlators assemble attack paths -> the orchestrator tests the workers and governs promotion of findings -> only strong findings move into safe PoC validation -> reporting and retesting close the loop

That is the key change:
the orchestrator should validate workers, not replace them.

A strong next step would be to convert this specification into epics and acceptance-test checklists for each worker type.