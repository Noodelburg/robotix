#!/usr/bin/env python3
import re, json, shlex, subprocess
from pathlib import Path
from collections import defaultdict
import logging

from prompts import build_chunk_plan_prompt



ABSOLUTE_MAX = 1_000_000
SKIP_DIRS={'.git','node_modules','dist','build','target','.venv','venv','.idea','.next','.cache','coverage','vendor','bin','obj'}
TEXT_EXTS={'.py','.js','.ts','.tsx','.jsx','.java','.kt','.go','.rs','.c','.cc','.cpp','.h','.hpp','.cs','.php','.rb','.swift','.scala','.sh','.bash','.zsh','.ps1','.sql','.html','.css','.scss','.md','.yaml','.yml','.json','.toml','.xml','.ini','.cfg','.conf','.tf','.dockerfile'}
BUILD_FILES={"dockerfile","makefile","jenkinsfile"}
CMD = "copilot -p"
DEFAULT_MAX_LINES = 2000
DEFAULT_OUTPUT_DIR = "chunks"




logging.basicConfig(
    filename="chunker.log",
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s"
)




def is_text(p:Path)->bool:
    return p.suffix.lower() in TEXT_EXTS or p.name.lower() in BUILD_FILES




def iterate_files(root: Path):
    """Yield relevant source files from a directory tree."""

    for path in sorted(root.rglob("*")):
        # Skip directories
        if path.is_dir():
            continue

        # Skip unwanted directories (e.g. .git, node_modules)
        if any(part in SKIP_DIRS for part in path.parts):
            continue

        # Skip non-text / non-source files
        if not is_text(path):
            continue

        try:
            # Skip huge files  
            file_size = path.stat().st_size
            if file_size > ABSOLUTE_MAX:
                logging.warning(f"Skipping huge file: {path}")
                continue

            # This file passed all filters → yield it
            yield path

        except OSError as e:
            logging.warning(f"Failed to process file: {path} | Error: {e}")
            continue




def count_lines(path: Path) -> int:
    """Count number of lines in a file. Returns 0 on failure."""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)

    except Exception as e:
        logging.error(f"Failed to count lines: {path} | Error: {e}")
        return 0




def inventory(root: Path):
    """Build metadata list for all relevant files in the repo."""
    items = []

    for path in iterate_files(root):
        try:
            relative_path = path.relative_to(root).as_posix()
            line_count = count_lines(path)

            # Get top-level directory (or '.' if file is at root)
            if "/" in relative_path:
                top_dir = relative_path.split("/", 1)[0]
            else:
                top_dir = "."

            # File extension fallback (handles files like 'Dockerfile')
            extension = path.suffix.lower() or path.name.lower()

            items.append({
                "path": relative_path,
                "dir": top_dir,
                "lines": line_count,
                "ext": extension
            })

        except Exception as e:
            logging.error(f"Failed to process file in inventory: {path} | Error: {e}")
            continue

    return items


def prompt_for(items, max_lines):
    """Build the chunk-planning prompt."""
    return build_chunk_plan_prompt(items, max_lines)






def call_ai(prompt: str):
    """Call Copilot CLI and return parsed JSON response."""

    try:
        # Build command
        cmd = shlex.split(CMD)

        # Run CLI
        result = subprocess.run(
            cmd + [prompt],
            capture_output=True,
            text=True
        )

        output = (result.stdout or result.stderr).strip()

        # Extract JSON from output
        match = re.search(r'\{.*\}', output, re.S)
        if not match:
            logging.error(f"No JSON in AI response:\n{output}")
            return None


        return json.loads(match.group(0))

    except Exception as e:
        logging.error(f"call_ai failed: {e}")
        return None



def fallback(items, max_lines):
    """Build deterministic chunks by grouping files by top-level directory."""

    groups = defaultdict(list)

    # Group files by top-level directory
    for item in items:
        groups[item["dir"]].append(item)

    chunks = []
    chunk_index = 1

    for directory, files in sorted(groups.items()):
        current_chunk = []
        current_total_lines = 0

        # Keep file order stable
        for file_info in sorted(files, key=lambda item: item["path"]):
            file_lines = file_info["lines"]

            # Start a new chunk if this file would exceed the limit
            if current_chunk and current_total_lines + file_lines > max_lines:
                chunk_name = re.sub(r"[^a-z0-9]+", "-", directory.lower()).strip("-") or "root"

                chunks.append({
                    "id": f"chunk-{chunk_index:04d}",
                    "name": chunk_name,
                    "reason": "deterministic directory fallback",
                    "files": [item["path"] for item in current_chunk]
                })

                chunk_index += 1
                current_chunk = []
                current_total_lines = 0

            current_chunk.append(file_info)
            current_total_lines += file_lines

        # Save the last chunk for this directory
        if current_chunk:
            chunk_name = re.sub(r"[^a-z0-9]+", "-", directory.lower()).strip("-") or "root"

            chunks.append({
                "id": f"chunk-{chunk_index:04d}",
                "name": chunk_name,
                "reason": "deterministic directory fallback",
                "files": [item["path"] for item in current_chunk]
            })

            chunk_index += 1

    return {"chunks": chunks}


def normalize(plan, items, max_lines):
    """Clean AI chunk plan and use fallback for any missing files."""

    # Ground truth: all valid files in the repo
    known = {item["path"]: item for item in items}

    seen = set()
    chunks = []

    for i, chunk in enumerate(plan.get("chunks", []), 1):

        # Keep only valid files that have not already been assigned
        files = [
            path for path in chunk.get("files", [])
            if path in known and path not in seen
        ]

        if not files:
            continue

        # Mark files as assigned
        seen.update(files)

        # Store normalized chunk
        chunks.append({
            "id": chunk.get("id") or f"chunk-{i:04d}",
            "name": chunk.get("name") or f"chunk-{i:04d}",
            "reason": chunk.get("reason", ""),
            "files": files
        })

    # Find files the AI missed
    missing_items = [known[path] for path in sorted(set(known) - seen)]

    # Use deterministic fallback to cover missing files
    if missing_items:
        logging.warning(f"AI missed {len(missing_items)} files. Using fallback.")

        fallback_chunks = fallback(missing_items, max_lines)["chunks"]
        next_index = len(chunks) + 1

        for chunk in fallback_chunks:
            chunk["id"] = f"chunk-{next_index:04d}"
            chunks.append(chunk)
            next_index += 1

    return {"chunks": chunks}





def write_outputs(root: Path, outdir: Path, plan, items):
    """Write chunk files and a manifest file."""

    # Quick lookup for file metadata
    metadata_by_path = {item["path"]: item for item in items}

    # Ensure output directory exists
    outdir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "root": str(root.resolve()),
        "chunk_count": len(plan["chunks"]),
        "chunks": []
    }

    for chunk in plan["chunks"]:
        chunk_id = chunk["id"]
        chunk_file = outdir / f"{chunk_id}.txt"

        total_lines = sum(metadata_by_path[path]["lines"] for path in chunk["files"])

        chunk_metadata = {
            "id": chunk_id,
            "name": chunk["name"],
            "reason": chunk["reason"],
            "total_lines": total_lines,
            "files": [
                {
                    "path": path,
                    "lines": metadata_by_path[path]["lines"]
                }
                for path in chunk["files"]
            ]
        }

        with chunk_file.open("w", encoding="utf-8") as output_file:
            # Write chunk metadata
            output_file.write("=== CHUNK METADATA START ===\n")
            output_file.write(json.dumps(chunk_metadata, indent=2))
            output_file.write("\n=== CHUNK METADATA END ===\n")

            # Write file contents
            for relative_path in chunk["files"]:
                file_path = root / relative_path
                file_content = file_path.read_text(encoding="utf-8", errors="ignore")

                output_file.write(f"\n=== FILE START: {relative_path} ===\n")
                output_file.write(file_content)

                # Ensure file content ends with a newline
                if not file_content.endswith("\n"):
                    output_file.write("\n")

                output_file.write("=== FILE END ===\n")

        manifest["chunks"].append({
            "id": chunk_id,
            "name": chunk["name"],
            "file": chunk_file.name,
            "total_lines": total_lines,
            "files": chunk["files"]
        })

    manifest_path = outdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
