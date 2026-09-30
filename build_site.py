"""Build docs/index.html (a static, GitHub Pages-ready dashboard) from report/*.csv.

Run `python visualize.py` first to (re)build report/, then run this script and
commit the docs/ folder. This script makes no network calls and costs nothing.
"""

import csv
import json
from pathlib import Path

REPORT_DIR = Path("report")
DOCS_DIR = Path("docs")

# Headquarters country per provider - a clean 1:1, since every provider here is one company.
PROVIDER_COUNTRY = {
    "openai": "USA", "anthropic": "USA", "google": "USA", "spacexai": "USA",
    "deepseek": "China", "zai": "China", "alibaba": "China", "moonshotai": "China",
    "mistral": "France", "meta": "USA",
}
# Whether a provider's models ship as open weights by default. A provider's flagship model
# can diverge from this (see MODEL_LICENSE_OVERRIDE) even when they also ship open models.
PROVIDER_LICENSE = {
    "openai": "closed", "anthropic": "closed", "google": "closed", "spacexai": "closed",
    "deepseek": "open", "zai": "open", "alibaba": "open", "moonshotai": "open",
    "mistral": "open", "meta": "open",
}
MODEL_LICENSE_OVERRIDE = {
    "qwen3.8-max": "closed",  # Alibaba's proprietary top tier, unlike their open Qwen weights
    "mistral-large-3": "closed",  # Mistral's commercial flagship, unlike their open models
}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_data():
    models_rows = read_csv(REPORT_DIR / "models.csv")
    summary_rows = read_csv(REPORT_DIR / "summary.csv")

    models = []
    for r in models_rows:
        provider, _, short_name = r["model"].partition("/")
        models.append({
            "model": r["model"],
            "provider": provider,
            "license": MODEL_LICENSE_OVERRIDE.get(short_name, PROVIDER_LICENSE.get(provider, "closed")),
            "country": PROVIDER_COUNTRY.get(provider, "other"),
            "judged": int(r["judged"]),
            "spotted": int(r["spotted"]),
            "performance": float(r["performance"]),
            "avg_output_tokens": float(r["avg_output_tokens"]),
            "avg_latency_seconds": float(r["avg_latency_seconds"]),
            "cost_per_pass_usd": float(r["cost_per_pass_usd"]) if r["cost_per_pass_usd"] else None,
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,900;1,600&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,500;0,8..60,600;1,8..60,400&family=Libre+Franklin:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {
  color-scheme: light;
  --page: #efe8d8;
  --surface-1: #fbf8f1;
  --surface-2: #f1dcd7;
  --text-primary: #191510;
  --text-secondary: #4a4234;
  --text-muted: #8a7f6a;
  --grid: #ddd3ba;
  --baseline: #c9bfa8;
  --border: rgba(25,21,16,0.14);
  --accent: #a3161a;
  --accent-soft: rgba(163,22,26,0.10);
  --serif-display: "Playfair Display", Georgia, "Times New Roman", serif;
  --serif-body: "Source Serif 4", Georgia, "Times New Roman", serif;
  --sans: "Libre Franklin", "Segoe UI", Arial, sans-serif;
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0;
  background: var(--page);
  color: var(--text-primary);
  font-family: var(--serif-body);
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1240px; margin: 0 auto; padding: 32px 20px 72px; }
header.top { margin-bottom: 28px; border-bottom: 3px double var(--text-primary); padding-bottom: 18px; }
h1 { font-family: var(--serif-display); font-weight: 900; font-size: 2.1rem; margin: 0 0 8px; letter-spacing: -0.01em; }
.subtitle { font-family: var(--sans); color: var(--text-secondary); font-size: 0.9rem; margin: 0; max-width: 640px; line-height: 1.5; }

.stat-row { display: flex; flex-wrap: wrap; gap: 12px; margin: 24px 0; }
.stat-tile {
  flex: 0 1 220px;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-top: 2px solid var(--text-primary);
  border-radius: 2px;
  padding: 16px 18px;
}
.stat-tile .label { font-family: var(--sans); font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.09em; font-weight: 700; color: var(--text-muted); margin-bottom: 8px; }
.stat-tile .value { font-family: var(--serif-display); font-size: 1.65rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.stat-tile .value.small { font-size: 1.15rem; }
.stat-tile .value .unit { font-size: 0.85rem; color: var(--text-secondary); font-weight: 500; }
.stat-tile .sub { font-family: var(--sans); font-size: 0.76rem; color: var(--text-secondary); margin-top: 4px; }
.stat-tile.grouped { flex-basis: auto; }
.group-row { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.group-box {
  border: 1px solid var(--border); border-left: 3px solid var(--box-color, var(--accent));
  border-radius: 2px; padding: 7px 11px; background: var(--page); min-width: 68px;
}
.group-box .key { font-family: var(--sans); font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; color: var(--text-muted); }
.group-box .val { font-family: var(--serif-display); font-size: 1.1rem; font-weight: 700; margin-top: 2px; font-variant-numeric: tabular-nums; }

.legend-row {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  margin-bottom: 24px; padding: 14px 16px;
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 2px;
}
.legend-title { font-family: var(--sans); font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.09em; font-weight: 700; color: var(--text-muted); margin-right: 6px; }
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 11px 5px 8px; border-radius: 999px; font-family: var(--sans); font-size: 0.78rem; font-weight: 600;
  border: 1px solid var(--border); background: var(--surface-1);
  cursor: pointer; user-select: none; transition: opacity 0.15s, border-color 0.15s;
  color: var(--text-secondary);
}
.chip .dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.chip.active { color: var(--text-primary); border-color: var(--chip-color, var(--accent)); background: color-mix(in srgb, var(--chip-color, var(--accent)) 14%, var(--surface-1)); }
.chip.inactive { opacity: 0.45; }
.chip-all { font-weight: 700; }

.dim-switch { display: flex; gap: 4px; margin-right: 10px; }
.dim-switch button {
  font-family: var(--sans); font-size: 0.74rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
  padding: 5px 10px; border-radius: 999px; border: 1px solid var(--border); background: var(--surface-1);
  color: var(--text-secondary); cursor: pointer;
}
.dim-switch button.active { color: #fff; background: var(--accent); border-color: var(--accent); }

.card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: 22px 24px;
  margin-bottom: 22px;
}
.card h2 { font-family: var(--serif-display); font-size: 1.3rem; margin: 0 0 4px; font-weight: 700; }
.card .desc { font-family: var(--sans); color: var(--text-secondary); font-size: 0.82rem; margin: 0 0 18px; }

.bar-row { display: flex; align-items: center; gap: 10px; margin: 7px 0; }
.bar-label { width: 230px; flex-shrink: 0; font-family: var(--sans); font-size: 0.8rem; font-weight: 500; text-align: right; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; justify-content: flex-end; gap: 6px; }
.bar-label .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.bar-track { flex: 1; background: var(--grid); border-radius: 2px; height: 18px; position: relative; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 2px; min-width: 3px; transition: width 0.2s; }
.bar-value { font-family: var(--sans); font-size: 0.78rem; font-weight: 600; color: var(--text-secondary); width: 44px; font-variant-numeric: tabular-nums; }
.bar-row.hidden { display: none; }

.scatter-stack { display: flex; flex-direction: column; gap: 20px; }
.toggle-extra {
  align-self: flex-start;
  font-family: var(--sans); font-size: 0.78rem; font-weight: 600;
  color: var(--accent); background: none; border: 1px solid var(--border);
  border-radius: 2px; padding: 6px 12px; cursor: pointer;
}
.toggle-extra:hover { border-color: var(--accent); }
#extra-scatters { display: flex; flex-direction: column; gap: 20px; }
#extra-scatters[hidden] { display: none; }
svg text { fill: var(--text-muted); font-family: var(--sans); font-size: 11px; }
.axis-title { fill: var(--text-secondary) !important; font-size: 12px !important; font-weight: 700; }
.dot-pt { stroke: var(--surface-1); stroke-width: 1.5; cursor: pointer; }
.point-label { fill: var(--text-secondary); font-family: var(--sans); font-size: 10px; pointer-events: none; }
.leader-line { stroke: var(--baseline); stroke-width: 1; pointer-events: none; }
.dot-hit { fill: transparent; cursor: pointer; }
.frontier-line { fill: none; stroke: var(--text-secondary); stroke-width: 1.5; stroke-dasharray: 5 4; opacity: 0.6; }
.frontier-pt { fill: none; stroke-width: 2; }

.tooltip {
  position: fixed;
  pointer-events: none;
  background: var(--surface-1);
  border: 1px solid var(--text-primary);
  color: var(--text-primary);
  padding: 8px 12px;
  border-radius: 2px;
  font-family: var(--sans);
  font-size: 0.8rem;
  opacity: 0;
  transform: translate(-50%, -125%);
  white-space: nowrap;
  z-index: 10;
  box-shadow: 3px 3px 0 rgba(25,21,16,0.12);
}
.tooltip b { color: var(--text-primary); }
.tooltip .tt-val { font-variant-numeric: tabular-nums; }
.tooltip .tt-row { color: var(--text-secondary); }
.tooltip .tt-row .tt-val { color: var(--text-primary); font-weight: 600; }

footer { font-family: var(--sans); color: var(--text-muted); font-size: 0.78rem; text-align: center; margin-top: 36px; }
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
      <button class="toggle-extra" id="toggle-extra-scatters">Show tokens &amp; latency charts</button>
      <div id="extra-scatters" hidden>
        <div id="scatter-tokens"></div>
        <div id="scatter-latency"></div>
      </div>
    </div>
  </div>

  <footer>Generated by build_site.py from report/summary.csv and report/models.csv. No network calls, no API costs to view.</footer>
</div>
<div class="tooltip" id="tooltip"></div>

<script>
const DATA = __DATA__;

// A restrained newsprint-infographic palette: ink-compatible, desaturated hues. Each
// dimension you can color/group by keeps its own fixed map plus a fallback palette for any
// category it doesn't have a color for yet.
const FALLBACK_COLORS = ["#a3161a", "#1c5cab", "#3d6b35", "#a66a1e", "#6b3fa0"];
const DIMENSIONS = {
  provider: {
    label: "Provider",
    keyOf: m => m.provider,
    colors: {
      openai: "#a3161a", anthropic: "#1c5cab", google: "#3d6b35", spacexai: "#a66a1e",
      deepseek: "#6b3fa0", zai: "#2f6f6b", alibaba: "#7a4a2b", moonshotai: "#ab4967",
      mistral: "#5c6b8a", meta: "#6e6e5a",
    },
  },
  license: {
    label: "License",
    keyOf: m => m.license,
    colors: { open: "#2f6f6b", closed: "#a3161a" },
  },
  country: {
    label: "Country",
    keyOf: m => m.country,
    colors: { USA: "#1c5cab", China: "#a3161a", France: "#a66a1e" },
  },
};
let currentDim = "provider";

function categoriesFor(dim) { return [...new Set(DATA.models.map(DIMENSIONS[dim].keyOf))].sort(); }

const activeCategories = {};
for (const dim in DIMENSIONS) activeCategories[dim] = new Set(categoriesFor(dim));

let fallbackIdx = 0;
function colorFor(dim, key) {
  const colors = DIMENSIONS[dim].colors;
  if (!colors[key]) colors[key] = FALLBACK_COLORS[fallbackIdx++ % FALLBACK_COLORS.length];
  return colors[key];
}

function shortName(m) { return m.split("/")[1] || m; }
function fmtPct(x) { return (x * 100).toFixed(0) + "%"; }
function visibleModels() {
  const active = activeCategories[currentDim], keyOf = DIMENSIONS[currentDim].keyOf;
  return DATA.models.filter(m => active.has(keyOf(m)));
}

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

// ---- dimension switch + legend ----
(function renderLegend() {
  const el = document.getElementById("provider-legend");
  function draw() {
    const categories = categoriesFor(currentDim);
    const active = activeCategories[currentDim];
    const allOn = active.size === categories.length;

    let html = '<span class="dim-switch">';
    for (const dim in DIMENSIONS) {
      html += `<button data-dim="${dim}" class="${dim === currentDim ? 'active' : ''}">${DIMENSIONS[dim].label}</button>`;
    }
    html += '</span>';
    html += `<span class="legend-title">${DIMENSIONS[currentDim].label}</span>`;
    html += `<span class="chip chip-all" id="chip-all">${allOn ? "Clear all" : "Select all"}</span>`;
    categories.forEach(key => {
      const c = colorFor(currentDim, key);
      html += `<span class="chip ${active.has(key) ? 'active' : 'inactive'}" data-key="${key}" style="--chip-color:${c}"><span class="dot" style="background:${c}"></span>${key}</span>`;
    });
    el.innerHTML = html;

    el.querySelectorAll(".dim-switch button").forEach(btn => {
      btn.addEventListener("click", () => {
        currentDim = btn.dataset.dim;
        draw();
        rerenderAll();
      });
    });
    el.querySelectorAll(".chip[data-key]").forEach(chip => {
      chip.addEventListener("click", () => {
        const key = chip.dataset.key;
        if (active.has(key)) active.delete(key); else active.add(key);
        draw();
        rerenderAll();
      });
    });
    el.querySelector("#chip-all").addEventListener("click", () => {
      if (active.size === categories.length) { active.clear(); }
      else { categories.forEach(key => active.add(key)); }
      draw();
      rerenderAll();
    });
  }
  draw();
})();

// ---- stat tiles ----
// sum(spotted)/sum(judged), pooled rather than a mean of per-model rates, so models with
// more graded answers count proportionally more. Null if nothing was judged.
function pooledRate(models) {
  const judged = models.reduce((s, m) => s + m.judged, 0);
  if (judged === 0) return null;
  const spotted = models.reduce((s, m) => s + m.spotted, 0);
  return spotted / judged;
}

// Buckets `models` by `keyOf(m)` and returns each bucket's pooled rate and color, best
// (highest detection rate) first.
function groupRates(models, dim) {
  const keyOf = DIMENSIONS[dim].keyOf;
  const buckets = new Map();
  models.forEach(m => {
    const key = keyOf(m);
    (buckets.get(key) || buckets.set(key, []).get(key)).push(m);
  });
  return [...buckets.entries()]
    .map(([key, bucket]) => ({ key, rate: pooledRate(bucket), color: colorFor(dim, key) }))
    .filter(g => g.rate !== null)
    .sort((a, b) => b.rate - a.rate);
}

(function renderStats() {
  const el = document.getElementById("stat-row");
  function draw() {
    const vis = visibleModels();
    const overall = pooledRate(vis);

    let html = `
      <div class="stat-tile">
        <div class="label">Overall detection rate</div>
        <div class="value">${overall === null ? "-" : fmtPct(overall)}</div>
      </div>`;

    [["Open vs. closed-source", "license"], ["By country", "country"]].forEach(([label, dim]) => {
      const groups = groupRates(vis, dim);
      html += `<div class="stat-tile grouped"><div class="label">${label}</div><div class="group-row">`;
      html += groups.length === 0
        ? '<div class="group-box"><div class="val">-</div></div>'
        : groups.map(g => `
          <div class="group-box" style="--box-color:${g.color}">
            <div class="key">${g.key}</div>
            <div class="val">${fmtPct(g.rate)}</div>
          </div>`).join("");
      html += `</div></div>`;
    });

    el.innerHTML = html;
  }
  renderers.push(draw);
  draw();
})();

// ---- bar chart ----
(function renderBars() {
  const el = document.getElementById("bar-chart");
  function draw() {
    const rows = [...DATA.models].sort((a, b) => b.performance - a.performance);
    const keyOf = DIMENSIONS[currentDim].keyOf, active = activeCategories[currentDim];
    el.innerHTML = rows.map(m => {
      const c = colorFor(currentDim, keyOf(m));
      const hidden = active.has(keyOf(m)) ? "" : "hidden";
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
    if (pts.length === 0) { el.innerHTML = `<p style="color:var(--text-muted); font-size:0.85rem;">No ${DIMENSIONS[currentDim].label.toLowerCase()} selected.</p>`; return; }

    // A log-scale axis has no position for 0 (or missing data): plotting it would
    // clamp to the left edge, indistinguishable from the smallest real value. Those
    // models are left off the plot and named below it instead, like the static
    // report does for 0%-performance dots.
    const plottable = pts.filter(m => m[xKey] > 0);
    const zero = pts.filter(m => !(m[xKey] > 0));
    if (plottable.length === 0) {
      el.innerHTML = `<p style="color:var(--text-muted); font-size:0.85rem;">No selected model has ${xLabel.replace(/\s*\(.*\)/, "")} data.</p>`;
      return;
    }

    const xsPos = plottable.map(m => m[xKey]);
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

    const frontier = computeFrontier(plottable, xKey);
    if (frontier.length > 1) {
      const path = frontier.map((p, i) => `${i === 0 ? "M" : "L"}${sx(p[xKey])},${sy(p.performance)}`).join(" ");
      inner += `<path class="frontier-line" d="${path}"/>`;
    }

    svg.innerHTML = inner;

    const frontierSet = new Set(frontier.map(p => p.model));

    // Layout: a label defaults to sitting right next to its dot, but a wide
    // label (a long model name) can reach past a neighboring dot even when
    // that dot isn't especially close in X. So each label's box (estimated
    // from its character count; SVG has no cheap text-measuring without an
    // extra render pass) is checked against every dot and every label placed
    // so far, at increasing vertical offsets, until one is clear; a leader
    // line is only drawn once a label has actually been pushed off its dot.
    const LABEL_H = 12, CHAR_W = 5.7, DOT_R = 8;
    function overlapBoxes(a, b) { return a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3]; }
    function labelBox(cx, y, label, side) {
      const w = label.length * CHAR_W + 6;
      const x0 = side === "left" ? cx - 9 - w : cx + 9;
      return [x0, y - LABEL_H / 2, x0 + w, y + LABEL_H / 2];
    }

    const items = plottable.map(m => ({
      m, cx: sx(m[xKey]), cy: sy(m.performance),
      label: shortName(m.model),
      side: sx(m[xKey]) > W - PAD_R - 90 ? "left" : "right",
    })).sort((a, b) => a.cx - b.cx || a.cy - b.cy);

    const dotBoxes = items.map(it => [it.cx - DOT_R, it.cy - DOT_R, it.cx + DOT_R, it.cy + DOT_R]);
    const placedBoxes = [];
    items.forEach((it, index) => {
      const otherDots = dotBoxes.filter((_, j) => j !== index);
      let chosen = null;
      for (let step = 0; step < 16 && !chosen; step++) {
        const dy = step === 0 ? 0 : (step % 2 ? 1 : -1) * Math.ceil(step / 2) * (LABEL_H + 2);
        const y = Math.max(PAD_T + LABEL_H / 2, Math.min(H - PAD_B - LABEL_H / 2, it.cy + dy));
        const box = labelBox(it.cx, y, it.label, it.side);
        if (!placedBoxes.some(p => overlapBoxes(box, p)) && !otherDots.some(d => overlapBoxes(box, d))) {
          chosen = { box, y };
        }
      }
      if (!chosen) chosen = { box: labelBox(it.cx, it.cy, it.label, it.side), y: it.cy };  // crowded: accept the overlap
      it.yLabel = chosen.y;
      placedBoxes.push(chosen.box);
    });

    items.forEach(it => {
      const { m, cx, cy } = it;
      const c = colorFor(currentDim, DIMENSIONS[currentDim].keyOf(m));
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

      const nearRight = it.side === "left";
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

    if (zero.length) {
      const note = document.createElement("p");
      note.style.cssText = "color:var(--text-muted); font-size:0.78rem; margin-top:8px;";
      note.textContent = `No ${xLabel.replace(/\s*\(.*\)/, "")} data: ${zero.map(m => shortName(m.model)).join(", ")}`;
      el.appendChild(note);
    }
  }
  renderers.push(draw);
  draw();
}

scatterChart("scatter-cost", "cost_per_pass_usd", "cost per pass ($, log scale)", v => v < 0.01 ? "$" + v.toFixed(3) : "$" + v.toFixed(2));
scatterChart("scatter-tokens", "avg_output_tokens", "avg output tokens (log scale)", v => v.toFixed(0));
scatterChart("scatter-latency", "avg_latency_seconds", "avg latency (s, log scale)", v => v.toFixed(0) + "s");

// ---- tokens/latency toggle (hidden by default) ----
(function () {
  const btn = document.getElementById("toggle-extra-scatters");
  const panel = document.getElementById("extra-scatters");
  btn.addEventListener("click", () => {
    const show = panel.hidden;
    panel.hidden = !show;
    btn.textContent = show ? "Hide tokens & latency charts" : "Show tokens & latency charts";
    if (show) rerenderAll();
  });
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
