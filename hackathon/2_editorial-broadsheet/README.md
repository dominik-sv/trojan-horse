# The Trojan Horse Report — Editorial Broadsheet

## Concept

This entry treats the benchmark results as the subject of a print investigation, not a
product dashboard. The framing device is a fictional special-report front page — a
masthead, a dateline bar, a byline, a lead story with a drop cap and a pull-out stat
rail, numbered exhibits ("Fig. 1", "Exhibit A–D"), figure captions that argue a point
rather than just describe an axis, and pull-quotes set in italic display serif with a
crimson rule, the way a magazine cover story would break out its most damning line.
The goal was to make the reader feel like they're reading a story about AI honesty,
with the data as evidence, rather than scanning a control panel.

## Why these choices

- **Serif display (Playfair Display) for headlines, serif body (Source Serif 4) for
  running text, sans (Libre Franklin) reserved for chrome** — captions, axis labels,
  table headers, small caps — mirrors how a broadsheet actually typesets: display
  serif for voice, a workhorse grotesque for anything functional or tabular.
- **Status color, not identity color.** With 10 providers in the field, a categorical
  legend would have needed 10 safely-distinguishable hues — not achievable per the
  dataviz method's own CVD gates past 3–4 slots. Instead, color encodes the one thing
  that actually matters editorially: a four-tier honesty band (Honest / Hedges /
  Evasive / Sycophantic), using the method's reserved status palette, always paired
  with a text label so the color is never load-bearing alone.
- **Three exhibits, one point each.** Fig. 1 is the ranked league table (who's
  honest). Figs. 2–3 are log-x scatters (cost and verbosity don't predict honesty).
  Exhibit D is the full sortable box score, so nothing in the aggregate CSV is lost —
  click any header to re-sort by any metric.
- **The copy does real analytical work.** Median (15%) is reported alongside mean
  (29%) specifically because they tell different stories — the mean is dragged up by
  two perfect scores while most of the field clusters near zero. The commentary calls
  out same-company divergence (Claude Opus 5.5 at 95% vs. Claude Sonnet 5 and Haiku
  4.5 at 0%) because it's the most surprising finding in the dataset: provider is not
  destiny.
- **Self-contained, no server.** All twenty rows are embedded as a JS array; charts
  are hand-built inline SVG (no charting library dependency) so the file opens
  directly via `file://` with full interactivity — hover tooltips on every mark,
  click-to-sort on the table.
