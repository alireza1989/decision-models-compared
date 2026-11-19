"""Figures for the post, from results/summary.json and the saved raw results only.

    python -m dmc.figures      # writes figures/*.png
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from dmc.common import RESULTS, ROOT, top_prob  # noqa: E402
from dmc.evaluate import HAIKU, SONNET, rows_of, subset  # noqa: E402

OUT = ROOT / "figures"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SHORT = {
    "typesafe/jev-1.14": "Jev 1.14", "typesafe/jev-1.13": "Jev 1.13", "google/gemini-decision-1": "Gemini Decision 1",
    "openai/gpt-6-luna-decisions": "OpenAI Decisions", "microsoft/microsoft-decision-1.1": "Microsoft Decision 1.1",
    "perplexity/pplx-decider-v1.2": "Perplexity Decider v1.2", "nace-ai/drex-max": "Drex Max",
    "liquid/d1.2-ultra": "Liquid d1.2-ultra", "togethercomputer/tev1-4b-experimental": "Tev1-4B",
    "cloudflare/clef": "Cloudflare Clef", "upstage/solar-decide": "Solar Decide", "heygen/heygen-decision-1": "HeyGen Decision 1",
    HAIKU: "Claude Haiku 5.5", SONNET: "Claude Sonnet 5.5",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10.5, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "xtick.color": INK2, "ytick.color": INK,
    "xtick.labelsize": 9.5, "ytick.labelsize": 10, "axes.titlesize": 11.5, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.titlepad": 10, "legend.frameon": False, "legend.fontsize": 9.5,
    "figure.dpi": 100, "savefig.dpi": 200, "savefig.bbox": "tight", "savefig.pad_inches": 0.15,
})


def style(ax, grid_axis="x"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{name}.png", facecolor="white")
    plt.close(fig)
    print("wrote", f"figures/{name}.png")


def fig_threshold_transfer(s):
    """Wrong automatic actions at each model's validation threshold: validation, CLINC test, fresh set."""
    th = s["routing"]["thresholds"]
    order = sorted(th["scoped_v2"], key=lambda m: th["scoped_v2"][m]["fresh"]["wrong_auto"])
    fig, axes = plt.subplots(2, 1, figsize=(6.6, 8.4), sharex=True)
    for ax, cond, title in ((axes[0], "base", "No scope sentence"), (axes[1], "scoped_v2", "With the tighter scope sentence")):
        style(ax)
        for i, m in enumerate(order):
            e = th[cond][m]
            vals = [100 * e["validation"]["wrong_auto"], 100 * e["test_all_traffic"]["wrong_auto"], 100 * e["fresh"]["wrong_auto"]]
            ax.plot([min(vals), max(vals)], [i, i], color=GRID, linewidth=2, zorder=1)
            ax.scatter(vals[0], i, s=46, facecolor="white", edgecolor=MUTED, linewidth=1.4, zorder=3)
            ax.scatter(vals[1], i, s=46, color=BLUE, edgecolor="white", linewidth=1.2, zorder=4)
            ax.scatter(vals[2], i, s=46, color=ORANGE, edgecolor="white", linewidth=1.2, zorder=5)
        ax.axvline(2, color=INK, linewidth=1, linestyle=(0, (3, 2)), zorder=2)
        ax.set_yticks(range(len(order)), [SHORT[m] for m in order])
        ax.invert_yaxis()
        ax.set_title(title)
    axes[1].set_xlabel("Wrong automatic actions (% of the actions the gate automated)")
    axes[1].set_xlim(0, 21)
    handles = [Line2D([], [], marker="o", linestyle="", markerfacecolor="white", markeredgecolor=MUTED, markersize=7, label="Validation (threshold picked here)"),
               Line2D([], [], marker="o", linestyle="", color=BLUE, markersize=7, label="CLINC150 test traffic"),
               Line2D([], [], marker="o", linestyle="", color=ORANGE, markersize=7, label="Fresh set"),
               Line2D([], [], color=INK, linewidth=1, linestyle=(0, (3, 2)), label="2%, the promise")]
    fig.legend(handles=handles, loc="upper left", ncol=2, bbox_to_anchor=(0.0, 1.05), handletextpad=0.4, columnspacing=1.4)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    save(fig, "fig1-threshold-transfer")


def repel(ys, gap):
    """Nudge label positions apart so that no two are closer than gap, keeping their order."""
    idx = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for _ in range(200):
        moved = False
        for a, b in zip(idx, idx[1:]):
            if out[b] - out[a] < gap:
                d = (gap - (out[b] - out[a])) / 2
                out[a] -= d
                out[b] += d
                moved = True
        if not moved:
            break
    return out


def fig_accuracy_brier(s):
    """Fresh set, tighter scope sentence: accuracy against Brier score, coloured by tie group."""
    fr = s["routing"]["fresh"]["scoped_v2"]
    groups = s["routing"]["tie_groups"]["scoped_v2"]["fresh"]
    colour = {m: c for g, c in zip(groups, (BLUE, ORANGE, AQUA)) for m in g}
    fig, ax = plt.subplots(figsize=(6.6, 5.2))
    style(ax, "both")
    models = list(colour) + ([SONNET] if SONNET in fr else [])
    xs = [100 * fr[m]["all"]["accuracy"] for m in models]
    ys = [fr[m]["all"]["brier"] for m in models]
    for m, x, y in zip(models, xs, ys):
        if m == SONNET:
            ax.scatter(x, y, s=60, facecolor="white", edgecolor=INK2, linewidth=1.4, zorder=4)
        else:
            ax.scatter(x, y, s=60, color=colour[m], edgecolor="white", linewidth=1.4, zorder=4)
    crowd = [i for i, x in enumerate(xs) if x >= 93.5]
    col = repel([ys[i] for i in crowd], 0.0046)
    for i, yy in zip(crowd, col):
        name = SHORT[models[i]] + (" (extra, not ranked)" if models[i] == SONNET else "")
        ax.annotate(name, (xs[i], ys[i]), xytext=(98.0, yy), fontsize=8.8, color=INK, ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", color=AXIS, linewidth=0.6, shrinkA=0, shrinkB=4))
    rest = [i for i in range(len(xs)) if i not in crowd]
    ly = repel([ys[i] for i in rest], 0.0042)
    for i, yy in zip(rest, ly):
        ax.annotate(SHORT[models[i]], (xs[i], ys[i]), xytext=(xs[i] + 0.35, yy), fontsize=8.8, color=INK, ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", color=AXIS, linewidth=0.6, shrinkA=0, shrinkB=4))
    ax.set_xlabel("Accuracy on the fresh set (%)")
    ax.set_ylabel("Brier score (lower is better)")
    ax.set_xlim(84, 105.5)
    ax.set_xticks(range(84, 100, 2))
    ax.set_ylim(0.015, 0.098)
    handles = [Line2D([], [], marker="o", linestyle="", color=c, markersize=7, label=l)
               for c, l in zip((BLUE, ORANGE, AQUA), ("Group 1 (can't be told apart)", "Group 2", "Group 3"))]
    ax.legend(handles=handles, loc="upper right")
    ax.spines["bottom"].set_bounds(84, 99)
    save(fig, "fig2-fresh-accuracy-brier")


def fig_scope_sentence(s):
    """In-scope card messages on the fresh set: the older scope sentence against the tighter one."""
    fr1, fr2 = s["routing"]["fresh"]["scoped_v1"], s["routing"]["fresh"]["scoped_v2"]
    models = [m for m in fr1 if m != SONNET]
    a = {m: 100 * fr1[m]["by_category"]["in_card"]["accuracy"] for m in models}
    b = {m: 100 * fr2[m]["by_category"]["in_card"]["accuracy"] for m in models}
    order = sorted(models, key=lambda m: a[m])
    fig, ax = plt.subplots(figsize=(6.6, 4.9))
    style(ax)
    for i, m in enumerate(order):
        ax.plot([a[m], b[m]], [i, i], color=GRID, linewidth=2.2, zorder=1)
        ax.scatter(a[m], i, s=50, color=ORANGE, edgecolor="white", linewidth=1.2, zorder=3)
        ax.scatter(b[m], i, s=50, color=BLUE, edgecolor="white", linewidth=1.2, zorder=4)
    ax.set_yticks(range(len(order)), [SHORT[m] for m in order])
    ax.invert_yaxis()
    ax.set_xlim(0, 103)
    ax.set_xlabel("Card charges, fraud and bills routed right (%, 45 messages)")
    handles = [Line2D([], [], marker="o", linestyle="", color=ORANGE, markersize=7, label="Older scope sentence (from the first post)"),
               Line2D([], [], marker="o", linestyle="", color=BLUE, markersize=7, label="Tighter scope sentence")]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, handletextpad=0.3, columnspacing=1.2)
    save(fig, "fig3-scope-sentence")


def fig_planted(s):
    """Share of messages sent to the skill a fake policy line named, with and without the line."""
    pl = s["stress"]["planted"]
    order = sorted(pl, key=lambda m: pl[m]["near"]["target_rate"])
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 5.0), sharey=True)
    for ax, kind, title in ((axes[0], "in", "In-scope messages"), (axes[1], "near", "Near-miss messages")):
        style(ax)
        for i, m in enumerate(order):
            v = pl[m][kind]
            ax.barh(i, 100 * v["target_rate"], height=0.62, color=BLUE, zorder=2)
            ax.plot([100 * v["target_rate_clean"]] * 2, [i - 0.36, i + 0.36], color=INK, linewidth=1.6, zorder=3)
        ax.set_xlim(0, 100)
        ax.set_title(title)
        ax.set_xlabel("Sent to the planted skill (%)")
    axes[0].set_yticks(range(len(order)), [SHORT[m] for m in order])
    axes[0].invert_yaxis()
    handles = [plt.Rectangle((0, 0), 1, 1, color=BLUE, label="With the fake policy line"),
               Line2D([], [], color=INK, linewidth=1.6, label="Same messages without it")]
    fig.legend(handles=handles, loc="upper left", ncol=2, bbox_to_anchor=(0.0, 1.04))
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save(fig, "fig4-planted-policy")


def fig_reliability(s):
    """Reliability on CLINC150 test (in-scope plus near-miss), tighter scope sentence, six models."""
    models = ["typesafe/jev-1.14", "google/gemini-decision-1", "openai/gpt-6-luna-decisions",
              "microsoft/microsoft-decision-1.1", "liquid/d1.2-ultra", HAIKU]
    fig, axes = plt.subplots(2, 3, figsize=(6.6, 4.8), sharex=True, sharey=True)
    for ax, m in zip(axes.flat, models):
        rows = [r for r in subset(rows_of("r1", m, "scoped_v2.test"), "in_near") if top_prob(r) is not None]
        style(ax, "both")
        ax.plot([0.5, 1], [0.5, 1], color=AXIS, linewidth=1, linestyle=(0, (3, 2)))
        xs, ys, ns = [], [], []
        for b in range(5, 10):
            lo, hi = b / 10, (b + 1) / 10
            inside = [r for r in rows if lo < top_prob(r) <= hi]
            if len(inside) >= 10:
                xs.append(sum(top_prob(r) for r in inside) / len(inside))
                ys.append(sum(r["pred"] == r["label"] for r in inside) / len(inside))
                ns.append(len(inside))
        ax.plot(xs, ys, color=BLUE, linewidth=2, zorder=3)
        ax.scatter(xs, ys, s=[12 + n / 12 for n in ns], color=BLUE, edgecolor="white", linewidth=1, zorder=4)
        ax.set_title(SHORT[m], fontsize=9.5)
        ax.set_xlim(0.5, 1.01)
        ax.set_ylim(0.3, 1.02)
    for ax in axes[1]:
        ax.set_xlabel("Stated probability")
    for ax in axes[:, 0]:
        ax.set_ylabel("Share right")
    fig.tight_layout()
    save(fig, "fig5-reliability")


def fig_toolcall(s):
    """Tool-call gate (When2Call): accuracy, and unneeded tool calls."""
    w = s["w2c"]
    order = sorted(w, key=lambda m: -w[m]["accuracy"])
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 4.9), sharey=True)
    for ax, key, title, colour in ((axes[0], "accuracy", "Right next step (%)", BLUE),
                                   (axes[1], "unwarranted_tool_call", "Tool called when it shouldn't be (%)", ORANGE)):
        style(ax)
        for i, m in enumerate(order):
            ax.barh(i, 100 * w[m][key], height=0.62, color=colour, zorder=2)
            ax.text(100 * w[m][key] + 1, i, f"{100 * w[m][key]:.0f}", va="center", fontsize=8.5, color=INK2)
        ax.set_title(title, fontsize=10.5)
        ax.set_xlim(0, 100)
    axes[0].set_yticks(range(len(order)), [SHORT[m] for m in order])
    axes[0].invert_yaxis()
    fig.tight_layout()
    save(fig, "fig6-tool-call-gate")


def fig_cost_latency(s):
    """Median latency (200 sequential calls through OpenRouter) against cost per 1,000 decisions."""
    lat, cost = s["latency"], s["cost"]
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    style(ax, "both")
    pts = []
    for m in cost:
        key = f"openrouter:{m}"
        if key in lat and m != "typesafe/jev-1.13":
            name = "Jev 1.14 and 1.13" if m == "typesafe/jev-1.14" else SHORT[m]
            pts.append((name, lat[key]["p50"], cost[m]["cost_per_1000_decisions"]))
    for _, x, y in pts:
        ax.scatter(x, y, s=55, color=BLUE, edgecolor="white", linewidth=1.3, zorder=3)
    import math
    ly = repel([math.log10(y) for _, _, y in pts], 0.075)
    for (name, x, y), yy in zip(pts, ly):
        ax.annotate(name, (x, y), xytext=(x + 16, 10 ** yy), fontsize=8.8, va="center",
                    arrowprops=dict(arrowstyle="-", color=AXIS, linewidth=0.6, shrinkA=0, shrinkB=4))
    ax.set_yscale("log")
    ax.set_yticks([0.005, 0.01, 0.02, 0.05, 0.1], ["$0.005", "$0.01", "$0.02", "$0.05", "$0.10"])
    ax.minorticks_off()
    ax.set_xlabel("Median latency through OpenRouter (ms)")
    ax.set_ylabel("Cost per 1,000 decisions (log scale)")
    ax.set_xlim(150, 1000)
    ax.set_ylim(0.004, 0.16)
    save(fig, "fig7-cost-latency")


def main() -> None:
    s = json.load(open(RESULTS / "summary.json"))
    fig_threshold_transfer(s)
    fig_accuracy_brier(s)
    fig_scope_sentence(s)
    fig_planted(s)
    fig_reliability(s)
    fig_toolcall(s)
    fig_cost_latency(s)


if __name__ == "__main__":
    main()
