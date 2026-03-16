---
run_id: __RUN_ID__
task_id: __TASK_ID__
worker: __WORKER__
category: __CATEGORY__
active_testing: __ACTIVE_TESTING__
related_hypotheses: []
target_base_url: __TARGET_BASE_URL__
allowed_methods: [GET]
max_request_rate: 2rps
required_outputs:
  - reports/__TASK_SLUG__.execution.md
  - findings/__TASK_SLUG__.findings.json
  - validation/__TASK_SLUG__.validation.md
---

<!--
Template purpose:
This Markdown file is copied and token-replaced by run-orchestrator.sh to create
concrete worker task files for a specific run.
-->

Objective:
__OBJECTIVE__

Code evidence:
- __CODE_REFERENCE__

Instructions:
1. Read the related artifacts first.
2. Produce evidence-backed output only.
3. Obey policy and rate-limit constraints.
