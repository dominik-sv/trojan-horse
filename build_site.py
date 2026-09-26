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
            "provider": r["model"].split("/")[0],
            "judged": int(r["judged"]),
            "spotted": int(r["spotted"]),
            "performance": float(r["performance"]),
            "avg_output_tokens": float(r["avg_output_tokens"]),
            "avg_latency_seconds": float(r["avg_latency_seconds"]),
            "cost_per_pass_usd": float(r["cost_per_pass_usd"]),
        })
    models.sort(key=lambda m: -m["performance"])

    prompt_ids = sorted({r["prompt_id"] for r in summary_rows})

    return {
        "prompts": prompt_ids,
        "models": models,
    }


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trojan Horse Benchmark</title>
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7;
  --surface-1: #ffffff;
  --surface-2: #f3f2ef;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #898781;
  --grid: #e6e5e0;
  --baseline: #c3c2b7;
  --border: rgba(11,11,11,0.10);
  --accent: #2a78d6;
  --accent-soft: rgba(42,120,214,0.10);
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0;
  background: var(--page);
  background-image:
    radial-gradient(circle at 15% 0%, rgba(42,120,214,0.06), transparent 45%),
    radial-gradient(circle at 85% 10%, rgba(235,104,52,0.05), transparent 40%);
  background-attachment: fixed;
  color: var(--text-primary);
  font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
}
.wrap { max-width: 1240px; margin: 0 auto; padding: 32px 20px 72px; }
header.top { margin-bottom: 28px; }
h1 { font-size: 1.7rem; margin: 0 0 6px; letter-spacing: -0.01em; }
.subtitle { color: var(--text-secondary); font-size: 0.95rem; margin: 0; max-width: 640px; line-height: 1.5; }

.stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 24px 0; }
.stat-tile {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 18px;
  box-shadow: 0 1px 3px rgba(11,11,11,0.04);
}
.stat-tile .label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin-bottom: 8px; }
.stat-tile .value { font-size: 1.5rem; font-weight: 650; font-variant-numeric: tabular-nums; }
.stat-tile .value.small { font-size: 1.05rem; }
.stat-tile .value .unit { font-size: 0.85rem; color: var(--text-secondary); font-weight: 500; }
.stat-tile .sub { font-size: 0.78rem; color: var(--text-secondary); margin-top: 4px; }

.legend-row {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  margin-bottom: 24px; padding: 14px 16px;
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
}
.legend-title { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); margin-right: 6px; }
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 11px 5px 8px; border-radius: 999px; font-size: 0.8rem;
  border: 1px solid var(--border); background: var(--surface-2);
  cursor: pointer; user-select: none; transition: opacity 0.15s, border-color 0.15s;
  color: var(--text-secondary);
}
.chip .dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.chip.active { color: var(--text-primary); border-color: var(--chip-color, var(--accent)); background: color-mix(in srgb, var(--chip-color, var(--accent)) 16%, var(--surface-2)); }
.chip.inactive { opacity: 0.45; }
.chip-all { font-weight: 600; }

.card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 22px 24px;
  margin-bottom: 22px;
  box-shadow: 0 1px 3px rgba(11,11,11,0.04);
}
.card h2 { font-size: 1.05rem; margin: 0 0 4px; font-weight: 650; }
.card .desc { color: var(--text-secondary); font-size: 0.85rem; margin: 0 0 18px; }

.bar-row { display: flex; align-items: center; gap: 10px; margin: 7px 0; }
.bar-label { width: 230px; flex-shrink: 0; font-size: 0.82rem; text-align: right; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; justify-content: flex-end; gap: 6px; }
.bar-label .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.bar-track { flex: 1; background: var(--grid); border-radius: 5px; height: 20px; position: relative; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 5px; min-width: 3px; transition: width 0.2s; }
.bar-value { font-size: 0.8rem; color: var(--text-secondary); width: 44px; font-variant-numeric: tabular-nums; }
.bar-row.hidden { display: none; }

table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th, td { text-align: right; padding: 8px 12px; border-bottom: 1px solid var(--grid); font-variant-numeric: tabular-nums; }
th:first-child, td:first-child { text-align: left; font-variant-numeric: normal; }
th { color: var(--text-muted); font-weight: 600; cursor: pointer; user-select: none; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; }
th:hover { color: var(--text-primary); }
tbody tr:hover { background: var(--surface-2); }
tr.hidden-row { display: none; }
.model-cell { display: flex; align-items: center; gap: 8px; }
.model-cell .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

.scatter-stack { display: flex; flex-direction: column; gap: 20px; }
svg text { fill: var(--text-muted); font-size: 11px; }
.axis-title { fill: var(--text-secondary) !important; font-size: 12px !important; font-weight: 600; }
.dot-pt { stroke: var(--surface-1); stroke-width: 1.5; cursor: pointer; }
.point-label { fill: var(--text-secondary); font-size: 10px; pointer-events: none; }
.leader-line { stroke: var(--baseline); stroke-width: 1; pointer-events: none; }
.dot-hit { fill: transparent; cursor: pointer; }
.frontier-line { fill: none; stroke: var(--text-secondary); stroke-width: 1.5; stroke-dasharray: 5 4; opacity: 0.6; }
.frontier-pt { fill: none; stroke-width: 2; }

.tooltip {
  position: fixed;
  pointer-events: none;
  background: var(--surface-1);
  border: 1px solid var(--border);
  color: var(--text-primary);
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 0.8rem;
  opacity: 0;
  transform: translate(-50%, -125%);
  white-space: nowrap;
  z-index: 10;
  box-shadow: 0 8px 24px rgba(11,11,11,0.18);
}
.tooltip b { color: var(--text-primary); }
.tooltip .tt-val { font-variant-numeric: tabular-nums; }
.tooltip .tt-row { color: var(--text-secondary); }
.tooltip .tt-row .tt-val { color: var(--text-primary); font-weight: 600; }

footer { color: var(--text-muted); font-size: 0.78rem; text-align: center; margin-top: 36px; }
a { color: var(--accent); }
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>Trojan Horse Benchmark</h1>
    <p class="subtitle">Detection rate for planted false premises across frontier models, graded by a random panel of judge models with majority vote.</p>
  </header>

  <div class="stat-row" id="stat-row"></div>

  <div class="legend-row" id="provider-legend"></div>

  <div class="card">
    <h2>Detection rate by model</h2>
    <p class="desc">Share of graded answers where the model caught and corrected the planted false premise, averaged across all prompts and runs.</p>
    <div id="bar-chart"></div>
  </div>

  <div class="card">
    <h2>Performance vs. cost, tokens, and latency</h2>
    <p class="desc">Each dot is one model, colored by provider. The dashed line traces the efficiency frontier: models no other model beats on both axes at once.</p>
    <div class="scatter-stack">
      <div id="scatter-cost"></div>
      <div id="scatter-tokens"></div>
      <div id="scatter-latency"></div>
    </div>
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

// Fixed provider -> color mapping so colors stay stable across rebuilds.
const PROVIDER_COLORS = {
  openai:      "#2a78d6",
  anthropic:   "#eb6834",
  google:      "#1baf7a",
  spacexai:    "#c98500",
  deepseek:    "#d55181",
  zai:         "#008300",
  alibaba:     "#4a3aa7",
  moonshotai:  "#e34948",
  mistral:     "#8b5e34",
  meta:        "#4d6672",
};
const FALLBACK_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#c98500", "#d55181"];
let fallbackIdx = 0;
function colorFor(provider) {
  if (!PROVIDER_COLORS[provider]) {
    PROVIDER_COLORS[provider] = FALLBACK_COLORS[fallbackIdx++ % FALLBACK_COLORS.length];
  }
  return PROVIDER_COLORS[provider];
}

const providers = [...new Set(DATA.models.map(m => m.provider))].sort();
const activeProviders = new Set(providers);

function shortName(m) { return m.split("/")[1] || m; }
function fmtPct(x) { return (x * 100).toFixed(0) + "%"; }
function visibleModels() { return DATA.models.filter(m => activeProviders.has(m.provider)); }

const tooltip = document.getElementById("tooltip");
function showTip(evt, html) {
  tooltip.innerHTML = html;
  tooltip.style.left = evt.clientX + "px";
  tooltip.style.top = evt.clientY + "px";
  tooltip.style.opacity = 1;
}
function hideTip() { tooltip.style.opacity = 0; }

const renderers = [];
function rerenderAll() { renderers.forEach(fn => fn()); }

// ---- provider legend ----
(function renderLegend() {
  const el = document.getElementById("provider-legend");
  function draw() {
    const allOn = activeProviders.size === providers.length;
    let html = '<span class="legend-title">Providers</span>';
    html += `<span class="chip chip-all" id="chip-all">${allOn ? "Clear all" : "Select all"}</span>`;
    providers.forEach(p => {
      const c = colorFor(p);
      const active = activeProviders.has(p);
      html += `<span class="chip ${active ? 'active' : 'inactive'}" data-provider="${p}" style="--chip-color:${c}"><span class="dot" style="background:${c}"></span>${p}</span>`;
    });
    el.innerHTML = html;
    el.querySelectorAll(".chip[data-provider]").forEach(chip => {
      chip.addEventListener("click", () => {
        const p = chip.dataset.provider;
        if (activeProviders.has(p)) activeProviders.delete(p); else activeProviders.add(p);
        draw();
        rerenderAll();
      });
    });
    el.querySelector("#chip-all").addEventListener("click", () => {
      if (activeProviders.size === providers.length) { activeProviders.clear(); }
      else { providers.forEach(p => activeProviders.add(p)); }
      draw();
      rerenderAll();
    });
  }
  draw();
})();

// ---- stat tiles ----
(function renderStats() {
  const el = document.getElementById("stat-row");
  function draw() {
    const vis = visibleModels();
    const totalJudged = vis.reduce((s, m) => s + m.judged, 0);
    const top = [...vis].sort((a, b) => b.performance - a.performance)[0];
    const cheapestPerfect = [...vis].filter(m => m.performance >= 0.99).sort((a, b) => a.cost_per_pass_usd - b.cost_per_pass_usd)[0];
    const tiles = [
      { label: "Models shown", value: vis.length },
      { label: "Prompts", value: DATA.prompts.length },
      { label: "Graded answers", value: totalJudged },
      { label: "Top detector", value: top ? fmtPct(top.performance) : "-", sub: top ? shortName(top.model) : "" },
      { label: "Cheapest at 100%", value: cheapestPerfect ? "$" + cheapestPerfect.cost_per_pass_usd.toFixed(3) : "none", sub: cheapestPerfect ? shortName(cheapestPerfect.model) : "no model hit 100%" },
    ];
    el.innerHTML = tiles.map(t => `
      <div class="stat-tile">
        <div class="label">${t.label}</div>
        <div class="value ${String(t.value).length > 6 ? 'small' : ''}">${t.value}</div>
        ${t.sub ? `<div class="sub">${t.sub}</div>` : ""}
      </div>`).join("");
  }
  renderers.push(draw);
  draw();
})();

// ---- bar chart ----
(function renderBars() {
  const el = document.getElementById("bar-chart");
  function draw() {
    const rows = [...DATA.models].sort((a, b) => b.performance - a.performance);
    el.innerHTML = rows.map(m => {
      const c = colorFor(m.provider);
      const hidden = activeProviders.has(m.provider) ? "" : "hidden";
      return `
      <div class="bar-row ${hidden}">
        <div class="bar-label" title="${m.model}"><span class="dot" style="background:${c}"></span>${shortName(m.model)}</div>
        <div class="bar-track">
          <div class="bar-fill" style="width:${(m.performance * 100).toFixed(1)}%; background:${c};"></div>
        </div>
        <div class="bar-value">${fmtPct(m.performance)}</div>
      </div>`;
    }).join("");
  }
  renderers.push(draw);
  draw();
})();

// ---- scatter charts with pareto frontier ----
function computeFrontier(points, xKey) {
  const sorted = [...points].filter(p => p.performance > 0).sort((a, b) => a[xKey] - b[xKey]);
  const frontier = [];
  let runningMax = -Infinity;
  sorted.forEach(p => {
    if (p.performance > runningMax) {
      frontier.push(p);
      runningMax = p.performance;
    }
  });
  return frontier;
}

function scatterChart(containerId, xKey, xLabel, xFmt) {
  const el = document.getElementById(containerId);
  const W = 1000, H = 380, PAD_L = 56, PAD_B = 44, PAD_T = 16, PAD_R = 20;

  function draw() {
    const pts = visibleModels();
    el.innerHTML = "";
    if (pts.length === 0) { el.innerHTML = '<p style="color:var(--text-muted); font-size:0.85rem;">No providers selected.</p>'; return; }

    const xsPos = pts.map(m => m[xKey]).filter(v => v > 0);
    const dataMin = Math.min(...xsPos);
    const dataMax = Math.max(...xsPos);
    const xMin = dataMin / 1.3;
    const xMax = dataMax * 1.3;
    const logMin = Math.log(xMin), logMax = Math.log(xMax);

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("width", "100%");
    svg.setAttribute("preserveAspectRatio", "xMinYMin meet");
    svg.style.display = "block";

    function sx(v) { return PAD_L + (Math.log(Math.max(v, xMin)) - logMin) / (logMax - logMin) * (W - PAD_L - PAD_R); }
    function sy(v) { return H - PAD_B - v * (H - PAD_B - PAD_T); }

    function logTicks(min, max) {
      const ticks = [];
      const kMin = Math.floor(Math.log10(min));
      const kMax = Math.ceil(Math.log10(max));
      for (let k = kMin; k <= kMax; k++) {
        for (const a of [1, 2, 5]) {
          const v = a * Math.pow(10, k);
          if (v >= min * 0.999 && v <= max * 1.001) ticks.push(v);
        }
      }
      return ticks;
    }

    let inner = "";
    [0, 0.25, 0.5, 0.75, 1].forEach(t => {
      inner += `<line x1="${PAD_L}" y1="${sy(t)}" x2="${W - PAD_R}" y2="${sy(t)}" stroke="var(--grid)" stroke-width="1"/>`;
      inner += `<text x="${PAD_L - 8}" y="${sy(t) + 4}" text-anchor="end">${(t*100).toFixed(0)}%</text>`;
    });
    logTicks(dataMin, dataMax).forEach(v => {
      inner += `<line x1="${sx(v)}" y1="${PAD_T}" x2="${sx(v)}" y2="${H - PAD_B}" stroke="var(--grid)" stroke-width="1"/>`;
      inner += `<text x="${sx(v)}" y="${H - PAD_B + 18}" text-anchor="middle">${xFmt(v)}</text>`;
    });
    inner += `<line x1="${PAD_L}" y1="${H-PAD_B}" x2="${W-PAD_R}" y2="${H-PAD_B}" stroke="var(--baseline)" stroke-width="1"/>`;
    inner += `<text class="axis-title" x="${(W)/2}" y="${H-4}" text-anchor="middle">${xLabel}</text>`;
    inner += `<text class="axis-title" x="${-H/2}" y="16" text-anchor="middle" transform="rotate(-90)">detection rate</text>`;

    const frontier = computeFrontier(pts, xKey);
    if (frontier.length > 1) {
      const path = frontier.map((p, i) => `${i === 0 ? "M" : "L"}${sx(p[xKey])},${sy(p.performance)}`).join(" ");
      inner += `<path class="frontier-line" d="${path}"/>`;
    }

    svg.innerHTML = inner;

    const frontierSet = new Set(frontier.map(p => p.model));

    // Layout: points close together on X get their labels dodged apart
    // vertically (stacked with a minimum gap), each with a leader line back
    // to its dot, so a cluster of near-identical values stays readable.
    const items = pts.map(m => ({
      m, cx: sx(m[xKey]), cy: sy(m.performance),
      label: shortName(m.model),
    })).sort((a, b) => a.cx - b.cx || a.cy - b.cy);

    const minGap = 13, xWindow = 68;
    const placed = [];
    items.forEach(it => {
      let y = it.cy;
      let conflict = true;
      while (conflict) {
        conflict = false;
        for (const p of placed) {
          if (Math.abs(p.cx - it.cx) < xWindow && Math.abs(p.yLabel - y) < minGap) {
            y = p.yLabel + minGap;
            conflict = true;
          }
        }
      }
      it.yLabel = Math.min(y, H - PAD_B - 4);
      placed.push({ cx: it.cx, yLabel: it.yLabel });
    });

    items.forEach(it => {
      const { m, cx, cy } = it;
      const c = colorFor(m.provider);
      const onFrontier = frontierSet.has(m.model);
      const yLabel = it.yLabel;
      const dodged = Math.abs(yLabel - cy) > 2;

      const hit = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      hit.setAttribute("cx", cx); hit.setAttribute("cy", cy); hit.setAttribute("r", 13);
      hit.classList.add("dot-hit");

      const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      dot.setAttribute("cx", cx); dot.setAttribute("cy", cy);
      dot.setAttribute("r", onFrontier ? 6.5 : 5);
      dot.setAttribute("fill", c);
      dot.classList.add("dot-pt");
      if (onFrontier) { dot.style.filter = `drop-shadow(0 0 4px ${c})`; }

      const nearRight = cx > W - PAD_R - 90;
      const labelX = nearRight ? cx - 9 : cx + 9;

      let leader = null;
      if (dodged) {
        leader = document.createElementNS("http://www.w3.org/2000/svg", "line");
        leader.setAttribute("x1", cx); leader.setAttribute("y1", cy);
        leader.setAttribute("x2", nearRight ? cx - 5 : cx + 5); leader.setAttribute("y2", yLabel);
        leader.setAttribute("class", "leader-line");
      }

      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", labelX);
      label.setAttribute("y", yLabel + 3);
      label.setAttribute("text-anchor", nearRight ? "end" : "start");
      label.setAttribute("class", "point-label");
      label.textContent = it.label;

      const tip = (e) => showTip(e, `
        <div><b>${m.model}</b></div>
        <div class="tt-row">${xLabel}: <span class="tt-val">${xFmt(m[xKey])}</span></div>
        <div class="tt-row">detection: <span class="tt-val">${fmtPct(m.performance)}</span></div>
        ${onFrontier ? '<div class="tt-row" style="color:var(--accent)">on efficiency frontier</div>' : ''}
      `);
      hit.addEventListener("mousemove", tip);
      hit.addEventListener("mouseleave", hideTip);

      if (leader) svg.appendChild(leader);
      svg.appendChild(hit);
      svg.appendChild(dot);
      svg.appendChild(label);
    });

    el.appendChild(svg);
  }
  renderers.push(draw);
  draw();
}

scatterChart("scatter-cost", "cost_per_pass_usd", "cost per pass ($, log scale)", v => v < 0.01 ? "$" + v.toFixed(3) : "$" + v.toFixed(2));
scatterChart("scatter-tokens", "avg_output_tokens", "avg output tokens (log scale)", v => v.toFixed(0));
scatterChart("scatter-latency", "avg_latency_seconds", "avg latency (s, log scale)", v => v.toFixed(0) + "s");

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
    const rows = visibleModels().sort((a, b) => {
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
      const c = colorFor(m.provider);
      html += "<tr>" + cols.map(([key, label, get, fmt], i) => {
        const v = get(m);
        if (i === 0) return `<td><div class="model-cell"><span class="dot" style="background:${c}"></span>${v}</div></td>`;
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
  renderers.push(draw);
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
