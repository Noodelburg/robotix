"""Simple entrypoint for the end-to-end review workflow."""

from pathlib import Path

from chunker import DEFAULT_MAX_LINES, DEFAULT_OUTPUT_DIR, run_chunking
from chunker_validator import validate_chunks
from mapper import run_mapper
from mapper_validator import validate_mapper
from repository_input import write_repository_input
from reviewer import run_reviewer
from reviewer_validator import validate_reviewer


TARGET_DIRECTORY = r"/some/dir"
DEFAULT_REVIEW_OUTPUT_DIR = "reviews/wstg"


def main():
    """Generate chunks, repository context, and WSTG review outputs."""
    root = Path(TARGET_DIRECTORY)
    outdir = Path(DEFAULT_OUTPUT_DIR)

    if not root.exists():
        raise FileNotFoundError(f"Target directory does not exist: {root}")

    run_chunking(root, outdir, DEFAULT_MAX_LINES)
    validate_chunks(outdir)
    repository_input_path = write_repository_input(outdir)
    system_map_path = outdir / "system-map.json"
    run_mapper(repository_input_path, system_map_path)
    validate_mapper(repository_input_path, system_map_path)
    review_output_dir = root / DEFAULT_REVIEW_OUTPUT_DIR
    run_reviewer(repository_input_path, system_map_path, review_output_dir)
    validate_reviewer(repository_input_path, system_map_path, review_output_dir)


if __name__ == "__main__":
    main()
