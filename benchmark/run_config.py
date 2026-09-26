"""Read benchmark.toml: which models, judge, and prompts a run uses."""

from dataclasses import dataclass
from pathlib import Path
import tomllib

from .models import provider_of


@dataclass(frozen=True)
class RunConfig:
    models: list[str]
    judge_pool: list[str]  # models that can judge; empty means skip grading
    judges_per_answer: int  # how many of the pool judge each answer (odd, so a majority exists)
    runs_per_prompt: int
    efforts: list[str | None]  # None means the model's default effort
    prompts_dir: Path
    prompts: list[str]  # file names inside prompts_dir; empty means all of them


def load_run_config(path: Path) -> RunConfig:
    if not path.is_file():
        raise SystemExit(f"Config file not found: {path}.")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"{path} is not valid TOML: {exc}")

    models = data.get("models", [])
    if not isinstance(models, list) or not models or not all(isinstance(m, str) and m for m in models):
        raise SystemExit(f"{path}: 'models' must be a non-empty list of model ID strings.")

    prompts = data.get("prompts", [])
    if not isinstance(prompts, list) or not all(isinstance(p, str) and p for p in prompts):
        raise SystemExit(f"{path}: 'prompts' must be a list of file name strings (or empty for all).")

    runs = data.get("runs_per_prompt", 1)
    if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1:
        raise SystemExit(f"{path}: 'runs_per_prompt' must be a whole number of at least 1.")

    test_all = data.get("test_all_efforts", False)
    if not isinstance(test_all, bool):
        raise SystemExit(f"{path}: 'test_all_efforts' must be true or false.")
    levels = data.get("effort_levels", ["minimal", "low", "medium", "high", "xhigh"])
    if (
        not isinstance(levels, list)
        or not all(isinstance(level, str) and level for level in levels)
        or len(set(levels)) != len(levels)
    ):
        raise SystemExit(f"{path}: 'effort_levels' must be a list of distinct level names.")
    efforts: list[str | None] = [None, *levels] if test_all else [None]

    for old_key in ("judge_model", "judge_models"):
        if old_key in data:
            raise SystemExit(
                f"{path}: '{old_key}' is now 'judge_pool' (the models that may judge) plus 'judges_per_answer' "
                "(how many of them judge each answer, chosen at random)."
            )
    judge_pool = data.get("judge_pool", [])
    if (
        not isinstance(judge_pool, list)
        or not all(isinstance(m, str) and m for m in judge_pool)
        or len(set(judge_pool)) != len(judge_pool)
    ):
        raise SystemExit(f"{path}: 'judge_pool' must be a list of distinct model IDs (empty to skip grading).")
    judges_per_answer = data.get("judges_per_answer", 3)
    if (
        not isinstance(judges_per_answer, int)
        or isinstance(judges_per_answer, bool)
        or judges_per_answer < 1
        or judges_per_answer % 2 == 0
    ):
        raise SystemExit(f"{path}: 'judges_per_answer' must be an odd whole number (1, 3, 5, ...) so a majority exists.")
    if judge_pool:
        for provider in dict.fromkeys(provider_of(m) for m in models):
            eligible = [j for j in judge_pool if provider_of(j) != provider]
            if len(eligible) < judges_per_answer:
                raise SystemExit(
                    f"{path}: answers from '{provider}' need {judges_per_answer} judges from other providers, "
                    f"but the pool has only {len(eligible)}. Add judges from more providers or lower 'judges_per_answer'."
                )

    return RunConfig(
        models=models,
        judge_pool=judge_pool,
        judges_per_answer=judges_per_answer,
        runs_per_prompt=runs,
        efforts=efforts,
        prompts_dir=Path(data.get("prompts_dir", "benchmark_prompts")),
        prompts=prompts,
    )
