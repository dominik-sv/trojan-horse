"""Turn saved results into detection rates, a summary table and charts.

Two callers use this. A benchmark run writes a quick summary of just its own
results. visualize.py rebuilds one report from every run saved under runs/, so
new prompts, new models and earlier runs all show up together.

Each run folder is a self-describing record: grading.json holds the answers and
scores, and meta.json holds what those scores depended on (judge model, token
caps, and a fingerprint of every prompt and judge criteria file). That is what
lets runs be merged safely.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import csv
import hashlib
import json

from .config import JUDGE_MAX_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS
from .judge import JUDGE_TEMPLATE, load_criteria
from .models import PromptItem
from .plot import plot_detection_rates, plot_performance_bars, plot_scatter

DEFAULT_LABEL = "default"  # how "the model's default effort" is written in files and charts

Counts = dict[tuple[str, str, str], list[int]]  # (effort, prompt_id, model) -> [judged, spotted]


# --- meta.json: what a run's results depended on --------------------------------


def fingerprint(text: str) -> str:
    """A short, stable ID for a piece of text, so a change to it is detectable."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:12]


def build_meta(
    prompts: list[PromptItem],
    models: list[str],
    judge_pool: list[str],
    judges_per_answer: int,
    runs_per_prompt: int,
    efforts: list[str | None],
    created: datetime | None = None,
) -> dict:
    criteria = {prompt.question_type: load_criteria(prompt.question_type) for prompt in prompts}
    return {
        "created": (created or datetime.now()).isoformat(timespec="seconds"),
        "models": models,
        "judge_pool": judge_pool,
        "judges_per_answer": judges_per_answer,
        "judge_selection": "random per answer, never from the answer's own provider, seeded by the answer id",
        "runs_per_prompt": runs_per_prompt,
        "efforts": [effort or DEFAULT_LABEL for effort in efforts],
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "judge_max_output_tokens": JUDGE_MAX_OUTPUT_TOKENS,
        "prompts": {
            prompt.prompt_id: {"question_type": prompt.question_type, "fingerprint": fingerprint(prompt.text)}
            for prompt in prompts
        },
        "criteria": {qt: (fingerprint(text) if text else None) for qt, text in criteria.items()},
        "judge_template": fingerprint(JUDGE_TEMPLATE),
    }


def write_meta(run_dir: Path, meta: dict) -> None:
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --- counting and writing the report --------------------------------------------


def detection_counts(entries: list[dict]) -> Counts:
    """Count judged answers and how many spotted the false premise, per (effort, prompt, model).

    `entries` are grading.json records. Answers that were not judged (errors,
    no criteria) are left out of both counts.
    """
    counts: Counts = {}
    for entry in entries:
        if entry.get("score") is None:
            continue
        key = (entry.get("effort") or DEFAULT_LABEL, entry["prompt_id"], entry["model"])
        judged_spotted = counts.setdefault(key, [0, 0])
        judged_spotted[0] += 1
        judged_spotted[1] += entry["score"] == 1
    return counts


def write_report(out_dir: Path, counts: Counts, models: list[str]) -> None:
    """Write summary.csv and one chart per effort: summary.png (default) and summary_<effort>.png."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["effort", "prompt_id", "model", "judged", "spotted", "rate"])
        for (effort, prompt_id, model), (judged, spotted) in sorted(counts.items()):
            writer.writerow([effort, prompt_id, model, judged, spotted, f"{spotted / judged:.2f}"])

    for old_chart in out_dir.glob("summary*.png"):  # a rebuilt report must not keep charts of efforts that are gone
        old_chart.unlink()
    for effort in sorted({effort for effort, _, _ in counts}, key=lambda e: (e != DEFAULT_LABEL, e)):
        by_prompt_model = {(prompt_id, model): c for (e, prompt_id, model), c in counts.items() if e == effort}
        if effort == DEFAULT_LABEL:
            plot_detection_rates(by_prompt_model, models, out_dir / "summary.png")
        else:
            plot_detection_rates(
                by_prompt_model, models, out_dir / f"summary_{effort}.png", title_suffix=f" (effort: {effort})"
            )


# --- overall performance, tokens and cost per model -------------------------------


@dataclass(frozen=True)
class ModelMetrics:
    judged: int  # answers that were judged
    spotted: int  # of those, the ones judged to have spotted the false premise
    avg_output_tokens: float | None  # average output tokens per answer (the API counts thinking inside these)
    avg_latency: float | None  # average seconds per answer, from sending the request to getting the full answer
    cost_per_pass: float | None  # list-price cost of the answers for one full pass over all prompts

    @property
    def performance(self) -> float:
        return self.spotted / self.judged


def model_metrics(entries: list[dict]) -> dict[tuple[str, str], ModelMetrics]:
    """Per (effort, model): performance, average tokens and cost of one pass over the benchmark.

    Performance is answers that spotted the false premise over judged answers,
    so a call that failed or could not be judged is left out for every model
    alike. Output tokens are averaged over every answer that reports them; the
    API already counts thinking tokens inside output tokens, so nothing is added
    on top. Latency is averaged over the answers whose calls succeeded, and includes any
    time spent waiting to retry a rate limit. The cost of a pass is the sum over prompts of that prompt's average
    answer cost, which is the average cost of one run through every question;
    it includes answers that were cut off or unjudged (they still cost money)
    but not the judge calls.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for entry in entries:
        groups.setdefault((entry.get("effort") or DEFAULT_LABEL, entry["model"]), []).append(entry)

    metrics: dict[tuple[str, str], ModelMetrics] = {}
    for key, group in groups.items():
        judged = [e for e in group if e.get("score") is not None]
        if not judged:
            continue
        tokens = [e["output_tokens"] for e in group if e.get("output_tokens") is not None]
        latencies = [
            e["latency_seconds"]
            for e in group
            if e.get("latency_seconds") is not None and e.get("output_tokens") is not None
        ]
        costs_by_prompt: dict[str, list[float]] = {}
        for e in group:
            if e.get("cost_usd") is not None:
                costs_by_prompt.setdefault(e["prompt_id"], []).append(e["cost_usd"])
        metrics[key] = ModelMetrics(
            judged=len(judged),
            spotted=sum(1 for e in judged if e["score"] == 1),
            avg_output_tokens=sum(tokens) / len(tokens) if tokens else None,
            avg_latency=sum(latencies) / len(latencies) if latencies else None,
            cost_per_pass=sum(sum(c) / len(c) for c in costs_by_prompt.values()) if costs_by_prompt else None,
        )
    return metrics


def write_overview(out_dir: Path, entries: list[dict], models: list[str]) -> list[str]:
    """Write models.csv and, for each effort, the overall bar chart and the three scatter plots.

    Files: overall.png, performance_vs_tokens.png, performance_vs_latency.png,
    performance_vs_cost.png, with
    _<effort> added for efforts other than the default. Returns notes about
    charts that could not be drawn (for example no cost data yet).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = model_metrics(entries)
    notes: list[str] = []

    with (out_dir / "models.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "effort", "model", "judged", "spotted", "performance", "avg_output_tokens",
            "avg_latency_seconds", "cost_per_pass_usd",
        ])
        for (effort, model), m in sorted(metrics.items()):
            writer.writerow([
                effort, model, m.judged, m.spotted, f"{m.performance:.3f}",
                "" if m.avg_output_tokens is None else f"{m.avg_output_tokens:.0f}",
                "" if m.avg_latency is None else f"{m.avg_latency:.1f}",
                "" if m.cost_per_pass is None else f"{m.cost_per_pass:.5f}",
            ])

    for old_chart in [*out_dir.glob("overall*.png"), *out_dir.glob("performance_vs_*.png")]:
        old_chart.unlink()
    efforts = sorted({effort for effort, _ in metrics}, key=lambda e: (e != DEFAULT_LABEL, e))
    for effort in efforts:
        suffix = "" if effort == DEFAULT_LABEL else f"_{effort}"
        title_suffix = "" if effort == DEFAULT_LABEL else f" (effort: {effort})"
        mine = {model: m for (e, model), m in metrics.items() if e == effort}
        performance = {model: m.performance for model, m in mine.items()}

        plot_performance_bars(performance, models, out_dir / f"overall{suffix}.png", title_suffix)

        token_points = {
            model: (m.avg_output_tokens, m.performance) for model, m in mine.items() if m.avg_output_tokens is not None
        }
        if token_points:
            plot_scatter(
                token_points, performance, models, out_dir / f"performance_vs_tokens{suffix}.png",
                title="Performance vs average output tokens per answer",
                x_label="Average output tokens per answer",
                x_format=lambda value: f"{value:,.0f}", title_suffix=title_suffix,
                footnote="Output tokens as the API reports them (thinking is counted inside), averaged over all "
                "prompts and runs. Darker shade = better within the provider.",
            )
        else:
            notes.append(f"No token data for effort '{effort}', so its tokens chart was skipped.")

        latency_points = {model: (m.avg_latency, m.performance) for model, m in mine.items() if m.avg_latency is not None}
        if latency_points:
            plot_scatter(
                latency_points, performance, models, out_dir / f"performance_vs_latency{suffix}.png",
                title="Performance vs average time per answer",
                x_label="Average time per answer (seconds)",
                x_format=lambda value: f"{value:.0f}s", title_suffix=title_suffix,
                footnote="Time from sending the request to receiving the full answer, averaged over all prompts and runs; "
                "includes any wait to retry a rate limit. Darker shade = better within the provider.",
            )
        else:
            notes.append(f"No latency data for effort '{effort}', so its time chart was skipped.")

        cost_points = {model: (m.cost_per_pass, m.performance) for model, m in mine.items() if m.cost_per_pass}
        if cost_points:
            costs = [x for x, _ in cost_points.values()]
            plot_scatter(
                cost_points, performance, models, out_dir / f"performance_vs_cost{suffix}.png",
                title="Performance vs cost of one pass over the benchmark",
                x_label="Average cost of one full run through all questions (USD, list prices)",
                x_format=lambda value: f"${value:.2g}",
                log_x=max(costs) / min(costs) >= 8,
                title_suffix=title_suffix,
                footnote="Cost = the answers' list-price cost for one full pass over all prompts, averaged over runs; "
                "judging not included. Darker shade = better within the provider.",
            )
        else:
            notes.append(
                f"No cost data for effort '{effort}' yet (runs made before costs were saved have none), "
                "so its cost chart was skipped."
            )
    return notes


# --- loading every saved run and keeping the latest version of each prompt -------


@dataclass
class SavedRun:
    path: Path
    created: datetime
    meta: dict
    entries: list[dict]

    @property
    def graded(self) -> bool:
        """Whether this run was judged. A run with judging off asked questions but scored none of them."""
        return any(entry.get("score") is not None for entry in self.entries)


def load_runs(runs_dir: Path, include_legacy: bool = False) -> tuple[list[SavedRun], list[str]]:
    """Read every run folder, oldest first. Returns (runs, names of folders skipped).

    A folder without meta.json is from before runs recorded what their scores
    depend on. Those are skipped unless `include_legacy`, which builds a partial
    meta from the folder's prompts.json; the judge and criteria are then unknown.
    """
    runs: list[SavedRun] = []
    skipped: list[str] = []
    for path in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        grading = path / "grading.json"
        if not grading.is_file():
            continue  # empty folder, or a run from before grading.json existed
        meta_path = path / "meta.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        elif include_legacy:
            meta = _legacy_meta(path)
        else:
            skipped.append(path.name)
            continue
        runs.append(
            SavedRun(
                path=path,
                created=_created(meta, path),
                meta=meta,
                entries=json.loads(grading.read_text(encoding="utf-8")),
            )
        )
    runs.sort(key=lambda run: run.created)
    return runs, skipped


def _legacy_meta(path: Path) -> dict:
    prompts_path = path / "prompts.json"
    prompts = json.loads(prompts_path.read_text(encoding="utf-8")) if prompts_path.is_file() else []
    return {
        "models": [],
        "judge_model": None,
        "prompts": {
            p["prompt_id"]: {"question_type": p["question_type"], "fingerprint": fingerprint(p["text"])}
            for p in prompts
        },
        "criteria": {},
    }


def _created(meta: dict, path: Path) -> datetime:
    if meta.get("created"):
        return datetime.fromisoformat(meta["created"])
    for pattern in ("%Y-%m-%d_%H-%M-%S", "%Y%m%d-%H%M%S"):
        try:
            return datetime.strptime(path.name, pattern)
        except ValueError:
            continue
    return datetime.fromtimestamp(path.stat().st_mtime)


def latest_version_entries(runs: list[SavedRun]) -> tuple[list[dict], list[str]]:
    """Keep only results for the newest version of each prompt.

    A prompt's version is its text, its judge criteria, the judge prompt template and the judging panel. The
    version of the newest run that judged the prompt wins, and judged results
    from runs with a different version are dropped, since they answered a
    different question or were graded by different rules. A missing value
    (unknown in a legacy run) matches anything. Runs that were not judged are
    left out. Returns (entries, warnings); the entries include calls that failed
    or were not judged, since those were still questions that were asked.
    """

    def version(run: SavedRun, prompt_id: str) -> tuple:
        info = run.meta["prompts"].get(prompt_id, {})
        return (
            info.get("fingerprint"),
            run.meta.get("criteria", {}).get(info.get("question_type")),
            _judge_key(run.meta),
            run.meta.get("judge_template"),
        )

    def same(a: tuple, b: tuple) -> bool:
        return all(x is None or y is None or x == y for x, y in zip(a, b))

    latest: dict[str, tuple[tuple, str]] = {}
    for run in runs:  # oldest first, so later runs overwrite
        for prompt_id in {e["prompt_id"] for e in run.entries if e.get("score") is not None}:
            latest[prompt_id] = (version(run, prompt_id), run.path.name)

    kept: list[dict] = []
    dropped: dict[tuple[str, str], int] = {}
    for run in runs:
        if not run.graded:
            continue
        for entry in run.entries:
            prompt_id = entry["prompt_id"]
            if prompt_id in latest and same(version(run, prompt_id), latest[prompt_id][0]):
                kept.append(entry)
            elif entry.get("score") is not None:
                dropped[(prompt_id, run.path.name)] = dropped.get((prompt_id, run.path.name), 0) + 1
    warnings = [
        f"Left out {count} judged result(s) for '{prompt_id}' from {run_name}: an older version of the prompt, "
        f"its judge criteria or the judging panel (latest is from {latest[prompt_id][1]})."
        for (prompt_id, run_name), count in sorted(dropped.items())
    ]
    return kept, warnings


def _judge_key(meta: dict) -> tuple | None:
    """The judging setup as a comparable value; None if unknown or if nothing was judged."""
    pool = meta.get("judge_pool")
    per_answer = meta.get("judges_per_answer")
    if pool is None:  # runs saved before the random pool: a fixed panel, or a single judge
        pool = meta.get("judge_models") or ([meta["judge_model"]] if meta.get("judge_model") else None)
        per_answer = len(pool) if pool else None
    return (tuple(sorted(pool)), per_answer) if pool else None


def models_in_order(runs: list[SavedRun], entries: list[dict]) -> list[str]:
    """Models in the order they first appear across runs, so charts stay stable as you add more."""
    ordered: list[str] = []
    for run in runs:
        for model in run.meta.get("models", []):
            if model not in ordered:
                ordered.append(model)
    for entry in entries:
        if entry["model"] not in ordered:
            ordered.append(entry["model"])
    return ordered
