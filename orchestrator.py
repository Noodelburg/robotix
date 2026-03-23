"""Simple entrypoint for the chunking workflow."""

from pathlib import Path

from poc import (
    DEFAULT_MAX_LINES,
    DEFAULT_OUTPUT_DIR,
    call_ai,
    fallback,
    inventory,
    normalize,
    prompt_for,
    write_outputs,
)

TARGET_DIRECTORY = r"C:\Users\attil\Desktop\robotix\mvp"


def main():
    """Generate chunk files for the configured target directory."""
    root = Path(TARGET_DIRECTORY)
    outdir = Path(DEFAULT_OUTPUT_DIR)

    if not root.exists():
        raise FileNotFoundError(f"Target directory does not exist: {root}")

    items = inventory(root)
    prompt = prompt_for(items, DEFAULT_MAX_LINES)
    plan = call_ai(prompt) or fallback(items, DEFAULT_MAX_LINES)
    plan = normalize(plan, items, DEFAULT_MAX_LINES)
    write_outputs(root, outdir, plan, items)


if __name__ == "__main__":
    main()
