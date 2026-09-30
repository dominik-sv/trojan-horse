# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A benchmark that sends prompts containing a planted false premise to many LLMs (through Vercel AI Gateway), has a random panel of cheap judge models grade whether each answer corrects the premise, and reports detection rate, tokens, cost and latency.

## Commands

- `python run.py` runs the benchmark, but auto-skips any model in `models` that already has enough saved runs for every current prompt, so adding one new model to `benchmark.toml` and running only pays for that model (`--all` forces the whole roster, `--models ID ...` forces specific ones; `--no-judge` skips grading; `--list-models [filter]` lists gateway models)
- `python visualize.py` rebuilds `report/` from all saved runs (free, no API calls)
- `python check_judge.py` scores the judge pool against `tests/judge_gold.json` (a few cents)
- Needs `VERCEL_API_KEY` as an environment variable. Editors only see it after a full restart.

## Where things live

- `benchmark.toml` is the only file you edit between runs: models, `judge_pool`, `judges_per_answer`, runs, effort levels, prompts, and the optional `report_since` cutoff.
- `benchmark_prompts/<type>_<id>.txt` are the prompts; the part before the last underscore is the question type.
- `judge_criteria/<type>.txt` is what the judge grades for that question type. A type with no file is not graded.
- `benchmark/workflow.py` is the run: per-model request limits, answers, then judging, then output files.
- `benchmark/judge.py` holds the judge template, random panel selection and majority vote.
- `benchmark/report.py` builds `meta.json` and merges runs; `benchmark/plot.py` only draws.
- `runs/<timestamp>/` is one run and is never edited afterwards.

## Things that are easy to get wrong

- Every run folder must keep `meta.json`. `visualize.py` charts only the newest version of each prompt, where a version is the prompt text, judge criteria, judge template and judge pool. Changing any of these makes older results drop out of the report; runs without `meta.json` are skipped. To start a fresh accumulation from a given run onward (without losing older run folders or bumping any version), set `report_since` in `benchmark.toml` to that run's `created` timestamp from its `meta.json` — runs before it are ignored, everything at/after it still accumulates as normal.
- Each answer is judged by 3 judges drawn at random from the pool, never from the answer's own provider, seeded by the answer id. A verdict needs a majority of the panel. If the panel ties (or has too many unusable replies), one more judge is drawn from the pool and added, repeating until a majority is reached or every eligible judge has been asked; only then is the answer left ungraded.
- `output_tokens` from the API already includes thinking tokens. Cost is the gateway's `marketCost` (list price), because calls made with your own OpenAI/Anthropic keys show a gateway `cost` of 0.
- After changing judge criteria or the template, rerun `check_judge.py`. Keep examples inside criteria files invented so they do not overlap with the gold set.
- The auto-skip only compares against the *latest saved* version of each prompt. A brand-new prompt file correctly makes every model "needing" it, but editing the text or criteria of an *existing* prompt doesn't force a re-run on its own — use `--all` or `--models` the first time after that kind of change.
