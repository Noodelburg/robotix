#!/usr/bin/env python3
"""Build normalized repository input documents from chunk manifests."""

import argparse
import json
from pathlib import Path

from chunker import inventory as build_inventory


DEFAULT_REPOSITORY_INPUT_FILE = "repository-input.json"


def resolve_manifest_path(manifest_path_or_dir):
    """Resolve a chunk manifest path from either a file or a directory."""
    path = Path(manifest_path_or_dir).resolve()

    if path.is_dir():
        return path / "manifest.json"

    return path


def load_manifest(manifest_path_or_dir):
    """Load a chunk manifest JSON document."""
    manifest_path = resolve_manifest_path(manifest_path_or_dir)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return manifest_path, payload


def build_repository_input_document(manifest_path_or_dir):
    """Convert a chunk manifest into the mapper/reviewer input shape."""
    manifest_path, manifest = load_manifest(manifest_path_or_dir)
    root = Path(manifest["root"]).resolve()
    items = build_inventory(root)
    metadata_by_path = {item["path"]: item for item in items}
    chunks = []

    for raw_chunk in manifest.get("chunks", []):
        file_entries = []

        for relative_path in raw_chunk.get("files", []):
            metadata = metadata_by_path.get(relative_path, {})
            file_entries.append(
                {
                    "path": relative_path,
                    "lines": int(metadata.get("lines", 0) or 0),
                }
            )

        total_lines = sum(file_info["lines"] for file_info in file_entries)
        chunks.append(
            {
                "id": str(raw_chunk.get("id") or "").strip(),
                "name": str(raw_chunk.get("name") or raw_chunk.get("id") or "").strip(),
                "reason": str(raw_chunk.get("reason") or "").strip(),
                "total_lines": total_lines,
                "file_count": len(file_entries),
                "files": file_entries,
            }
        )

    return {
        "root": str(root),
        "chunks": chunks,
        "source": {
            "manifest": str(manifest_path),
            "chunk_count": len(chunks),
            "source_file_count": int(manifest.get("source_file_count", 0) or 0),
            "max_lines": int(manifest.get("max_lines", 0) or 0),
        },
    }


def write_repository_input(manifest_path_or_dir, output_path=None):
    """Write the normalized repository input JSON to disk."""
    manifest_path = resolve_manifest_path(manifest_path_or_dir)
    target_path = (
        Path(output_path).resolve()
        if output_path
        else manifest_path.parent / DEFAULT_REPOSITORY_INPUT_FILE
    )
    payload = build_repository_input_document(manifest_path)
    target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target_path


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Build a normalized repository input JSON from chunks/manifest.json."
    )
    parser.add_argument(
        "manifest_or_dir",
        help="Path to chunks/manifest.json or the chunks directory itself.",
    )
    parser.add_argument(
        "output_json",
        nargs="?",
        help="Optional explicit output path. Defaults to repository-input.json next to the manifest.",
    )
    args = parser.parse_args()
    write_repository_input(args.manifest_or_dir, args.output_json)


if __name__ == "__main__":
    main()
