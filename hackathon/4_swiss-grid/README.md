# Trojan Horse Benchmark — Swiss Grid Edition

## Concept

A dashboard built like a Müller-Brockmann poster: a strict 12-column grid you can
literally turn on (top-right "Show grid" toggle reveals the underlying columns
in red), one workhorse grotesk typeface (Inter) at a small, disciplined type
scale, and exactly one accent color — signal red — used consistently for
exactly one thing: the trojan horse getting caught (detection). Everything
else lives in near-black ink on warm off-white paper. No gradients, no
shadows, no rounded corners, no card chrome — hairline rules and 1-3px strokes
do all the separating.

## Why these choices

- **Oversized numeral masthead + numbered stat cells** (01–04) borrow directly
  from Swiss poster conventions: big confident type up top, then a strip of
  indexed facts that read like museum wall labels, not "KPI cards."
- **The ranked bar list** replaces a conventional bar chart with something
  closer to a results sheet: rank number, name, provider, a thin red track,
  and the raw fraction (spotted/judged) — every number that matters sits on
  one line, right-aligned, in tabular monospace figures so the columns line
  up like a ledger.
- **Hand-drawn SVG scatters with log-x axes** (cost, tokens, latency vs.
  detection) are stripped to axis lines, tick hairlines, and small red dots —
  no legends, no drop shadows. Clicking a dot, a rank row, or a table row
  cross-highlights the same model everywhere (a single shared `activeIdx`
  state), which is the one bit of "flair" I allowed myself: precision and
  linkage instead of decoration.
- **The full data table** is the browsable source of truth: every column
  sortable by click, monospace tabular numerals throughout, no zebra striping
  (that would be ornament without informational purpose) — only the header
  rule and row hairlines carry the structure.
- Single file, no build step, no external data fetch — data is embedded as a
  plain JS array taken verbatim from `report/models.csv`, so it opens directly
  via `file://`.
