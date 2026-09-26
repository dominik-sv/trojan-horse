# Field Notes on the Trojan Horse Benchmark

## Concept

Instead of a leaderboard, this is an illustrated field journal — the kind of notebook a naturalist keeps after a day of observing specimens in the wild. Twenty LLMs become twenty "specimens" sent out to encounter questions with a false premise hidden inside, and the page catalogues what each one did when it found the trap: did it notice, or did it just answer and walk on?

## Why these choices

- **Warm paper background + hand-torn section markers** instead of a dark corporate dashboard shell — the goal is "curious and trustworthy," not "cold and clinical." A subtle horizontal rule pattern and grain give the sense of lined notebook paper without ever getting in the way of the numbers.
- **Caveat (handwriting-style) for headers and annotations, Source Serif 4 for body/data, Nunito Sans for UI chrome** — the handwriting voice stays confined to narration and never touches the actual figures, so nothing important becomes hard to read.
- **Muted natural palette (sage, ochre, terracotta, dusty blue, olive, slate)** mapped one color per provider, used consistently across the ranked list, the scatter plot, and the ledger table, so a reader learns "terracotta = Anthropic" once and can use it everywhere.
- **"Specimen cards" with a one-line field note** for each model (e.g. "Never once let a false premise past" for gpt-6-astra, "This one rarely pushes back" for the models that scored 0%) — this is the most literal expression of the naturalist framing: models are observed and described, not just scored.
- **A sortable ranked list (with expandable detail cards), a log-scaled scatter plot (rate vs. cost/tokens/latency, switchable), and a fully sortable raw ledger table** together satisfy the content-parity requirement three different ways, so a reader who wants the story, the trend, or the raw numbers all get what they came for.
- **Light/dark toggle** respects `prefers-color-scheme` by default but is overridable, since a paper aesthetic should still be comfortable at night.

Everything is inline in a single `index.html` with the benchmark data embedded as a JS array — no build step, no fetch, opens straight from `file://`.
