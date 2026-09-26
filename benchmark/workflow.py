"""The benchmark run: every prompt, sent to every model, saved for grading."""

from collections import defaultdict, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TextIO
import json
import time

from tqdm import tqdm

from .client import BenchmarkClient
from .config import MAX_CALLS_PER_MODEL, MAX_OUTPUT_TOKENS, MAX_PARALLEL_CALLS
from .judge import JudgeVote, apply_votes, judge_vote, load_criteria, pick_judges
from .models import ModelResult, PromptItem
from .report import build_meta, detection_counts, write_meta, write_report


def _query_one(
    client: BenchmarkClient, prompt: PromptItem, model: str, run: int, effort: str | None
) -> ModelResult:
    start = time.monotonic()
    try:
        reply = client.ask(model=model, prompt=prompt.text, max_output_tokens=MAX_OUTPUT_TOKENS, effort=effort)
        # A cut-off or empty answer is recorded as an error so it is never graded as if it were complete.
        error = None
        if reply.incomplete_reason:
            error = (
                f"Answer was cut off ({reply.incomplete_reason}) after {reply.output_tokens} tokens, "
                f"{reply.reasoning_tokens} of them thinking."
            )
        elif not reply.text.strip():
            error = f"Empty answer after {reply.output_tokens} tokens, {reply.reasoning_tokens} of them thinking."
        return ModelResult(
            prompt_id=prompt.prompt_id,
            question_type=prompt.question_type,
            model=model,
            run=run,
            effort=effort,
            response=reply.text or None,
            latency_seconds=time.monotonic() - start,
            error=error,
            output_tokens=reply.output_tokens,
            reasoning_tokens=reply.reasoning_tokens,
            cost_usd=reply.cost_usd,
        )
    except Exception as exc:  # a bad model name or a hard API error should not kill the whole run
        return ModelResult(
            prompt_id=prompt.prompt_id,
            question_type=prompt.question_type,
            model=model,
            run=run,
            effort=effort,
            response=None,
            latency_seconds=time.monotonic() - start,
            error=str(exc),
        )


def _run_limited(
    jobs: list[tuple[str, Any]],
    work: Callable[[Any], Any],
    on_done: Callable[[Any, Any], None],
) -> None:
    """Run (model, payload) jobs on a thread pool without flooding any one model.

    At most MAX_PARALLEL_CALLS calls run at once and at most MAX_CALLS_PER_MODEL
    of them go to the same model. New calls are started by cycling through the
    models, so back-to-back requests go to different models. `on_done(payload,
    result)` runs on the calling thread as each call finishes.
    """
    queues: dict[str, deque] = {}
    for model, payload in jobs:
        queues.setdefault(model, deque()).append(payload)
    order = deque(queues)  # models that still have jobs, in rotation
    active: dict[str, int] = defaultdict(int)
    in_flight: dict[Any, tuple[str, Any]] = {}

    pool = ThreadPoolExecutor(max_workers=min(len(jobs), MAX_PARALLEL_CALLS))

    def start_one_round() -> bool:
        """Offer each waiting model one free slot; return whether anything was started."""
        started = False
        for _ in range(len(order)):
            if len(in_flight) >= MAX_PARALLEL_CALLS:
                break
            model = order[0]
            order.rotate(-1)
            if active[model] >= MAX_CALLS_PER_MODEL:
                continue
            payload = queues[model].popleft()
            in_flight[pool.submit(work, payload)] = (model, payload)
            active[model] += 1
            started = True
            if not queues[model]:
                del queues[model]
                order.remove(model)
        return started

    try:
        while queues or in_flight:
            while start_one_round():
                pass
            done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:
                model, payload = in_flight.pop(future)
                active[model] -= 1
                on_done(payload, future.result())
    except BaseException:  # includes Ctrl+C: don't wait for calls that are still in flight
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown()


def run_benchmark(
    prompts: list[PromptItem],
    models: list[str],
    output_root: Path,
    judge_pool: list[str],
    judges_per_answer: int,
    runs_per_prompt: int,
    efforts: list[str | None],
) -> Path:
    """Send every prompt to every model and write one run folder with the results.

    Returns the run directory. It contains:
      - prompts.json  the exact prompts used, with their question types
      - results.json  every model's raw response, latency, and any error
      - grading.json  one entry per (prompt, model, run). For prompts with a file
                       in judge_criteria/, score is 1 if the judge says the model
                       spotted the false premise (else 0), with the judge's quote
                       and reasoning; otherwise score is null.
      - meta.json     what the scores depend on (judge, token caps, a fingerprint of
                       every prompt and judge criteria file); visualize.py uses it
                       to merge runs safely
      - summary.csv   a quick summary of this run only: per (effort, prompt, model),
                       judged runs, spotted runs, the rate
      - summary.png   bar chart of that rate at the models' default effort;
                       with several efforts, summary_<effort>.png for each other one
    visualize.py builds the same tables and charts across all runs.
    While the run is going, progress.jsonl gets one line per finished call, so a
    run that is killed still leaves its results behind; it is deleted once the
    files above are written. Each answer is graded by `judges_per_answer` judges drawn
    at random from `judge_pool` (never from the answer's own provider) and the majority
    decides; pass an empty pool to skip judging.
    """
    if not prompts:
        raise ValueError("No prompts to run.")
    if not models:
        raise ValueError("No models to run. Check 'models' in benchmark.toml.")

    client = BenchmarkClient()  # fail on a missing API key before creating a run folder

    run_dir = output_root / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir.mkdir(parents=True, exist_ok=False)
    journal_path = run_dir / "progress.jsonl"
    write_meta(run_dir, build_meta(prompts, models, judge_pool, judges_per_answer, runs_per_prompt, efforts))

    jobs = [
        (model, (prompt, model, run, effort))
        for model in models
        for prompt in prompts
        for effort in efforts
        for run in range(1, runs_per_prompt + 1)
    ]
    # One bar counts every API response we wait for: the model answers, plus one call
    # per judge for each answer that has grading criteria. A failed answer is never
    # judged, so the total is trimmed for each of those.
    judge_calls = (judges_per_answer if judge_pool else 0) * sum(
        1 for _, (prompt, *_) in jobs if load_criteria(prompt.question_type)
    )
    results: list[ModelResult] = []
    interrupted = False

    with journal_path.open("a", encoding="utf-8") as journal:
        try:
            with tqdm(total=len(jobs) + judge_calls, desc="API responses", unit="call") as progress:

                def answer_done(_payload: Any, result: ModelResult) -> None:
                    results.append(result)
                    _journal(journal, result)
                    progress.update(1)

                _run_limited(jobs, lambda payload: _query_one(client, *payload), answer_done)

                if judge_pool:
                    _judge_all(client, judge_pool, judges_per_answer, results, progress, journal)
        except KeyboardInterrupt:
            interrupted = True
            client.stop()
            print("\nStopped early; saving the results that finished.")

    results.sort(key=lambda result: (result.prompt_id, result.model, result.effort or "", result.run))

    (run_dir / "prompts.json").write_text(
        json.dumps([asdict(prompt) for prompt in prompts], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (run_dir / "results.json").write_text(
        json.dumps([asdict(result) for result in results], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    (run_dir / "grading.json").write_text(
        json.dumps([_grading_entry(result) for result in results], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    write_report(run_dir, detection_counts([_grading_entry(result) for result in results]), models)
    journal_path.unlink()  # everything is in the files above now

    failures = [result for result in results if result.error]
    if failures:
        print(f"{len(failures)} of {len(results)} calls failed; see the 'error' field in grading.json.")

    judge_failures = [result for result in results if result.judge_error]
    if judge_failures:
        print(f"{len(judge_failures)} responses got no majority from the judges; see judge_error in grading.json.")
    _print_judging(results)

    if interrupted:
        print(f"{len(results)} of {len(jobs)} answers finished before the run was stopped.")

    _print_cost(results)
    return run_dir


def _print_judging(results: list[ModelResult]) -> None:
    """Say how the judging went: agreement, and how many calls each judge handled."""
    judged = [r for r in results if r.judge_votes]
    if not judged:
        return
    if len(judged[0].judge_votes) >= 2:
        unanimous = split = 0
        for r in judged:
            verdicts = [vote["verdict"] for vote in r.judge_votes]
            if r.verdict is not None and verdicts.count(r.verdict) == len(verdicts):
                unanimous += 1
            elif r.verdict is not None:
                split += 1
        ungraded = sum(1 for r in judged if r.verdict is None)
        print(f"Judges: unanimous on {unanimous} of {len(judged)} answers, split on {split}, no majority on {ungraded}.")
    calls: dict[str, int] = defaultdict(int)
    unusable: dict[str, int] = defaultdict(int)
    for r in judged:
        for vote in r.judge_votes:
            calls[vote["judge_model"]] += 1
            unusable[vote["judge_model"]] += vote["verdict"] is None
    print("Judge calls: " + ", ".join(f"{m.split('/', 1)[-1]} {n}" for m, n in sorted(calls.items())))
    bad = {m: n for m, n in unusable.items() if n}
    if bad:
        print("Unusable judge replies: " + ", ".join(f"{m.split('/', 1)[-1]} {n}" for m, n in sorted(bad.items())))


def _print_cost(results: list[ModelResult]) -> None:
    """Print what the run cost at the providers' list prices."""
    answers = sum(result.cost_usd or 0.0 for result in results)
    judging = sum(result.judge_cost_usd or 0.0 for result in results)
    print(f"Total cost: ${answers + judging:,.4f} at list prices (answers ${answers:,.4f}, judging ${judging:,.4f}).")
    # A call that succeeded but reported no cost is missing from the total, so say so.
    unknown = sum(1 for r in results if r.output_tokens is not None and r.cost_usd is None)
    unknown += sum(
        1 for r in results for vote in (r.judge_votes or []) if vote["verdict"] is not None and vote["cost_usd"] is None
    )
    if unknown:
        print(f"Note: {unknown} call(s) reported no cost and are not included in that total.")


def _journal(journal: TextIO, result: ModelResult) -> None:
    """Append one finished result to the on-disk log right away."""
    journal.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
    journal.flush()


def _judge_all(
    client: BenchmarkClient,
    judge_pool: list[str],
    judges_per_answer: int,
    results: list[ModelResult],
    progress: tqdm,
    journal: TextIO,
) -> None:
    """Have judges grade every successful answer whose question type has criteria.

    Each answer gets its own panel drawn from the pool. Its verdict is set, and
    journaled, once all of its judges have replied. `results` is updated in place.
    """
    criteria_by_type: dict[str, str | None] = {}
    for result in results:
        if result.question_type not in criteria_by_type:
            criteria_by_type[result.question_type] = load_criteria(result.question_type)

    panels: dict[int, list[str]] = {}
    jobs: list[tuple[str, Any]] = []
    for index, result in enumerate(results):
        criteria = criteria_by_type[result.question_type]
        if criteria and result.response and not result.error:
            seed_text = f"{result.prompt_id}|{result.model}|{result.effort or 'default'}|{result.run}"
            panels[index] = pick_judges(judge_pool, judges_per_answer, result.model, seed_text)
            for judge_model in panels[index]:
                jobs.append((judge_model, (index, judge_model, result.response, criteria)))
        elif criteria:  # the answer failed, so the judge calls the bar expected won't happen
            progress.total -= judges_per_answer
    progress.refresh()
    if not jobs:
        return

    votes: dict[int, list[JudgeVote]] = defaultdict(list)

    def vote_done(payload: Any, vote: JudgeVote) -> None:
        index = payload[0]
        votes[index].append(vote)
        progress.update(1)
        if len(votes[index]) == len(panels[index]):
            ordered = sorted(votes.pop(index), key=lambda v: judge_pool.index(v.judge_model))
            judged = apply_votes(results[index], ordered, len(panels[index]))
            results[index] = judged
            _journal(journal, judged)

    _run_limited(jobs, lambda payload: judge_vote(client, payload[1], payload[2], payload[3]), vote_done)


def _judge_agreement(result: ModelResult) -> str | None:
    """How the panel voted on one answer, for example '2 yes / 1 no / 0 unusable'."""
    if not result.judge_votes:
        return None
    verdicts = [vote["verdict"] for vote in result.judge_votes]
    return f"{verdicts.count('yes')} yes / {verdicts.count('no')} no / {verdicts.count(None)} unusable"


def _grading_entry(result: ModelResult) -> dict:
    """One readable record per answer; the long response goes last."""
    return {
        "prompt_id": result.prompt_id,
        "question_type": result.question_type,
        "model": result.model,
        "run": result.run,
        "effort": result.effort or "default",
        "score": {"yes": 1, "no": 0}.get(result.verdict),  # null if not judged
        "judge_quote": result.judge_quote,
        "judge_quote_about": result.judge_quote_about,
        "judge_reasoning": result.judge_reasoning,
        "judge_error": result.judge_error,
        "judge_agreement": _judge_agreement(result),
        "judge_votes": result.judge_votes,
        "error": result.error,
        "latency_seconds": round(result.latency_seconds, 1),
        "output_tokens": result.output_tokens,
        "reasoning_tokens": result.reasoning_tokens,
        "cost_usd": result.cost_usd,
        "judge_cost_usd": result.judge_cost_usd,
        "response": result.response,
    }
