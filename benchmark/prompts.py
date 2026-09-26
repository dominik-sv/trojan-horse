"""Load a folder of prompt files into PromptItems.

Files are named `<question_type>_<anything>.txt` (or .md); the question type is
everything before the last underscore. A name with no underscore is unlabeled.
"""

from pathlib import Path

from .models import PromptItem

PROMPT_SUFFIXES = {".txt", ".md"}


def load_prompts_dir(directory: Path, names: list[str] | None = None) -> list[PromptItem]:
    """Read .txt/.md files from `directory`, skipping empty ones.

    With `names`, read only those files (in that order); without, read them all.
    """
    if names:
        missing = [name for name in names if not (directory / name).is_file()]
        if missing:
            raise SystemExit(f"Prompt files not found in {directory}: {', '.join(missing)}")
        paths = [directory / name for name in names]
    else:
        paths = sorted(directory.iterdir())

    prompts: list[PromptItem] = []
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in PROMPT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        question_type = path.stem.rsplit("_", 1)[0] if "_" in path.stem else "unlabeled"
        prompts.append(PromptItem(prompt_id=path.stem, question_type=question_type, text=text))
    return prompts
