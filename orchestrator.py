"""Simple entrypoint for the chunking workflow."""

from pathlib import Path

from chunker import DEFAULT_MAX_LINES, DEFAULT_OUTPUT_DIR, run_chunking
from validator import validate_chunks


TARGET_DIRECTORY = r"/some/dir"


def main():
    """Generate chunk files, then validate and correct them."""
    root = Path(TARGET_DIRECTORY)
    outdir = Path(DEFAULT_OUTPUT_DIR)

    if not root.exists():
        raise FileNotFoundError(f"Target directory does not exist: {root}")

    run_chunking(root, outdir, DEFAULT_MAX_LINES)
    validate_chunks(outdir)


if __name__ == "__main__":
    main()
