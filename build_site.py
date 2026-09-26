"""Build docs/index.html (a static, GitHub Pages-ready dashboard) from report/*.csv.

Run `python visualize.py` first to (re)build report/, then run this script and
commit the docs/ folder. This script makes no network calls and costs nothing.
"""

import csv
import json
from pathlib import Path

REPORT_DIR = Path("report")
DOCS_DIR = Path("docs")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_data():
    models_rows = read_csv(REPORT_DIR / "models.csv")
    summary_rows = read_csv(REPORT_DIR / "summary.csv")

    models = []
    for r in models_rows:
        models.append({
            "model": r["model"],
            "judged": int(r["judged"]),
            "spotted": int(r["spotted"]),
            "performance": float(r["performance"]),
            "avg_output_tokens": float(r["avg_output_tokens"]),
            "avg_latency_seconds": float(r["avg_latency_seconds"]),
            "cost_per_pass_usd": float(r["cost_per_pass_usd"]),
        })
    models.sort(key=lambda m: -m["performance"])

    prompt_ids = sorted({r["prompt_id"] for r in summary_rows})
    by_model = {}
    for r in summary_rows:
        by_model.setdefault(r["model"], {})[r["prompt_id"]] = {
            "rate": float(r["rate"]),
            "judged": int(r["judged"]),
            "spotted": int(r["spotted"]),
        }

    return {
        "prompts": prompt_ids,
        "models": models,
        "byPrompt": by_model,
    }


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>False-Premise LLM Benchmark</title>
<style>
:root {
  color-scheme: light;
  --surface-1: #fcfcfb;
  --page: #f9f9f7;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #898781;
  --grid: #e1e0d9;
  --baseline: #c3c2b7;
  --border: rgba(11,11,11,0.10);
  --series-1: #2a78d6;
  --series-1-light: #cde2fb;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --surface-1: #1a1a19;
    --page: #0d0d0d;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #898781;
    --grid: #2c2c2a;
    --baseline: #383835;
    --border: rgba(255,255,255,0.10);
    --series-1: #3987e5;
    --series-1-light: #184f95;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-1: #1a1a19;
  --page: #0d0d0d;
  --text-primary: #ffffff;
  --text-secondary: #c3c2b7;
  --text-muted: #898781;
  --grid: #2c2c2a;
  --baseline: #383835;
  --border: rgba(255,255,255,0.10);
  --series-1: #3987e5;
  --series-1-light: #184f95;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--page);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}
.wrap { max-width: 1100px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 1.5rem; margin: 0 0 4px; }
.subtitle { color: var(--text-secondary); font-size: 0.9rem; margin: 0 0 24px; }
.card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 24px;
}
.card h2 { font-size: 1.05rem; margin: 0 0 4px; }
.card .desc { color: var(--text-secondary); font-size: 0.85rem; margin: 0 0 16px; }
.bar-row { display: flex; align-items: center; gap: 10px; margin: 6px 0; }
.bar-label { width: 220px; flex-shrink: 0; font-size: 0.82rem; text-align: right; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bar-track { flex: 1; background: var(--grid); border-radius: 4px; height: 18px; position: relative; }
.bar-fill { background: var(--series-1); height: 100%; border-radius: 4px; min-width: 2px; }
.bar-value { font-size: 0.78rem; color: var(--text-secondary); width: 44px; font-variant-numeric: tabular-nums; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th, td { text-align: right; padding: 6px 10px; border-bottom: 1px solid var(--grid); font-variant-numeric: tabular-nums; }
th:first-child, td:first-child { text-align: left; font-variant-numeric: normal; }
th { color: var(--text-muted); font-weight: 600; cursor: pointer; user-select: none; }
th:hover { color: var(--text-primary); }
tbody tr:hover { background: var(--series-1-light); }
.scatter-wrap { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
svg text { fill: var(--text-muted); font-size: 10px; }
.axis-title { fill: var(--text-secondary) !important; font-size: 11px !important; }
.dot { fill: var(--series-1); stroke: var(--surface-1); stroke-width: 1.5; cursor: pointer; }
.dot:hover { fill: var(--text-primary); }
.tooltip {
  position: fixed;
  pointer-events: none;
  background: var(--text-primary);
  color: var(--surface-1);
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.78rem;
  opacity: 0;
  transform: translate(-50%, -130%);
  white-space: nowrap;
  z-index: 10;
}
.heat-cell { padding: 4px 8px; text-align: center; border-radius: 4px; font-variant-numeric: tabular-nums; }
.meta-pills { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.pill { background: var(--grid); color: var(--text-secondary); border-radius: 999px; padding: 3px 10px; font-size: 0.78rem; }
footer { color: var(--text-muted); font-size: 0.78rem; text-align: center; margin-top: 32px; }
a { color: var(--series-1); }
</style>
</head>
<body>
<div class="wrap">
  <h1>False-Premise LLM Benchmark</h1>
  <p class="subtitle">Detection rate for planted false premises, graded by a random panel of judge models with majority vote.</p>

  <div class="card">
    <div class="meta-pills" id="meta-pills"></div>
  </div>

  <div class="card">
    <h2>Detection rate by model</h2>
    <p class="desc">Share of graded answers where the model caught and corrected the planted false premise, averaged across all prompts and runs.</p>
    <div id="bar-chart"></div>
  </div>

  <div class="card">
    <h2>Performance vs. cost, tokens, latency</h2>
    <p class="desc">Each dot is one model. Hover for details.</p>
    <div class="scatter-wrap">
      <div id="scatter-cost"></div>
      <div id="scatter-tokens"></div>
      <div id="scatter-latency"></div>
    </div>
  </div>

  <div class="card">
    <h2>Detection rate by prompt</h2>
    <p class="desc">One cell per model x prompt, colored by detection rate (darker = higher).</p>
    <div id="heatmap" style="overflow-x:auto;"></div>
  </div>

  <div class="card">
    <h2>Full results</h2>
    <p class="desc">Click a column header to sort.</p>
    <div id="table-wrap" style="overflow-x:auto;"></div>
  </div>

  <footer>Generated by build_site.py from report/summary.csv and report/models.csv. No network calls, no API costs to view.</footer>
</div>
<div class="tooltip" id="tooltip"></div>

<script>
const DATA = __DATA__;

function shortName(m) { return m.split("/")[1] || m; }
function providerOf(m) { return m.split("/")[0]; }
function fmtPct(x) { return (x * 100).toFixed(0) + "%"; }

const tooltip = document.getElementById("tooltip");
function showTip(evt, html) {
  tooltip.innerHTML = html;
  tooltip.style.left = evt.clientX + "px";
  tooltip.style.top = evt.clientY + "px";
  tooltip.style.opacity = 1;
}
function hideTip() { tooltip.style.opacity = 0; }

// ---- meta pills ----
(function renderMeta() {
  const el = document.getElementById("meta-pills");
  const n = DATA.models.length;
  const totalJudged = DATA.models.reduce((s, m) => s + m.judged, 0);
  const pills = [
    n + " models",
    DATA.prompts.length + " prompts",
    totalJudged + " graded answers",
  ];
  el.innerHTML = pills.map(p => `<span class="pill">${p}</span>`).join("");
})();

// ---- bar chart ----
(function renderBars() {
  const el = document.getElementById("bar-chart");
  const max = 1.0;
  el.innerHTML = DATA.models.map(m => `
    <div class="bar-row">
      <div class="bar-label" title="${m.model}">${shortName(m.model)}</div>
      <div class="bar-track">
        <div class="bar-fill" style="width:${(m.performance / max * 100).toFixed(1)}%"></div>
      </div>
      <div class="bar-value">${fmtPct(m.performance)}</div>
    </div>
  `).join("");
})();

// ---- scatter charts ----
function scatter(containerId, xKey, xLabel, xFmt) {
  const el = document.getElementById(containerId);
  const W = 320, H = 260, PAD = 40;
  const xs = DATA.models.map(m => m[xKey]);
  const xMax = Math.max(...xs) * 1.1 || 1;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("width", "100%");

  function sx(v) { return PAD + (v / xMax) * (W - PAD - 15); }
  function sy(v) { return H - PAD - v * (H - PAD - 15); }

  let inner = "";
  // gridlines + y axis ticks (0, 0.5, 1)
  [0, 0.25, 0.5, 0.75, 1].forEach(t => {
    inner += `<line x1="${PAD}" y1="${sy(t)}" x2="${W - 10}" y2="${sy(t)}" stroke="var(--grid)" stroke-width="1"/>`;
    inner += `<text x="${PAD - 6}" y="${sy(t) + 3}" text-anchor="end">${(t*100).toFixed(0)}%</text>`;
  });
  // x axis ticks
  [0, 0.5, 1].forEach(f => {
    const v = xMax * f;
    inner += `<text x="${sx(v)}" y="${H - PAD + 14}" text-anchor="middle">${xFmt(v)}</text>`;
  });
  inner += `<line x1="${PAD}" y1="${H-PAD}" x2="${W-10}" y2="${H-PAD}" stroke="var(--baseline)" stroke-width="1"/>`;
  inner += `<text class="axis-title" x="${(W)/2}" y="${H-4}" text-anchor="middle">${xLabel}</text>`;

  svg.innerHTML = inner;

  DATA.models.forEach(m => {
    const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    c.setAttribute("cx", sx(m[xKey]));
    c.setAttribute("cy", sy(m.performance));
    c.setAttribute("r", 5);
    c.classList.add("dot");
    c.addEventListener("mousemove", (e) => showTip(e, `<b>${m.model}</b><br>${xLabel}: ${xFmt(m[xKey])}<br>detection: ${fmtPct(m.performance)}`));
    c.addEventListener("mouseleave", hideTip);
    svg.appendChild(c);
  });

  el.appendChild(svg);
}

scatter("scatter-cost", "cost_per_pass_usd", "cost per pass ($)", v => "$" + v.toFixed(2));
scatter("scatter-tokens", "avg_output_tokens", "avg output tokens", v => v.toFixed(0));
scatter("scatter-latency", "avg_latency_seconds", "avg latency (s)", v => v.toFixed(0) + "s");

// ---- heatmap ----
(function renderHeatmap() {
  const el = document.getElementById("heatmap");
  const prompts = DATA.prompts;
  let html = '<table><thead><tr><th>model</th>' + prompts.map(p => `<th>${p}</th>`).join("") + '</tr></thead><tbody>';
  DATA.models.forEach(m => {
    html += `<tr><td>${shortName(m.model)}</td>`;
    prompts.forEach(p => {
      const cell = (DATA.byPrompt[m.model] || {})[p];
      const rate = cell ? cell.rate : null;
      if (rate === null) {
        html += `<td>-</td>`;
      } else {
        const bg = `color-mix(in srgb, var(--series-1) ${(rate*100).toFixed(0)}%, var(--surface-1))`;
        const fg = rate > 0.55 ? "#fff" : "var(--text-primary)";
        html += `<td><span class="heat-cell" style="background:${bg}; color:${fg};">${fmtPct(rate)}</span></td>`;
      }
    });
    html += "</tr>";
  });
  html += "</tbody></table>";
  el.innerHTML = html;
})();

// ---- full table ----
(function renderTable() {
  const el = document.getElementById("table-wrap");
  const cols = [
    ["model", "model", m => m.model],
    ["performance", "detection", m => m.performance, fmtPct],
    ["judged", "judged", m => m.judged],
    ["spotted", "spotted", m => m.spotted],
    ["avg_output_tokens", "avg tokens", m => m.avg_output_tokens, v => v.toFixed(0)],
    ["avg_latency_seconds", "avg latency (s)", m => m.avg_latency_seconds, v => v.toFixed(1)],
    ["cost_per_pass_usd", "cost/pass ($)", m => m.cost_per_pass_usd, v => "$" + v.toFixed(4)],
  ];
  let sortKey = "performance", sortDir = -1;

  function draw() {
    const rows = [...DATA.models].sort((a, b) => {
      const va = cols.find(c => c[0] === sortKey)[2](a);
      const vb = cols.find(c => c[0] === sortKey)[2](b);
      if (va < vb) return -1 * sortDir;
      if (va > vb) return 1 * sortDir;
      return 0;
    });
    let html = "<table><thead><tr>" + cols.map(([key, label]) =>
      `<th data-key="${key}">${label}${sortKey === key ? (sortDir === 1 ? " ^" : " v") : ""}</th>`
    ).join("") + "</tr></thead><tbody>";
    rows.forEach(m => {
      html += "<tr>" + cols.map(([key, label, get, fmt]) => {
        const v = get(m);
        return `<td>${fmt ? fmt(v) : v}</td>`;
      }).join("") + "</tr>";
    });
    html += "</tbody></table>";
    el.innerHTML = html;
    el.querySelectorAll("th").forEach(th => {
      th.addEventListener("click", () => {
        const key = th.dataset.key;
        if (sortKey === key) sortDir *= -1; else { sortKey = key; sortDir = -1; }
        draw();
      });
    });
  }
  draw();
})();
</script>
</body>
</html>
"""


def main():
    data = build_data()
    DOCS_DIR.mkdir(exist_ok=True)
    html = TEMPLATE.replace("__DATA__", json.dumps(data))
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Written to {DOCS_DIR / 'index.html'} ({len(data['models'])} models, {len(data['prompts'])} prompts)")


if __name__ == "__main__":
    main()
