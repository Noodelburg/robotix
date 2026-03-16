# AI Code Reviewer MVP

This project is a very small Python command-line app that reviews a git diff or patch and prints a short report.

It is designed for learning first:
- small files
- simple data models
- one clear provider interface
- easy local execution

## What the app does

1. Load a diff from a file or from `git diff`
2. Send that diff to a review provider
3. Ask the provider for structured JSON
4. Parse the JSON into Python objects
5. Print a readable console report

## Why the provider abstraction exists

The `BaseReviewProvider` interface keeps the rest of the app independent from any specific LLM vendor.

That means:
- the CLI does not care whether the review comes from OpenAI, Anthropic, Azure OpenAI, Copilot, or a mock
- each provider can focus only on authentication and API calling details
- adding a new provider later should mostly mean adding one file and one factory branch

For an MVP, this is enough abstraction to be useful without becoming heavy.

## Project structure

```text
ai_code_reviewer/
  README.md
  requirements.txt
  .env.example
  sample.diff
  reviewer/
    __init__.py
    main.py
    config.py
    models.py
    prompts.py
    git_utils.py
    reviewer_service.py
    providers/
      __init__.py
      base.py
      openai_provider.py
      mock_provider.py
```

## Install

From inside the project folder:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy the environment example if you want local configuration:

```bash
copy .env.example .env
```

## Run with MockProvider first

The mock provider lets you test the app without any API key.

```bash
python -m reviewer.main --provider mock --diff-file sample.diff
```

You can also rely on `.env`:

```env
REVIEWER_PROVIDER=mock
```

## Run with OpenAIProvider

Set your API key and choose the OpenAI provider:

```env
REVIEWER_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5-mini
```

Then run:

```bash
python -m reviewer.main --diff-file sample.diff
```

You can also generate a diff directly from git:

```bash
python -m reviewer.main --provider openai --repo-path . --base-ref main
```

## Sample diff file

This repository includes a small sample file at `sample.diff`.

Example shape:

```diff
diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1,4 +1,5 @@
 def run(user_input):
-    return process(user_input)
+    if user_input is None:
+        return process(None)
+    return eval(user_input)
```

## Example JSON response shape

This is the shape the provider is asked to return:

```json
{
  "summary": "The diff introduces one security problem and one correctness risk.",
  "findings": [
    {
      "file_path": "app.py",
      "severity": "high",
      "category": "security",
      "title": "Unsafe use of eval on user-controlled input",
      "explanation": "The new code executes raw user input, which can lead to arbitrary code execution.",
      "suggested_fix": "Replace eval with safe parsing or an allowlisted command dispatcher."
    }
  ]
}
```

## Architecture in plain English

### `reviewer/main.py`

The CLI entrypoint. It parses arguments, loads a diff, builds the provider, runs the review, and prints the result.

### `reviewer/config.py`

Loads environment variables into a small `Settings` dataclass.

### `reviewer/models.py`

Defines the internal Python objects:
- `ReviewFinding`
- `ReviewReport`

It also contains the JSON schema used for structured model output.

### `reviewer/prompts.py`

Holds the system prompt and the user prompt builder so prompt text is not mixed into provider code.

### `reviewer/git_utils.py`

Contains the simple file-reading and `git diff` helpers.

### `reviewer/reviewer_service.py`

A thin orchestration layer between the CLI and the provider.

### `reviewer/providers/base.py`

Defines the provider contract: `review_diff(diff_text: str) -> ReviewReport`

### `reviewer/providers/mock_provider.py`

Returns a predictable hardcoded report. Useful for learning, demos, and smoke tests.

### `reviewer/providers/openai_provider.py`

Implements the real model-backed review using the OpenAI Responses API and structured JSON output.

## Where to plug in future features

### Pull request comments

Add them after `ReviewReport` is produced. A future layer could translate findings into GitHub or GitLab review comments.

### Severity thresholds

Add them between `ReviewerService` and `print_report`. That is the simplest place to filter out low-severity findings.

### GitHub Actions CI

Wrap the CLI in a workflow that installs dependencies, generates a diff, and fails the job when findings above a threshold exist.

### Alternate LLM providers

Add a new file under `reviewer/providers/`, implement `review_diff`, and register it in `reviewer/providers/__init__.py`.

## Next improvements

- add optional line-number extraction when the model can ground it reliably
- add severity filtering flags in the CLI
- add markdown or JSON output modes
- add provider-specific retry handling
- add GitHub PR comment publishing

## Notes about the OpenAI implementation

The OpenAI provider uses the Responses API and requests structured output with a JSON schema. That keeps parsing simple and makes the project easier to extend later.

