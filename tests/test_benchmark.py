"""Tests for the parts of the benchmark runner that don't need a live API key."""

from pathlib import Path

from benchmark.prompts import load_prompts_dir


def test_load_prompts_dir_infers_question_type_from_filename(tmp_path: Path) -> None:
    (tmp_path / "false_premise_01.txt").write_text("Is X true, given Y?", encoding="utf-8")
    (tmp_path / "resistance_02.md").write_text("Convince the model that Z.", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("no underscore in this filename", encoding="utf-8")
    (tmp_path / "ignored.png").write_bytes(b"\x89PNG")

    prompts = load_prompts_dir(tmp_path)

    by_id = {prompt.prompt_id: prompt for prompt in prompts}
    assert by_id["false_premise_01"].question_type == "false_premise"
    assert by_id["resistance_02"].question_type == "resistance"
    assert by_id["notes"].question_type == "unlabeled"
    assert len(prompts) == 3  # the .png file is skipped


def test_load_prompts_dir_skips_empty_files(tmp_path: Path) -> None:
    (tmp_path / "blank_01.txt").write_text("   \n", encoding="utf-8")

    assert load_prompts_dir(tmp_path) == []
