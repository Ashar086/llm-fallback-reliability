"""Phase 4 Results figures — data hardcoded from significance_results.md."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# --- Ground truth from significance_results.md (do not recompute) ---
CONDS = ["B0", "B1", "P1", "P2", "P3", "P4"]

# Pooled pass % (section 2)
PASS = {
    "B0": 60.0,
    "B1": 64.2,
    "P1": 75.8,
    "P2": 75.8,
    "P3": 78.3,
    "P4": 70.0,
}
# Per-trial pass % (section 1) — error bars = trial min–max
TRIAL_PASS = {
    "B0": [57.5, 62.5, 60.0],
    "B1": [62.5, 67.5, 62.5],
    "P1": [77.5, 75.0, 75.0],
    "P2": [75.0, 75.0, 77.5],
    "P3": [77.5, 80.0, 77.5],
    "P4": [67.5, 72.5],
}
# Significance vs B0 (Fisher/table stars; B0 is baseline)
SIG_VS_B0 = {
    "B0": "",
    "B1": "ns",
    "P1": "**",
    "P2": "**",
    "P3": "**",
    "P4": "ns",
}
# Pooled cost avg/Q (section 2)
COST_PER_Q = {
    "B0": 0.0060,
    "B1": 0.0108,
    "P1": 0.0075,
    "P2": 0.0075,
    "P3": 0.0075,
    "P4": 0.0164,
}
# Pooled p95 latency ms (section 2)
P95_MS = {
    "B0": 10397,
    "B1": 34506,
    "P1": 10398,
    "P2": 9591,
    "P3": 10369,
    "P4": 30708,
}

# Consistent colors across all figures
COLORS = {
    "B0": "#5B5B5B",  # neutral baseline
    "B1": "#C47B2C",  # amber — costly blind retry
    "P1": "#1F6B5C",  # teal cluster
    "P2": "#2A8F7C",
    "P3": "#3AAD96",
    "P4": "#A33B3B",  # red — expensive / dominated
}

# Publication rc
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif", "Times", "serif"],
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 12,
        "xtick.labelsize": 11,
        "ytick.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.08,
    }
)


def fig1_pass_rate() -> Path:
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    x = np.arange(len(CONDS))
    heights = [PASS[c] for c in CONDS]
    yerr_lo = [PASS[c] - min(TRIAL_PASS[c]) for c in CONDS]
    yerr_hi = [max(TRIAL_PASS[c]) - PASS[c] for c in CONDS]
    colors = [COLORS[c] for c in CONDS]

    bars = ax.bar(
        x,
        heights,
        width=0.72,
        color=colors,
        edgecolor="white",
        linewidth=0.6,
        zorder=2,
    )
    ax.errorbar(
        x,
        heights,
        yerr=[yerr_lo, yerr_hi],
        fmt="none",
        ecolor="#222222",
        elinewidth=1.1,
        capsize=3.5,
        capthick=1.1,
        zorder=3,
    )

    # Significance markers vs B0 above error caps
    for i, c in enumerate(CONDS):
        mark = SIG_VS_B0[c]
        if not mark:
            continue
        top = heights[i] + yerr_hi[i]
        ax.text(
            i,
            top + 1.2,
            mark,
            ha="center",
            va="bottom",
            fontsize=10 if mark == "ns" else 12,
            color="#222222",
            fontweight="normal" if mark == "ns" else "bold",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(CONDS)
    ax.set_ylabel("Pass rate (%)")
    ax.set_ylim(50, 88)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(5))
    ax.axhline(PASS["B0"], color="#5B5B5B", ls=":", lw=0.9, alpha=0.7, zorder=1)
    ax.set_title("Pass rate by condition (pooled; error bars = trial min–max)", pad=8)
    # Small legend note
    ax.text(
        0.99,
        0.02,
        "Markers: significance vs B0  ·  ** p<0.01  ·  ns = not significant",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.5,
        color="#555555",
    )
    path = OUT / "fig1_pass_rate.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig2_pareto() -> Path:
    fig, ax = plt.subplots(figsize=(6.2, 4.2))

    # Soft highlight behind the P1/P2/P3 good-value region
    ax.axhspan(74, 80.5, xmin=0.18, xmax=0.42, color="#2A8F7C", alpha=0.08, zorder=0)
    # Vertical band for the cheap cluster (~0.007–0.008)
    ax.axvspan(0.0068, 0.0082, color="#2A8F7C", alpha=0.06, zorder=0)

    # Dominated / expensive region hint (right side)
    ax.axvspan(0.0095, 0.0175, color="#A33B3B", alpha=0.04, zorder=0)

    for c in CONDS:
        ax.scatter(
            COST_PER_Q[c],
            PASS[c],
            s=110 if c in {"P1", "P2", "P3"} else 90,
            color=COLORS[c],
            edgecolors="white",
            linewidths=0.8,
            zorder=3,
            label=c,
        )

    # Labels kept to the RIGHT of the teal cluster
    offsets = {
        "B0": (-18, -14),
        "B1": (8, -12),
        "P1": (18, 5),
        "P2": (18, -13),
        "P3": (18, 7),
        "P4": (-8, 10),
    }
    for c in CONDS:
        dx, dy = offsets[c]
        weight = "bold" if c in {"P1", "P2", "P3"} else "normal"
        ax.annotate(
            c,
            (COST_PER_Q[c], PASS[c]),
            textcoords="offset points",
            xytext=(dx, dy),
            fontsize=10,
            fontweight=weight,
            color=COLORS[c],
            zorder=4,
        )

    # Arrow to top-LEFT corner of shaded box — away from right-side labels
    ax.annotate(
        "Good value\n(P1–P3)",
        xy=(0.00685, 80.4),
        xytext=(0.0051, 83.8),
        fontsize=8.5,
        color="#1F6B5C",
        arrowprops=dict(
            arrowstyle="-|>",
            color="#1F6B5C",
            lw=0.9,
            shrinkB=1,
            mutation_scale=8,
            connectionstyle="arc3,rad=0",
        ),
        ha="center",
        va="bottom",
        zorder=5,
    )
    ax.annotate(
        "Dominated\n(higher cost,\nweaker accuracy)",
        xy=(0.0135, 67),
        xytext=(0.0138, 58),
        fontsize=8,
        color="#A33B3B",
        ha="center",
        arrowprops=dict(arrowstyle="->", color="#A33B3B", lw=0.8),
    )

    ax.set_xlabel("Average cost per question (USD)")
    ax.set_ylabel("Pass rate (%)")
    ax.set_xlim(0.0045, 0.018)
    ax.set_ylim(55, 85)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("$%.3f"))
    ax.set_title("Cost–accuracy tradeoff (pooled)", pad=8)
    path = OUT / "fig2_cost_vs_accuracy_pareto.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig3_p95_latency() -> Path:
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    x = np.arange(len(CONDS))
    vals_s = [P95_MS[c] / 1000.0 for c in CONDS]  # seconds for readability
    colors = [COLORS[c] for c in CONDS]

    ax.bar(x, vals_s, width=0.72, color=colors, edgecolor="white", linewidth=0.6)
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(CONDS)
    ax.set_ylabel("p95 latency (seconds, log scale)")
    ax.set_ylim(7, 50)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(mticker.NullFormatter())
    ax.set_title("p95 end-to-end latency by condition (pooled)", pad=8)

    # Value labels
    for i, v in enumerate(vals_s):
        ax.text(
            i,
            v * 1.08,
            f"{v:.1f}s",
            ha="center",
            va="bottom",
            fontsize=8.5,
            color="#333333",
        )

    path = OUT / "fig3_p95_latency.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> None:
    paths = [fig1_pass_rate(), fig2_pareto(), fig3_p95_latency()]
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
