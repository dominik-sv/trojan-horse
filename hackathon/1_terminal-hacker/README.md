# Trojan Horse Benchmark — Terminal Hacker edition

A single-file `index.html` that recasts the benchmark as an **intrusion-detection report** running on a green-phosphor CRT terminal — because the whole premise of this project (a trojan smuggled inside an innocent-looking question) already *is* a security-report story, so I leaned all the way in instead of just skinning a normal dashboard in a monospace font.

## Concept

- **Boot sequence**: on load, a BIOS-style typed log ("mounting report/models.csv", "running 400 graded intrusion attempts... DONE") stages the reveal and states the headline number before the dashboard even appears. Click/keypress/`[SKIP BOOT]` bypasses it instantly for repeat viewers.
- **Framing**: models are "targets", detection is "the payload was caught", 0%-detection models are labeled "fully compromised", ambiguous ones "partial". This isn't just cute copy — it makes the actual finding (most frontier models get owned by a false premise) land harder than a neutral "detection rate" label would.
- **ASCII/box-drawing everywhere**: a hand-built ASCII wordmark, unicode block-bar meters (`████░░░░`) inline in the table instead of a separate bar-chart column, dashed rules as section dividers, bracketed `[ BUTTON ]` controls.
- **CRT physicality**: scanline overlay, vignette, a subtle flicker keyframe, blinking block cursors, and a live UTC clock — all meant to sell "you are looking at a live terminal session," not just a themed page.
- **Correlation scan**: a canvas-drawn log-scale scatter (detection % vs. cost/tokens/latency, switchable) rendered manually in the terminal palette rather than a bolted-on chart library, with hover tooltips and click-to-select syncing with the table.
- **Full interactivity, kept legible**: sortable/filterable roster table (search, provider filter, click-to-sort columns), a click-through "trace" detail panel per model, and a verdict badge (CAUGHT / PARTIAL / EVADED) so the signal is scannable even before you read a single number.

## Why these choices

The persona is "someone who lives in a terminal at 3am," so the design had to *function* like a real tool a security engineer would actually use during a review — not just look like one in a screenshot. That's why sorting, filtering, hover tooltips, and a real (if retro-styled) scatterplot all made the cut instead of just static ASCII tables: atmosphere without usability would betray the persona as much as skipping the theme entirely.

## Files

- `index.html` — self-contained, no build step, no network calls, opens directly via `file://`. Data for all 20 models is embedded inline as a JS array.
