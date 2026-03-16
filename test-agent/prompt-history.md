




Invite team members

test-agent-description.md
File
your job is to further build upon the CoPilot software testing toolchain design and description. I will give you a file called test-agent-description.md which contains a toolchain overview and some loose descriptions of how the testing toolchain could look. Keep in mind that the this is an AI toolchain that should be used with the copilot cli, in a devcontainer with access to the sourcecode and testenvironments. The focus of the testign toolchain should be security and robustness (the security aspect is very important). 

Your output should be two files, one .md file that describes the testing toolchain. Based on this toolchian description that you create based on the file i have given you and the instrucitons here you should create yet another .md file with the techincal implementaitiondetails.

I’m turning your draft into two markdown deliverables: a security-first testing toolchain design and a companion implementation spec for Copilot CLI in a devcontainer, grounded in your uploaded file and the orchestrator/worker/validator model.


also, the testing should be code first with testing payloads executed through curl and such based on the findings that are found to explore exploitabuility. 

I’ve now grounded the design in current Copilot CLI primitives—custom agents, skills, hooks, programmatic invocation, trusted directories, and tight tool permissions—and I’m making security the control-plane default with stricter isolation, approval gates, evidence handling, and clearer task contracts.

I’m now shifting the workflow to a code-first gray-box model: source analysis drives attack hypotheses, and exploitability is confirmed with deterministic curl/HTTP payloads against approved test environments instead of broad UI-first exploration.


white box

I’ve got both markdowns drafted, and I’m refining them into an explicitly white-box toolchain where source, configuration, and internal execution paths are the primary inputs. The implementation spec now also emphasizes safe-curl wrappers, fixture identities, and validator replay so exploitability is evidenced with reproducible request artifacts.

I’m making the dynamic layer explicitly a guarded confirmation phase rather than generic DAST, and the implementation now spells that out through repo layout, agent profiles, hooks, and state files.

Thought for 34m 12s
I created both markdown files and folded in your original orchestrator/worker/validator outline plus the later requirements that the toolchain be explicitly white-box, code-first, and use curl-style payload execution to validate exploitability from source-derived findings. 


Toolchain description

Technical implementation details

The implementation document is aligned to current GitHub Copilot CLI capabilities such as repository custom agents, skills, hooks, programmatic prompt execution and session sharing, permission controls, and devcontainer-based setup guidance. 


Alright so now that there is a vague idea, and some specifics, on how the toolchain should be structure,  what is the best way to implement it? The test orchestrator should for example break down the test and codebase into smaller bitesize pieces suitable for the context window. Different codebases thus require different amount of runtime. What is the best way to create an agentic workflow, where the result of one run will be used in the next?    


Stopped thinking

Alright so now that there is a vague idea, and some specifics, on how the toolchain should be structure, what is the best way to implement it? The test orchestrator should for example break down the test and codebase into smaller bitesize pieces suitable for the context window. Different codebases thus require different amount of runtime. What is the best way to create an agentic workflow, where the result of one run will be used in the next? 

I’m grounding the recommendation in the two markdowns we already produced, then I’ll map that into a concrete run-to-run workflow with durable state, chunking, and replay so it works across small and large codebases.

Thought for 1m 32s
The best implementation is not one long autonomous Copilot run. It is a durable controller + many bounded Copilot CLI runs.

Your original design already points that way: an orchestrator that creates task files, workers that execute and document, and validators that verify results. 


For Copilot CLI specifically, that maps well to custom agents, because agent work can be offloaded to subagents with their own context windows, which is exactly what you want for large codebases. Copilot CLI also supports programmatic runs with -p, resumable sessions, JSON output, hooks, custom instructions, and fine-grained tool permissions. 

The key design rule
Make the agent stateless; make the workflow stateful.

Do not rely on the LLM’s conversational memory as the system of record.
Instead, every run should read a small, explicit task package and write machine-readable outputs that the next run consumes.

That is the cleanest way to handle:

context-window limits,

different codebase sizes,

variable runtime,

retry/replay,

validator handoff,

auditability for security work.

Recommended architecture
1. A thin external controller
Use a small controller process outside Copilot CLI as the real orchestrator.

Its job is to:

scan the repo and environment once,

split the codebase into slices,

queue tasks,

invoke Copilot CLI programmatically for one bounded task at a time,

collect outputs,

schedule the next tasks from prior results,

stop when the frontier is exhausted or the budget is reached.

Copilot CLI is very good at bounded analysis/execution tasks, but for long-running agentic workflows, the controller should own the state machine. Copilot CLI’s programmatic mode is built for this pattern. 

2. Use Copilot agents for roles
Implement the workflow as a few custom agents:

test-orchestrator

code-slicer

security-analyzer

exploit-confirmor

validator

Custom agents are defined in Markdown and stored under .github/agents/ or ~/.copilot/agents/. Their work is done through subagents with separate context windows, which is useful for large-task decomposition. 

3. Use skills for repeatable specialist behavior
Put the reusable procedures in skills under .github/skills/, each with SKILL.md.

Examples:

repo-map

route-enumerator

authz-review

input-validation-review

safe-curl

exploit-replay

finding-normalizer

Skills are the right place for instructions, scripts, and domain-specific procedures that should be reused across tasks. 

4. Put the workflow policy in repo instructions
Store repo-wide operating rules in .github/copilot-instructions.md:

white-box only,

code-first,

dynamic checks only against approved targets,

all exploit confirmation must use approved wrappers,

findings must be emitted in JSON schema,

no direct destructive commands,

validator replay required before escalation.

Copilot CLI supports repository-wide custom instructions in .github/copilot-instructions.md. 

How one run should feed the next
The cleanest model is:

A. Every task is a file-backed contract
Each task file should contain:

task_id

parent_task_id

phase

target_slice

allowed_tools

allowed_urls

question

input_artifacts

expected_outputs

budget

B. Every worker emits two outputs
Keep your original pattern, but make one of them machine-readable:

result.json

notes.md

result.json should include:

status

summary

claims[]

evidence[]

new_targets[]

new_tasks[]

confidence

validator_required

C. The controller merges and schedules
After each run:

merge new claims into the global finding graph,

de-duplicate by code location / sink / endpoint / parameter,

add new tasks to the queue,

prioritize by risk and exploitability,

send only the top slice(s) into the next Copilot run.

That gives you a true agentic workflow where the output of one run becomes structured input to the next.

How to chunk the codebase for the context window
Do not chunk by raw file count. Chunk by security-relevant execution slices.

A good slice is:

one entrypoint or route group,

plus reachable middleware,

plus authn/authz logic,

plus input validation/parsing,

plus sensitive sinks,

plus relevant config,

plus nearby tests.

In practice, the controller should first build a lightweight repo map:

routes / controllers

RPC handlers

middleware chains

auth boundaries

database access points

deserializers / parsers

file / command / network sinks

crypto / token / session handling

config and secrets loading

Then it creates slices from that map.

Splitting rule
If a slice is too large:

split by route,

then by function cluster,

then by source-to-sink path.

Runtime implication
Different codebases will take different time because the runtime should scale with:

number of reachable slices,

number of auth boundaries,

number of dangerous sinks,

number of generated follow-up tasks.

That is expected. The controller should therefore budget per phase, not per repository.

The workflow I would implement
Phase 1: Inventory
One Copilot run, tightly bounded:

understand framework

identify entrypoints

identify auth model

identify high-risk sinks

write repo-map.json

Phase 2: Slice planning
Controller creates many slice tasks from repo-map.json.

Phase 3: White-box analysis per slice
For each slice, the analyzer agent:

reads only the files for that slice,

identifies trust boundaries,

proposes exploit hypotheses,

outputs precise candidate payloads and required evidence.

Phase 4: Code-first exploit confirmation
Only after a source-backed hypothesis exists, the exploit-confirmor runs:

curl or approved HTTP clients only,

against approved test URLs only,

with fixture identities/tokens only,

with deterministic request artifacts saved to disk.

This matches your white-box, code-first requirement.

Phase 5: Validator replay
A validator agent replays:

the source claim,

the request,

the response,

the impact check.

If replay fails, the finding drops or is downgraded.

Phase 6: Aggregate and recurse
The orchestrator:

merges validated findings,

spawns deeper tasks where needed,

stops when no new meaningful tasks are produced.

Copilot CLI features I would actually use
Programmatic runs, not just interactive sessions
Use copilot -p as the main execution primitive. Copilot CLI supports programmatic prompt execution, JSON output, resuming sessions, and sharing sessions to files. 

For this workflow, I would treat sessions as helpful but secondary.
Primary continuity should come from your own artifacts on disk.

Resume only for human-supervised investigations
Copilot CLI supports --resume, --continue, /resume, and session sharing. 

Use that for investigator continuity, not as the core orchestration mechanism.

Hooks for policy enforcement and logging
This is the most important Copilot-native control surface.

Use:

sessionStart to load or register run metadata,

userPromptSubmitted to log intent,

preToolUse to deny unsafe commands and enforce wrappers,

postToolUse to capture outputs/evidence,

sessionEnd to finalize run state.

Copilot’s hook system explicitly supports session start/end, prompt submission, pre-tool, and post-tool hooks. Pre-tool hooks can deny dangerous tool executions, and post-tool hooks can log results for audit trails. 

For your use case, preToolUse should enforce rules like:

deny raw rm, sudo, package install, docker control, cloud CLI, and outbound network except approved hosts,

deny direct curl,

allow only safe-curl wrapper or an approved shell pattern,

allow writes only inside a specific work directory.

Tight permissions
Copilot CLI lets you control trusted directories, tools, paths, and URLs, and supports allow/deny rules for shell commands, reads/writes, URLs, and more. 

For this toolchain, do not use broad autonomy by default.
Autopilot is good for well-defined tasks, but GitHub explicitly notes it is not ideal for open-ended exploration and that broad approvals effectively grant very wide power. 

So for security testing:

prefer bounded -p runs,

use --allow-tool narrowly,

use --deny-tool aggressively,

use URL allowlists,

use trusted directories,

only enable autopilot inside very constrained subtasks.

The most important implementation choice
If you want run N to drive run N+1 reliably, the best pattern is:

controller-managed task graph + file-backed state + bounded Copilot subruns

Not:

one giant Copilot session,

not freeform chat memory,

not a single autonomous worker left running until it “feels done.”

That will be too brittle for security work.

Concretely, I would build it like this
Repository layout:

.github/
  agents/
    test-orchestrator.agent.md
    security-analyzer.agent.md
    exploit-confirmor.agent.md
    validator.agent.md
  skills/
    repo-map/
      SKILL.md
    safe-curl/
      SKILL.md
      safe-curl.sh
    finding-normalizer/
      SKILL.md
  copilot-instructions.md
  hooks/
    policy.json

.toolchain/
  state/
    campaign.json
    queue.jsonl
    findings.jsonl
    slices/
    tasks/
    runs/
    evidence/
Execution model:

Controller reads campaign.json

Picks next task from queue.jsonl

Launches copilot -p ... --agent=security-analyzer --output-format=json

Saves outputs under runs/<run-id>/

Normalizes results

Pushes follow-up tasks back into queue

When a task requests confirmation, launch exploit-confirmor

Then launch validator

Merge validated results into findings.jsonl

That is the cleanest way to get true agentic chaining.

My recommendation in one sentence
Build it as a state machine outside Copilot CLI, and use Copilot CLI as the bounded reasoning/execution engine for each step.

That gives you:

context-window control,

variable-runtime support,

deterministic chaining,

reproducibility,

validator replay,

and much better security governance.

The next good step is to define the exact JSON schemas for task.json, result.json, finding.json, and evidence.json, because once those contracts are stable, the rest of the workflow becomes much easier to implement.


Need to make changes?
Try sending a follow-up while ChatGPT is thinking.




