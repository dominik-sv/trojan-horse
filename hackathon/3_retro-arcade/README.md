# Trojan Horse Benchmark — Retro-Futurist Arcade Edition

## Concept
The benchmark is fundamentally a competition — 20 LLMs get thrown the same trap and either catch it or don't. That's an arcade high-score table wearing a lab coat. So this redesign leans all the way into an '80s arcade cabinet / synthwave album cover: a chrome-glowing title over a scanning sun and receding neon grid horizon, an "INSERT COIN" call-to-action, rank badges (gold/silver/bronze) on a sortable LEADERBOARD, "energy cost" standing in for dollars spent, and a CRT scanline overlay across the whole page to sell the cabinet feel without sacrificing readability.

## Design choices
- **Palette**: deep navy-to-violet background with magenta/cyan/purple/yellow neon accents — high contrast against dark so text and bars stay legible even under all the glow.
- **Typography**: "Press Start 2P" for chunky pixel headers (used sparingly, only for section titles and the hero, since it's hard to read in long runs), "Orbitron" for chrome-style display numbers, and "Share Tech Mono" for all body/data text so the actual numbers stay scannable.
- **Leaderboard**: sortable by score / cost / latency / tokens / provider — click any row to expand a stat-sheet panel with the full metric set, satisfying "browsable full data" without a dense literal table dominating the page.
- **Score vs Energy scatter**: detection rate (y) against cost per pass (x, log scale, per the standard convention for wide-range cost data) with bubble size mapped to output tokens, so cost/tokens/latency-vs-detection relationships are visible in one glowing chart. Latency is available per-model in the leaderboard and detail panel.
- **Provider Factions**: a simple average-detection-rate-by-manufacturer bar section, framed as competing "factions," since the persona treats companies like arcade teams.
- **Motion**: pure CSS — pulsing sun glow, scrolling grid horizon, blinking "insert coin," hover-lift on stat coins and leaderboard rows — all decorative, none blocking readability or requiring a build step.

Single self-contained `index.html`, data embedded inline, opens directly via `file://`.
