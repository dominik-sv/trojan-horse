"""Score judge prompts against the hand-labelled gold set in tests/judge_gold.json.

Run it after changing a judge criteria file or the judge template, to see whether
the change made the judge more accurate. It costs a few cents.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import argparse
import json

from tqdm import tqdm

from .client import BenchmarkClient
from .config import JUDGE_MAX_OUTPUT_TOKENS
from .judge import CRITERIA_DIR, JUDGE_TEMPLATE, _parse_verdict, build_judge_prompt, load_criteria
from .run_config import load_run_config
from .workflow import _run_limited

GOLD_PATH = Path("tests/judge_gold.json")


@dataclass(frozen=True)
class Config:
    """One way of judging: which model, which criteria files, which template."""

    judge_model: str
    criteria_dir: Path = CRITERIA_DIR
    template: str = JUDGE_TEMPLATE


@dataclass(frozen=True)
class Vote:
    item_id: str
    tier: str
    label: int  # the gold verdict
    verdict: int | None  # the judge's verdict, or None if its reply could not be used
    error: str | None
    cost: float


def load_gold(path: Path = GOLD_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["items"]


def collect_votes(
    client: BenchmarkClient, gold: list[dict], configs: dict[str, Config], repeats: int
) -> dict[str, list[Vote]]:
    """Ask every config to judge every gold item `repeats` times."""
    criteria = {
        name: {qt: load_criteria(qt, cfg.criteria_dir) for qt in {item["question_type"] for item in gold}}
        for name, cfg in configs.items()
    }

    def work(payload: Any) -> tuple[str, Vote]:
        name, item = payload
        cfg = configs[name]
        prompt = build_judge_prompt(criteria[name][item["question_type"]], item["response"], cfg.template)
        verdict = error = None
        cost = 0.0
        try:
            reply = client.ask(model=cfg.judge_model, prompt=prompt, max_output_tokens=JUDGE_MAX_OUTPUT_TOKENS)
            cost = reply.cost_usd or 0.0
            if reply.incomplete_reason:
                raise ValueError(f"cut off ({reply.incomplete_reason})")
            verdict = 1 if _parse_verdict(reply.text)["verdict"].strip().lower() == "yes" else 0
        except Exception as exc:
            error = str(exc)[:200]
        return name, Vote(item["id"], item["tier"], item["label"], verdict, error, cost)

    # Each config has its own queue, so several configs run side by side.
    jobs = [(name, (name, item)) for name in configs for item in gold for _ in range(repeats)]
    votes: dict[str, list[Vote]] = {name: [] for name in configs}
    with tqdm(total=len(jobs), desc="Judge calls", unit="call") as progress:

        def done(_payload: Any, result: tuple[str, Vote]) -> None:
            votes[result[0]].append(result[1])
            progress.update(1)

        _run_limited(jobs, work, done)
    return votes


def summarize(votes: dict[str, list[Vote]]) -> str:
    """A table of accuracy per config, then the votes on every 'hard' item."""
    lines = []
    header = f"{'config':<26}{'accuracy':>10}{'clear':>9}{'hard':>8}{'false +':>9}{'false -':>9}{'unusable':>10}{'cost $':>9}"
    lines += [header, "-" * len(header)]

    def acc(votes_: list[Vote]) -> str:
        valid = [v for v in votes_ if v.verdict is not None]
        return f"{sum(v.verdict == v.label for v in valid) / len(valid):.0%}" if valid else "n/a"

    for name, vs in votes.items():
        valid = [v for v in vs if v.verdict is not None]
        false_pos = sum(1 for v in valid if v.verdict == 1 and v.label == 0)
        false_neg = sum(1 for v in valid if v.verdict == 0 and v.label == 1)
        lines.append(
            f"{name:<26}{acc(vs):>10}{acc([v for v in vs if v.tier == 'clear']):>9}"
            f"{acc([v for v in vs if v.tier == 'hard']):>8}{false_pos:>9}{false_neg:>9}"
            f"{len(vs) - len(valid):>10}{sum(v.cost for v in vs):>9.3f}"
        )

    hard_ids = sorted({v.item_id for vs in votes.values() for v in vs if v.tier == "hard"})
    lines += ["", "Votes on the hard items (gold verdict in brackets; 1 = corrects the premise, 0 = does not):"]
    for item_id in hard_ids:
        gold_label = next(v.label for vs in votes.values() for v in vs if v.item_id == item_id)
        lines.append(f"  {item_id}  [gold {gold_label}]")
        for name, vs in votes.items():
            cast = [v.verdict for v in vs if v.item_id == item_id]
            lines.append(f"      {name:<24}{' '.join('?' if c is None else str(c) for c in cast)}")
    wrong = sorted(
        {(v.item_id, name) for name, vs in votes.items() for v in vs if v.verdict is not None and v.verdict != v.label}
    )
    clear_wrong = [(i, n) for i, n in wrong if not any(v.tier == "hard" and v.item_id == i for vs in votes.values() for v in vs)]
    if clear_wrong:
        lines += ["", "Clear items any config got wrong at least once:"]
        lines += [f"  {item_id}  ({name})" for item_id, name in clear_wrong]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the current judge prompts against the gold set.")
    parser.add_argument("--judge-models", nargs="+", help="Judge models to test (default: every model in the judge pool in benchmark.toml).")
    parser.add_argument("--repeats", type=int, default=3, help="Times each judge sees each item (default 3).")
    parser.add_argument("--criteria-dir", type=Path, default=CRITERIA_DIR)
    args = parser.parse_args()

    judges = args.judge_models or load_run_config(Path("benchmark.toml")).judge_pool
    if not judges:
        raise SystemExit("No judge model: pass --judge-models or set judge_pool in benchmark.toml.")
    configs = {model.split("/", 1)[-1]: Config(model, args.criteria_dir) for model in judges}
    print(summarize(collect_votes(BenchmarkClient(), load_gold(), configs, args.repeats)))
