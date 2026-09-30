"""The one-command entry point for the model benchmark runner."""

import argparse
from pathlib import Path

from .client import BenchmarkClient
from .models import PromptItem
from .prompts import load_prompts_dir
from .report import models_needing_run
from .run_config import load_run_config
from .workflow import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send prompts to the models listed in benchmark.toml, grade the answers, and save the results."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="A single prompt to send instead of the prompts listed in the config file.",
    )
    parser.add_argument(
        "--type",
        default="unlabeled",
        help="Question type label to record for a single positional prompt.",
    )
    parser.add_argument(
        "--config", type=Path, default=Path("benchmark.toml"), help="Config file (default: benchmark.toml)."
    )
    parser.add_argument(
        "--list-models",
        nargs="?",
        const="",
        metavar="FILTER",
        help="Print the model IDs the gateway offers (only those containing FILTER, if given) and exit, "
        "without sending any prompt. Example: --list-models claude",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("runs"), help="Folder that will contain timestamped runs."
    )
    parser.add_argument(
        "--no-judge", action="store_true", help="Skip automatic grading and leave scores empty."
    )
    override = parser.add_mutually_exclusive_group()
    override.add_argument(
        "--all", action="store_true",
        help="Run every model in 'models', even ones already covered by saved runs.",
    )
    override.add_argument(
        "--models", nargs="+", metavar="MODEL",
        help="Run exactly these model IDs, even if already covered by saved runs.",
    )
    args = parser.parse_args()

    if args.list_models is not None:
        for model_id in BenchmarkClient().list_models(args.list_models):
            print(model_id)
        return

    config = load_run_config(args.config)

    if args.prompt:
        prompts = [PromptItem(prompt_id="prompt", question_type=args.type, text=args.prompt)]
    else:
        if not config.prompts_dir.is_dir():
            raise SystemExit(f"Prompts folder not found: {config.prompts_dir}.")
        prompts = load_prompts_dir(config.prompts_dir, config.prompts)
        if not prompts:
            raise SystemExit(f"No prompts to run in {config.prompts_dir}. Check 'prompts' in {args.config}.")

    if args.prompt or args.all:
        models = config.models
    elif args.models:
        models = args.models
    else:
        models, covered = models_needing_run(config.models, prompts, config.efforts, config.runs_per_prompt, args.output_dir)
        if covered:
            print(f"{len(covered)} of {len(config.models)} model(s) already covered: {', '.join(covered)}")
        if not models:
            print("Nothing new to run. Use --all or --models to force specific models.")
            return
        print(f"Running {len(models)} new model(s): {', '.join(models)}")

    judge_pool = [] if args.no_judge else config.judge_pool
    run_dir = run_benchmark(
        prompts, models, args.output_dir, judge_pool, config.judges_per_answer, config.runs_per_prompt, config.efforts
    )
    print(f"Benchmark complete. Results are in {run_dir}.")
