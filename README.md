# GPT Model Benchmark

Sends a set of prompts to a set of models (through Vercel AI Gateway), repeats each several times,
has a panel of judge models grade every answer (did it spot the false premise?), and
saves everything in a timestamped run folder. No agent framework: one request
per (prompt, model, run), plus one request per judge for each answer.

## Setup

Use Python 3.11 or newer. From this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Store your Vercel AI Gateway key as a Windows user environment variable named
`VERCEL_API_KEY`. The project never reads a local secret file. Every model
call goes through the gateway, so one key covers OpenAI, Anthropic, Google and
the other providers Vercel offers.

## Choose what to run: `benchmark.toml`

Everything you change between runs lives in [benchmark.toml](benchmark.toml):

- `models` — the models that answer each prompt
- `judge_pool` and `judges_per_answer` — the models that may grade answers (did it
  spot the false premise?) and how many of them grade each answer, drawn at
  random. Use an odd number, normally three; the majority decides. An empty pool
  skips grading
- `runs_per_prompt` — how many times each prompt goes to each model
- `test_all_efforts` and `effort_levels` — by default every model runs at its
  own default thinking effort. Set `test_all_efforts = true` to also run every
  prompt at each level in `effort_levels`, which multiplies the number of calls
  by the number of levels plus one
- `prompts_dir` and `prompts` — which prompt files to run (empty list = all)

Model IDs are written `provider/model`, for example `openai/gpt-5.6-luna` or
`anthropic/claude-opus-5`. `python run.py --list-models` prints every model the
gateway offers, and `python run.py --list-models claude` filters the list.

## Run it

```powershell
python run.py
```

Other options: `--config other.toml` uses a different config file,
`--no-judge` skips grading, and a quoted prompt
(`python run.py "your question" --type false_premise`) sends just that prompt
to the configured models.

## Prompts and grading

Put one prompt per file in `benchmark_prompts/`, named
`<question_type>_<anything>.txt`. The part before the last underscore is the
question type. A file named `judge_criteria/<question_type>.txt` holds the
yes/no question the judge answers for that type; prompts whose type has no
criteria file are not graded.

## How answers are graded

The judge pool is one cheap model from each provider. For every answer,
`judges_per_answer` (three) judges are drawn at random from the pool, never from
the answer's own provider, so no model family grades its own answers. The draw
is seeded by the answer's id (prompt, model, effort and run number), so the same
answer always gets the same judges. Each judge votes yes or no.

An answer's verdict needs more than half of its panel to agree, so two matching
votes decide it, even if the third judge's reply was unusable. If neither side
gets a majority, the answer is left ungraded and the reason is recorded.

`grading.json` keeps every vote (which judge, its verdict, quote and reasoning,
and cost) plus `judge_agreement` (for example `2 yes / 1 no / 0 unusable`). The end
of a run prints how often the judges were unanimous, split, or gave no majority,
how many calls each judge handled, and any judge whose replies were unusable.
Judging costs one call per judge per answer, three per answer in total.

Every provider that answers needs at least `judges_per_answer` pool judges from
other providers; the run refuses to start otherwise.

## Checking the judge

The judge's wording lives in `judge_criteria/<question_type>.txt` (what counts)
and in `JUDGE_TEMPLATE` in `benchmark/judge.py` (how to grade). After changing
either, check the judge against a hand-labelled set of answers:

```powershell
python check_judge.py
```

With no arguments it tests every model in the judge pool; pass `--judge-models` to test
others. The gold set is `tests/judge_gold.json`: answers from a saved run with a hand
verdict for each (1 = corrects the false premise). "Clear" items are
unambiguous; "hard" items are cases an earlier judge got wrong or that are
borderline. The command prints accuracy overall, on clear and on hard items,
false positives and negatives, and every vote on the hard items. It costs a few
cents. Keep any examples you put inside the criteria files invented, so they do
not overlap with the gold set.

Changing the criteria or the template changes a prompt's version, so the report
will chart only runs judged with the new wording.

## What a run produces

Each run creates `runs/<date>_<time>/` containing:

- `prompts.json` — the exact prompts used
- `results.json` — every response, latency, error, and the judge's verdict
- `grading.json` — one entry per (prompt, model, run), with `score` 1 (spotted
  the false premise) or 0, the judge's quote and reasoning, the token counts,
  the cost of the answer call (`cost_usd`) and of the judge call
  (`judge_cost_usd`), and the response
- `meta.json` — what the scores depend on: the judging panel, token caps, and a
  fingerprint of every prompt and judge criteria file
- `summary.csv` and `summary.png` — a quick summary of this run only: per
  (effort, prompt, model), judged runs, spotted runs and the rate, and a bar
  chart of it at default effort (one group per prompt, one bar per model; not
  written when nothing was graded); with `test_all_efforts` on, a
  `summary_<effort>.png` for each other level

Costs are the gateway's `marketCost`: what each call is worth at the provider's
list price. It is used because calls made with your own provider keys are billed
by the provider and show a gateway `cost` of 0. The run prints the total when it
finishes. Runs made before this was added have no cost data.

A failed call shows up as an empty `response` and a filled `error` field
rather than stopping the run. If the call was rate limited, the error holds the
response body, which says whether the limit was Vercel's or the provider's.

While a run is going, `progress.jsonl` gets one line per finished call. If you
press Ctrl+C, the run writes the files above from what finished; if the process
is killed harder than that, `progress.jsonl` is what's left. It is deleted once
the run completes normally.

## Request limits

Calls are limited in `benchmark/config.py`: `MAX_PARALLEL_CALLS` at once
overall and `MAX_CALLS_PER_MODEL` to any one model, cycling through the models
so back-to-back requests go to different ones. A temporary failure (429, 5xx,
dropped connection) is retried up to `RETRY_MAX_ATTEMPTS` times, waiting the
server's retry-after time if it sends one and otherwise 1, 2, 4, ... seconds.

## Charts across all runs

```powershell
python visualize.py
```

This reads every saved run in `runs/`, merges them, and writes `report/`:

- `summary.csv` and `summary.png` — detection rate per prompt and model
- `overall.png` — one bar per model: its overall performance
- `performance_vs_tokens.png` — performance against average output tokens per answer
- `performance_vs_latency.png` — performance against average time per answer
- `performance_vs_cost.png` — performance against the cost of one full pass over
  all prompts, averaged over runs (needs runs that saved costs)
- `models.csv` — the numbers behind those charts

With `test_all_efforts` on, each of the charts above also gets a version per
effort level (`overall_<effort>.png` and so on).

The script sends no requests and costs nothing, so run it any time; new prompts,
new models and earlier runs all appear together.

- **Pooling:** results for the same prompt, model and effort from different
  runs are added together, so each bar rests on more samples.
- **Performance** is answers that spotted the false premise divided by judged
  answers, so a call that failed is left out for every model alike.
- **Tokens** are output tokens as the API reports them. They already include
  thinking tokens, so nothing is added on top.
- **Time** is the wall-clock time of each answer's call, from sending the request
  to receiving the whole answer. It includes any wait to retry a rate limit and
  reflects the load at that moment, so treat it as a typical speed, not a benchmark.
- **Cost** counts the answers only (not the judge), at list prices.
- **Latest version only:** a prompt's version is its text, its judge criteria
  and the judging panel. Only results from the newest version are charted; older
  results are listed as left out.
- **Older runs:** a run without `meta.json` was saved before runs recorded what
  their scores depend on, so it is skipped. `--include-legacy` adds them anyway,
  but their judge and criteria are unknown and some used a token cap that cut
  answers off.

Other options: `--runs-dir` and `--out` change the folders.

## Where to look in the code

1. `benchmark/run_config.py` — reads `benchmark.toml`.
2. `benchmark/client.py` — one Responses API call, with the retry loop.
3. `benchmark/workflow.py` — `run_benchmark`: the job list, the per-model
   request scheduler, progress bar, and output files.
4. `benchmark/judge.py` — the grading prompt and verdict parsing;
   `benchmark/judge_check.py` scores it against the gold set.
5. `benchmark/report.py` — `meta.json`, merging runs, and the summary and charts;
   `benchmark/plot.py` only draws.
6. `benchmark/prompts.py` — how prompt files become `PromptItem`s.
