"""Rebuild the report (summary table and charts) from every run saved under runs/."""

import argparse
from pathlib import Path

from .report import (
    detection_counts,
    latest_version_entries,
    load_runs,
    models_in_order,
    write_overview,
    write_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Combine all saved runs into one summary.csv and charts. Sends no requests and costs nothing."
    )
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"), help="Folder of saved runs (default: runs).")
    parser.add_argument("--out", type=Path, default=Path("report"), help="Folder to write the report to (default: report).")
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="Also use runs saved before meta.json existed. Their judge and criteria are unknown, so they "
        "cannot be checked against the latest versions, and older ones may contain answers cut off by a low token cap.",
    )
    args = parser.parse_args()

    if not args.runs_dir.is_dir():
        raise SystemExit(f"Runs folder not found: {args.runs_dir}.")

    runs, skipped = load_runs(args.runs_dir, args.include_legacy)
    if skipped:
        print(f"Skipped {len(skipped)} run(s) without meta.json (use --include-legacy to add them): {', '.join(skipped)}")
    if not runs:
        raise SystemExit(f"No usable runs found in {args.runs_dir}.")

    entries, warnings = latest_version_entries(runs)
    for warning in warnings:
        print(warning)
    counts = detection_counts(entries)
    if not counts:
        raise SystemExit("None of the saved runs have graded answers, so there is nothing to chart.")

    ordered_models = models_in_order(runs, entries)
    write_report(args.out, counts, ordered_models)
    notes = write_overview(args.out, entries, ordered_models)
    prompts = {prompt_id for _, prompt_id, _ in counts}
    models = {model for _, _, model in counts}
    print(f"Report from {len(runs)} run(s): {len(prompts)} prompt(s), {len(models)} model(s), {len(entries)} graded answers.")
    for note in notes:
        print(note)
    print(f"Written to {args.out}.")
