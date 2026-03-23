#!/usr/bin/env python3
import json, re, shlex, subprocess
from pathlib import Path
import logging

from prompts import build_validation_prompt


CMD = "copilot -p"
DEFAULT_CHUNKS_DIR = "chunks"
DEFAULT_REPORT_FILE = "validation.json"
METADATA_START = "=== CHUNK METADATA START ==="
METADATA_END = "=== CHUNK METADATA END ==="


logging.basicConfig(
    filename="validator.log",
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def load_manifest(chunks_dir: Path):
    """Load the chunk manifest JSON."""
    manifest_path = chunks_dir / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def extract_chunk_metadata(chunk_file: Path):
    """Extract the metadata block from a chunk file."""
    content = chunk_file.read_text(encoding="utf-8", errors="ignore")
    pattern = re.escape(METADATA_START) + r"\s*(\{.*?\})\s*" + re.escape(METADATA_END)
    match = re.search(pattern, content, re.S)

    if not match:
        raise ValueError(f"Missing metadata block in {chunk_file}")

    return json.loads(match.group(1))


def load_chunk_metadata(chunks_dir: Path, manifest):
    """Load metadata for each chunk referenced by the manifest."""
    chunks = []

    for chunk in manifest.get("chunks", []):
        chunk_file = chunks_dir / chunk["file"]
        metadata = extract_chunk_metadata(chunk_file)
        chunks.append(metadata)

    return chunks


def prompt_for(manifest, chunks):
    """Build the validation prompt."""
    manifest_json = json.dumps(manifest, indent=2)
    chunks_json = json.dumps(chunks, indent=2)
    return build_validation_prompt(manifest_json, chunks_json)


def call_ai(prompt: str):
    """Call Copilot CLI and return parsed JSON response."""
    try:
        cmd = shlex.split(CMD)
        result = subprocess.run(
            cmd + [prompt],
            capture_output=True,
            text=True
        )

        output = (result.stdout or result.stderr).strip()
        match = re.search(r"\{.*\}", output, re.S)

        if not match:
            logging.error(f"No JSON in AI response:\n{output}")
            return None

        return json.loads(match.group(0))

    except Exception as exc:
        logging.error(f"call_ai failed: {exc}")
        return None


def fallback(manifest, chunks):
    """Build a deterministic validation report if AI output is unavailable."""
    issues = []
    seen_files = set()
    duplicate_files = set()

    if manifest.get("chunk_count") != len(manifest.get("chunks", [])):
        issues.append({
            "chunk_id": None,
            "severity": "medium",
            "message": "Manifest chunk_count does not match the number of chunk entries."
        })

    for chunk in chunks:
        chunk_files = chunk.get("files", [])
        declared_total = chunk.get("total_lines", 0)
        actual_total = sum(file_info.get("lines", 0) for file_info in chunk_files)

        if declared_total != actual_total:
            issues.append({
                "chunk_id": chunk.get("id"),
                "severity": "medium",
                "message": "Chunk total_lines does not match the sum of file line counts."
            })

        for file_info in chunk_files:
            path = file_info.get("path")
            if path in seen_files:
                duplicate_files.add(path)
            else:
                seen_files.add(path)

    for path in sorted(duplicate_files):
        issues.append({
            "chunk_id": None,
            "severity": "high",
            "message": f"File appears in more than one chunk: {path}"
        })

    status = "pass" if not issues else "needs_review"
    summary = (
        "Chunk validation passed with no deterministic issues found."
        if not issues
        else f"Chunk validation found {len(issues)} issue(s) that need review."
    )

    return {
        "status": status,
        "summary": summary,
        "issues": issues,
        "recommendations": [],
    }


def normalize(report, manifest, chunks):
    """Normalize the AI validation response into a stable shape."""
    if not isinstance(report, dict):
        return fallback(manifest, chunks)

    status = report.get("status", "needs_review")
    if status not in {"pass", "needs_review", "fail"}:
        status = "needs_review"

    issues = []
    for issue in report.get("issues", []):
        if not isinstance(issue, dict):
            continue

        severity = issue.get("severity", "medium")
        if severity not in {"low", "medium", "high"}:
            severity = "medium"

        issues.append({
            "chunk_id": issue.get("chunk_id"),
            "severity": severity,
            "message": issue.get("message", "").strip(),
        })

    recommendations = [
        str(item).strip()
        for item in report.get("recommendations", [])
        if str(item).strip()
    ]

    normalized = {
        "status": status,
        "summary": str(report.get("summary", "")).strip(),
        "issues": [issue for issue in issues if issue["message"]],
        "recommendations": recommendations,
    }

    if not normalized["summary"]:
        normalized["summary"] = (
            "Chunk validation passed."
            if normalized["status"] == "pass"
            else "Chunk validation needs review."
        )

    return normalized


def write_output(chunks_dir: Path, report):
    """Write the validation report to disk."""
    outpath = chunks_dir / DEFAULT_REPORT_FILE
    outpath.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main():
    """Validate the chunking job in the default chunks directory."""
    chunks_dir = Path(DEFAULT_CHUNKS_DIR)

    if not chunks_dir.exists():
        raise FileNotFoundError(f"Chunks directory does not exist: {chunks_dir}")

    manifest = load_manifest(chunks_dir)
    chunks = load_chunk_metadata(chunks_dir, manifest)
    prompt = prompt_for(manifest, chunks)
    report = call_ai(prompt) or fallback(manifest, chunks)
    report = normalize(report, manifest, chunks)
    write_output(chunks_dir, report)


if __name__ == "__main__":
    main()
