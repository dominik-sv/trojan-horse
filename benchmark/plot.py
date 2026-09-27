"""Charts for the benchmark report.

Each provider (openai, anthropic, google, ...) gets one hue, and the models of
a provider are shades of it: the darkest shade is the provider's best model in
that chart, the lightest its weakest. Every chart here uses that same coloring.
"""

import math
import textwrap
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")  # write files only; no window needed
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

# One base hue per provider, close to each company's own color. The three were
# checked together for color-blind separation (worst pair: delta E 13 in OKLab x100).
PROVIDER_COLORS = {"openai": "#0e9e8f", "anthropic": "#e0662f", "google": "#3a78d8"}
# Providers without a color of their own take these, in order of appearance.
EXTRA_COLORS = ["#7a4fc9", "#c94f8f", "#6b6b66", "#a08a1e"]
PROVIDER_NAMES = {"openai": "OpenAI", "anthropic": "Anthropic", "google": "Google"}

DARKEN = 0.38  # how far toward black the best model's shade goes
LIGHTEN = 0.40  # how far toward white the weakest model's shade goes (keeps 2:1 against the surface)

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e4e3df"

Layout = list[tuple[str, list[tuple[str, str]]]]  # [(provider, [(model, color), ...]), ...], best model first


def plot_detection_rates(
    counts: dict[tuple[str, str], list[int]], models: list[str], path: Path, title_suffix: str = ""
) -> None:
    """Draw one group of bars per prompt, one bar per model, saved to `path`.

    `counts` maps (prompt_id, model) to [judged, spotted]. A model with no
    judged runs on a prompt simply has no bar there.
    """
    prompts = sorted({prompt_id for prompt_id, _ in counts})
    if not prompts:
        return

    def overall_rate(model: str) -> float:
        judged = sum(j for (_, m), (j, _) in counts.items() if m == model)
        spotted = sum(s for (_, m), (_, s) in counts.items() if m == model)
        return spotted / judged if judged else -1.0

    present = [model for model in models if any(m == model for _, m in counts)]
    layout = _provider_layout({model: overall_rate(model) for model in present}, present)
    ordered = [(model, color) for _, members in layout for model, color in members]

    group_width = 0.8
    bar_width = group_width / len(ordered)
    fig, ax = plt.subplots(figsize=(max(7.5, 1.7 * len(prompts) + 0.45 * len(ordered)), 5.6), facecolor=SURFACE)
    _style_axes(ax)

    for position, (model, color) in enumerate(ordered):
        for prompt_index, prompt_id in enumerate(prompts):
            if (prompt_id, model) not in counts:
                continue
            judged, spotted = counts[(prompt_id, model)]
            rate = spotted / judged
            x = prompt_index - group_width / 2 + (position + 0.5) * bar_width
            # The surface-colored edge leaves a thin gap between neighboring bars.
            ax.bar(x, rate, bar_width, color=color, edgecolor=SURFACE, linewidth=1.5)
            ax.text(x, rate + 0.015, f"{rate:.0%}", ha="center", va="bottom", rotation=90, fontsize=7.5, color=INK_SECONDARY)

    ax.set_xticks(range(len(prompts)))
    ax.set_xticklabels([textwrap.fill(prompt_id.replace("_", " "), 16) for prompt_id in prompts], color=INK)
    _percent_axis(ax, "Runs that spotted the false premise", top=1.16)
    ax.set_title("Detection rate by model and prompt" + title_suffix, color=INK, loc="left", fontsize=13, pad=14)

    _draw_legend(ax, layout, anchor_y=-0.16)
    fig.text(
        0.5, -0.02, "Darker shade = higher detection rate within the provider, across the prompts shown",
        ha="center", va="top", fontsize=8.5, color=INK_SECONDARY,
    )
    _save(fig, path)


def plot_performance_bars(performance: dict[str, float], models: list[str], path: Path, title_suffix: str = "") -> None:
    """One bar per model, best first: the share of its judged answers that spotted the false premise."""
    present = [model for model in models if model in performance]
    if not present:
        return
    layout = _provider_layout(performance, present)
    color_of = {model: color for _, members in layout for model, color in members}
    ordered = sorted(present, key=lambda model: -performance[model])  # stable: ties keep the config order

    fig, ax = plt.subplots(figsize=(max(7.5, 0.85 * len(ordered) + 2.5), 5.6), facecolor=SURFACE)
    _style_axes(ax)
    for position, model in enumerate(ordered):
        ax.bar(position, performance[model], 0.7, color=color_of[model], edgecolor=SURFACE, linewidth=1.5)
        ax.text(position, performance[model] + 0.015, f"{performance[model]:.0%}", ha="center", va="bottom", fontsize=9, color=INK_SECONDARY)
    ax.set_xticks(range(len(ordered)))
    ax.set_xticklabels([model.split("/", 1)[-1] for model in ordered], rotation=35, ha="right", color=INK)
    _percent_axis(ax, "Performance", top=1.1)
    ax.set_title("Overall performance by model" + title_suffix, color=INK, loc="left", fontsize=13, pad=14)

    _draw_legend(ax, layout, anchor_y=-0.34)
    fig.text(
        0.5, 0.09,
        "Performance = answers that spotted the false premise ÷ judged answers. "
        "Darker shade = better within the provider.",
        ha="center", va="top", fontsize=8.5, color=INK_SECONDARY,
    )
    _save(fig, path)


def plot_scatter(
    points: dict[str, tuple[float, float]],
    performance: dict[str, float],
    models: list[str],
    path: Path,
    *,
    title: str,
    x_label: str,
    x_format: Callable[[float], str],
    footnote: str,
    log_x: bool = False,
    title_suffix: str = "",
) -> None:
    """A scatter of performance (y) against `points[model] = (x, performance)` (x is tokens or dollars)."""
    present = [model for model in models if model in points and model in performance]
    if not present:
        return
    layout = _provider_layout(performance, present)
    color_of = {model: color for _, members in layout for model, color in members}

    fig, ax = plt.subplots(figsize=(9.0, 6.2), facecolor=SURFACE)
    _style_axes(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    xs = [points[model][0] for model in present]
    for model in present:
        x, y = points[model]
        ax.scatter([x], [y], s=110, color=color_of[model], edgecolor=SURFACE, linewidth=1.5, zorder=3)

    # Models with 0% performance all sit on the same horizontal line, where full name
    # labels for more than a couple of them would overlap into mush. They get a small
    # numbered tag instead, resolved against a footnote list below the chart.
    zero = sorted((model for model in present if performance[model] == 0), key=lambda model: points[model][0])
    nonzero = [model for model in present if model not in zero]
    tag_of = {model: _zero_tag(index) for index, model in enumerate(zero)}

    if log_x:
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
        ax.xaxis.set_minor_formatter(NullFormatter())
        low, high = min(xs), max(xs)
        ax.set_xlim(low / 1.6, high * 1.6)
    else:
        ax.set_xlim(0, max(xs) * 1.18)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: x_format(value)))
    ax.set_xlabel(x_label, color=INK_SECONDARY)
    ax.tick_params(axis="x", colors=INK_SECONDARY)
    _percent_axis(ax, "Performance", top=1.08)
    ax.set_ylim(-0.04, 1.08)  # room below 0% so a point at 0% is not cut in half
    ax.set_title(title + title_suffix, color=INK, loc="left", fontsize=13, pad=14)

    fig.tight_layout()
    # A few nonzero dots can still sit close enough that neither can get an individual
    # label spot; those get pulled into a stacked, leader-lined list instead.
    clusters = _cluster_points(ax, nonzero, points)
    singles, cluster_taken = _label_clusters(fig, ax, clusters, points, color_of)
    _label_points(
        fig, ax, [(model.split("/", 1)[-1], *points[model], color_of[model]) for model in singles],
        markers=[points[model] for model in nonzero], taken=cluster_taken,
    )
    _label_points(fig, ax, [(tag_of[model], *points[model], color_of[model]) for model in zero])
    _draw_legend(ax, layout, anchor_y=-0.17)
    fig.text(0.5, -0.03, footnote, ha="center", va="top", fontsize=8.5, color=INK_SECONDARY)
    if zero:
        zero_list = "  ".join(f"{tag_of[model]} {model.split('/', 1)[-1]}" for model in zero)
        fig.text(
            0.5, -0.065, textwrap.fill(f"Scored 0%: {zero_list}", 110),
            ha="center", va="top", fontsize=8.5, color=INK_SECONDARY,
        )
    _save(fig, path, tighten=False)


# --- shared helpers --------------------------------------------------------------


def _style_axes(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="both", length=0)


def _percent_axis(ax, label: str, top: float) -> None:
    ax.set_ylim(0, top)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"], color=INK_SECONDARY)
    ax.set_ylabel(label, color=INK_SECONDARY)


def _draw_legend(ax, layout: Layout, anchor_y: float) -> None:
    """One legend column per provider: its name, then its models best (darkest) first."""
    height = max(len(members) for _, members in layout) + 1
    handles, labels, header_rows = [], [], []
    for provider, members in layout:
        header_rows.append(len(handles))
        handles.append(Patch(alpha=0))
        labels.append(PROVIDER_NAMES.get(provider, provider.title()))
        for model, color in members:
            handles.append(Patch(facecolor=color, edgecolor=SURFACE))
            labels.append(model.split("/", 1)[-1])
        for _ in range(height - 1 - len(members)):  # pad so every column has the same height
            handles.append(Patch(alpha=0))
            labels.append("")
    legend = ax.legend(
        handles, labels, loc="upper center", bbox_to_anchor=(0.5, anchor_y), ncol=len(layout), frameon=False,
        columnspacing=2.2, handlelength=1.4,
    )
    for index, text in enumerate(legend.get_texts()):
        text.set_color(INK)
        if index in header_rows:
            text.set_fontweight("bold")


def _overlaps(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _label_points(
    fig, ax, labeled: list[tuple[str, float, float, str]],
    markers: list[tuple[float, float]] | None = None,
    taken: list[tuple[float, float, float, float]] | None = None,
) -> None:
    """Write each point's model name next to it, trying spots around the point until one is clear.

    `markers` are the data-coordinate dots to avoid (defaults to the labeled points
    themselves); pass the full set when `labeled` is only some of the dots on the chart.
    `taken` seeds already-placed label boxes to steer clear of, e.g. from `_label_clusters`.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axes_box = ax.get_window_extent(renderer)
    if markers is None:
        markers = [(x, y) for _, x, y, _ in labeled]
    marker_boxes = []
    for x, y in markers:
        px, py = ax.transData.transform((x, y))
        marker_boxes.append((px - 9, py - 9, px + 9, py + 9))

    spots = [  # (dx, dy in points, horizontal alignment, vertical alignment)
        (9, 0, "left", "center"), (-9, 0, "right", "center"), (0, 10, "center", "bottom"), (0, -10, "center", "top"),
        (9, 9, "left", "bottom"), (9, -9, "left", "top"), (-9, 9, "right", "bottom"), (-9, -9, "right", "top"),
    ]
    taken = list(taken) if taken else []
    for name, x, y, _ in sorted(labeled, key=lambda item: (item[1], item[2])):
        own_px, own_py = ax.transData.transform((x, y))
        best = None
        for dx, dy, ha, va in spots:
            text = ax.annotate(
                name, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, fontsize=8.5, color=INK, zorder=4
            )
            box = text.get_window_extent(renderer)
            rect = (box.x0, box.y0, box.x1, box.y1)
            clear = (
                axes_box.x0 <= rect[0] and rect[2] <= axes_box.x1 and axes_box.y0 <= rect[1] and rect[3] <= axes_box.y1
                and not any(_overlaps(rect, other) for other in taken)
                and not any(
                    _overlaps(rect, m) for m in marker_boxes if not (m[0] < own_px < m[2] and m[1] < own_py < m[3])
                )
            )
            if clear:
                best = rect
                break
            text.remove()
        if best is None:  # crowded: fall back to the first spot even if it touches something
            dx, dy, ha, va = spots[0]
            text = ax.annotate(name, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, fontsize=8.5, color=INK, zorder=4)
            box = text.get_window_extent(renderer)
            best = (box.x0, box.y0, box.x1, box.y1)
        taken.append(best)


CLUSTER_RADIUS = 26  # px: dots closer than this can't both get an individual label spot


def _cluster_points(ax, models: list[str], points: dict[str, tuple[float, float]]) -> list[list[str]]:
    """Group `models` whose dots sit within `CLUSTER_RADIUS` pixels of each other, transitively."""
    positions = {model: ax.transData.transform(points[model]) for model in models}
    remaining = list(models)
    clusters: list[list[str]] = []
    while remaining:
        cluster = [remaining.pop()]
        grown = True
        while grown:
            grown = False
            for model in remaining[:]:
                if any(math.hypot(*(positions[model] - positions[member])) < CLUSTER_RADIUS for member in cluster):
                    cluster.append(model)
                    remaining.remove(model)
                    grown = True
        clusters.append(cluster)
    return clusters


def _label_clusters(
    fig, ax, clusters: list[list[str]], points: dict[str, tuple[float, float]], color_of: dict[str, str]
) -> tuple[list[str], list[tuple[float, float, float, float]]]:
    """Place a stacked, leader-lined label next to each cluster of 2+ dots too close to label individually.

    Returns the models left over (clusters of size 1, unaffected) to be labeled the normal
    way, plus the label boxes already placed here, so `_label_points` can steer clear of them.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axes_box = ax.get_window_extent(renderer)
    all_marker_boxes = {}
    for group in clusters:
        for model in group:
            px, py = ax.transData.transform(points[model])
            all_marker_boxes[model] = (px - 9, py - 9, px + 9, py + 9)

    singles: list[str] = []
    taken: list[tuple[float, float, float, float]] = []
    for cluster in clusters:
        if len(cluster) == 1:
            singles.append(cluster[0])
            continue
        ordered = sorted(cluster, key=lambda model: -ax.transData.transform(points[model])[1])  # top to bottom
        names = [model.split("/", 1)[-1] for model in ordered]
        other_marker_boxes = [box for model, box in all_marker_boxes.items() if model not in cluster]
        xs_px, ys_px = zip(*(ax.transData.transform(points[model]) for model in ordered))
        anchor = ax.transData.inverted().transform((sum(xs_px) / len(xs_px), sum(ys_px) / len(ys_px)))

        best = None
        for dx, ha in [(14, "left"), (-14, "right"), (26, "left"), (-26, "right")]:
            text = ax.annotate(
                "\n".join(names), anchor, xytext=(dx, 0), textcoords="offset points",
                ha=ha, va="center", fontsize=8.5, color=INK, zorder=4, linespacing=1.7,
            )
            box = text.get_window_extent(renderer)
            rect = (box.x0, box.y0, box.x1, box.y1)
            clear = (
                axes_box.x0 <= rect[0] and rect[2] <= axes_box.x1 and axes_box.y0 <= rect[1] and rect[3] <= axes_box.y1
                and not any(_overlaps(rect, other) for other in taken)
                and not any(_overlaps(rect, m) for m in other_marker_boxes)
            )
            if clear:
                best = (rect, ha)
                break
            text.remove()
        if best is None:  # crowded: fall back to the first spot even if it touches something
            dx, ha = 14, "left"
            text = ax.annotate(
                "\n".join(names), anchor, xytext=(dx, 0), textcoords="offset points",
                ha=ha, va="center", fontsize=8.5, color=INK, zorder=4, linespacing=1.7,
            )
            box = text.get_window_extent(renderer)
            best = ((box.x0, box.y0, box.x1, box.y1), ha)

        rect, ha = best
        taken.append(rect)
        line_height = (rect[3] - rect[1]) / len(names)
        edge_x = rect[0] if ha == "left" else rect[2]
        for index, model in enumerate(ordered):
            line_y = rect[3] - (index + 0.5) * line_height
            edge_data = ax.transData.inverted().transform((edge_x, line_y))
            ax.plot(
                [points[model][0], edge_data[0]], [points[model][1], edge_data[1]],
                color=INK_SECONDARY, linewidth=0.8, zorder=2, solid_capstyle="round",
            )
    return singles, taken


def _zero_tag(index: int) -> str:
    """A short tag for the index-th (0-based) 0%-performance model: circled digits, then plain numbers."""
    circled = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
    return circled[index] if index < len(circled) else f"({index + 1})"


def _save(fig, path: Path, tighten: bool = True) -> None:
    if tighten:
        fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def _provider_layout(rates: dict[str, float], models: list[str]) -> Layout:
    """Group `models` by provider (in order of first appearance) and shade each group by rank.

    `rates[model]` is the number that decides "best". Returns
    [(provider, [(model, color), ...]), ...], each provider's models ordered best
    first, so the first entry gets the darkest shade.
    """
    providers: dict[str, list[str]] = {}
    for model in models:
        providers.setdefault(model.split("/", 1)[0], []).append(model)

    extras = iter(EXTRA_COLORS)
    layout: Layout = []
    for provider, members in providers.items():
        base = PROVIDER_COLORS.get(provider) or next(extras, "#6b6b66")
        ranked = sorted(members, key=lambda model: -rates.get(model, -1.0))  # stable: ties keep the config order
        layout.append((provider, list(zip(ranked, _shades(base, len(ranked))))))
    return layout


def _shades(base: str, count: int) -> list[str]:
    """`count` shades of `base`, from a darkened one down to a lightened one."""
    if count == 1:
        return [base]
    dark = _mix(base, "#000000", DARKEN)
    light = _mix(base, "#ffffff", LIGHTEN)
    return [_mix(dark, light, step / (count - 1)) for step in range(count)]


def _mix(a: str, b: str, amount: float) -> str:
    """Blend hex color `a` toward hex color `b` by `amount` (0 = a, 1 = b)."""
    channels = [
        round(int(a[i : i + 2], 16) * (1 - amount) + int(b[i : i + 2], 16) * amount) for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{value:02x}" for value in channels)
