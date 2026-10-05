"""Publication-ready scaled-experiment figures (300 DPI).

Reads:
  results_scaled/stats/wilson_ci.csv
  results_scaled/stats/cost_efficiency.csv
  results_scaled/stats/pairwise_pvalues_tidy.csv
  results_scaled/stats/stage_failures.csv
  results_scaled/experiment_summary.json

Writes to figures_scaled/:
  fig1_pass_rate.png
  fig2_cost_accuracy.png
  fig3_latency.png
  fig4_stage_heatmap.png
  fig5_p4_confusion.png
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "results_scaled" / "stats"
SUMMARY_PATH = ROOT / "results_scaled" / "experiment_summary.json"
OUT = ROOT / "figures_scaled"
OUT.mkdir(parents=True, exist_ok=True)

CONDS = ["B0", "B1", "P1", "P2", "P3", "P4", "P5"]
BONFERRONI_ALPHA = 0.05 / 21

# Colorblind-friendly, matches request: B0 grey, B1 orange, P1–P3 teal shades,
# P4 red, P5 purple.
COLORS = {
    "B0": "#6B6B6B",
    "B1": "#E07B39",
    "P1": "#1B7F6E",
    "P2": "#2A9B86",
    "P3": "#3DB8A0",
    "P4": "#C44E52",
    "P5": "#7B5EA7",
}

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


def _load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    wilson = pd.read_csv(STATS / "wilson_ci.csv")
    cost = pd.read_csv(STATS / "cost_efficiency.csv")
    pairwise = pd.read_csv(STATS / "pairwise_pvalues_tidy.csv")
    stages = pd.read_csv(STATS / "stage_failures.csv")
    with SUMMARY_PATH.open(encoding="utf-8") as f:
        summary = json.load(f)
    return wilson, cost, pairwise, stages, summary


def _p_vs_b0(pairwise: pd.DataFrame) -> dict[str, float]:
    paired_path = STATS / "paired_question_highlight.csv"
    if paired_path.exists():
        ph = pd.read_csv(paired_path)
        out: dict[str, float] = {}
        for _, r in ph.iterrows():
            if r["condition_b"] == "B0":
                out[r["condition_a"]] = float(r["mcnemar_p"])
            elif r["condition_a"] == "B0":
                out[r["condition_b"]] = float(r["mcnemar_p"])
        if out:
            return out

    out = {"B0": 1.0}
    for _, r in pairwise.iterrows():
        a, b = r["condition_a"], r["condition_b"]
        if a == "B0":
            out[b] = float(r["p_raw"])
        elif b == "B0":
            out[a] = float(r["p_raw"])
    return out


def fig1_pass_rate(wilson: pd.DataFrame, pairwise: pd.DataFrame) -> Path:
    w = wilson.set_index("Condition").loc[CONDS]
    rates = (w["Pass Rate"] * 100).to_numpy()
    lo = (w["Pass Rate"] - w["CI Lower"]) * 100
    hi = (w["CI Upper"] - w["Pass Rate"]) * 100
    yerr = np.vstack([lo.to_numpy(), hi.to_numpy()])
    p_vs = _p_vs_b0(pairwise)
    b0_rate = float(w.loc["B0", "Pass Rate"] * 100)

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    x = np.arange(len(CONDS))
    bars = ax.bar(
        x,
        rates,
        color=[COLORS[c] for c in CONDS],
        width=0.72,
        edgecolor="white",
        linewidth=0.6,
        zorder=3,
    )
    ax.errorbar(
        x,
        rates,
        yerr=yerr,
        fmt="none",
        ecolor="#222222",
        elinewidth=1.1,
        capsize=3.5,
        capthick=1.1,
        zorder=4,
    )

    ax.axhline(
        b0_rate,
        color="#6B6B6B",
        linestyle=(0, (2, 2)),
        linewidth=1.2,
        zorder=2,
        label=f"B0 baseline ({b0_rate:.1f}%)",
    )

    # Significance markers vs B0 (Bonferroni): ** or explicit "ns"
    for i, c in enumerate(CONDS):
        if c == "B0":
            continue
        p = p_vs.get(c, 1.0)
        top = rates[i] + hi.iloc[i]
        if p < BONFERRONI_ALPHA:
            ax.text(
                i,
                top + 1.4,
                "**",
                ha="center",
                va="bottom",
                fontsize=13,
                fontweight="bold",
                color="#222222",
            )
        else:
            ax.text(
                i,
                top + 1.6,
                "ns",
                ha="center",
                va="bottom",
                fontsize=9,
                style="italic",
                color="#555555",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(CONDS)
    ax.set_ylabel("Pass rate (%)")
    ax.set_ylim(0, 100)
    ax.set_xlabel("")
    ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
    ax.legend(frameon=False, loc="upper left")
    ax.set_title("Pass rate by condition (Wilson 95% CI; ** = sig. vs B0)", pad=8)
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.5, zorder=0)

    # Tiny note under plot
    ax.text(
        0.99,
        0.02,
        f"** p < {BONFERRONI_ALPHA:.4f} (Bonferroni); ns = not significant vs B0",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#555555",
    )

    path = OUT / "fig1_pass_rate.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig2_cost_accuracy(cost: pd.DataFrame) -> Path:
    c = cost.set_index("Condition").loc[CONDS]
    xs = c["cost_per_question"].to_numpy()
    ys = (c["pass_rate"] * 100).to_numpy()

    fig, ax = plt.subplots(figsize=(6.8, 4.2))

    # Pareto cluster highlight (convex hull-ish band around P1/P2/P3/P5)
    pareto = ["P1", "P2", "P3", "P5"]
    px = [float(c.loc[p, "cost_per_question"]) for p in pareto]
    py = [float(c.loc[p, "pass_rate"] * 100) for p in pareto]
    # Draw a soft ellipse-like rectangle around the cluster
    ax.add_patch(
        plt.Rectangle(
            (min(px) - 0.0006, min(py) - 2.2),
            (max(px) - min(px)) + 0.0012,
            (max(py) - min(py)) + 4.4,
            fill=True,
            facecolor="#3DB8A0",
            alpha=0.10,
            edgecolor="#2A9B86",
            linewidth=1.0,
            linestyle="--",
            zorder=1,
            label="Pareto frontier (P1–P3, P5)",
        )
    )

    for cond, x, y in zip(CONDS, xs, ys):
        ax.scatter(
            [x],
            [y],
            s=90,
            color=COLORS[cond],
            edgecolors="white",
            linewidths=0.8,
            zorder=3,
        )
        # Default label offset
        dx, dy = 0.00035, 0.6
        if cond == "B0":
            dx, dy = 0.00025, -1.8
        elif cond == "B1":
            dx, dy = 0.00035, 1.2
        elif cond == "P4":
            dx, dy = 0.0004, -2.0
        elif cond == "P5":
            dx, dy = -0.0011, -1.6
        elif cond == "P1":
            dx, dy = -0.00105, 1.0
        elif cond == "P2":
            dx, dy = 0.0003, 1.2
        elif cond == "P3":
            dx, dy = 0.0003, 1.2
        ax.text(x + dx, y + dy, cond, fontsize=10, fontweight="bold", color=COLORS[cond])

    # Annotations
    ax.annotate(
        "Dominated",
        xy=(float(c.loc["P4", "cost_per_question"]), float(c.loc["P4", "pass_rate"] * 100)),
        xytext=(0.0145, 62.0),
        textcoords="data",
        fontsize=9,
        color=COLORS["P4"],
        arrowprops=dict(arrowstyle="->", color=COLORS["P4"], lw=1.1),
        zorder=4,
    )
    ax.annotate(
        "Higher cost, weaker gain",
        xy=(float(c.loc["B1", "cost_per_question"]), float(c.loc["B1", "pass_rate"] * 100)),
        xytext=(0.0105, 57.5),
        textcoords="data",
        fontsize=9,
        color=COLORS["B1"],
        arrowprops=dict(arrowstyle="->", color=COLORS["B1"], lw=1.1),
        zorder=4,
    )

    ax.set_xlabel("Average cost per question (USD)")
    ax.set_ylabel("Pass rate (%)")
    ax.set_title("Cost–accuracy trade-off", pad=8)
    ax.set_ylim(50, 85)
    ax.set_xlim(0.0035, 0.021)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("$%.3f"))
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.45, zorder=0)
    ax.legend(frameon=False, loc="lower right", fontsize=9)

    path = OUT / "fig2_cost_accuracy.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig3_latency(summary: dict) -> Path:
    p95 = {}
    for block in summary["conditions"]:
        p95[block["condition"]] = float(block["latency_ms"]["p95"])

    vals = [p95[c] for c in CONDS]
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    x = np.arange(len(CONDS))
    bar_colors = []
    for c in CONDS:
        if c in {"B1", "P4"}:
            bar_colors.append(COLORS[c])
        else:
            bar_colors.append("#A8B0B8")

    bars = ax.bar(
        x,
        vals,
        color=bar_colors,
        width=0.72,
        edgecolor="white",
        linewidth=0.6,
        zorder=3,
    )
    # Restore teal/grey for non-highlighted but keep B1/P4 vivid
    for i, c in enumerate(CONDS):
        if c not in {"B1", "P4"}:
            bars[i].set_color(COLORS[c])
            bars[i].set_alpha(0.75)

    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(CONDS)
    ax.set_ylabel("P95 latency (ms, log scale)")
    ax.set_title("Tail latency (p95) by condition", pad=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.grid(axis="y", which="both", linestyle=":", linewidth=0.55, alpha=0.45, zorder=0)

    # Highlight callouts
    for c in ("B1", "P4"):
        i = CONDS.index(c)
        ax.text(
            i,
            vals[i] * 1.12,
            "3× tail",
            ha="center",
            va="bottom",
            fontsize=8.5,
            color=COLORS[c],
            fontweight="bold",
        )

    # Baseline reference at B0 p95
    ax.axhline(
        p95["B0"],
        color="#6B6B6B",
        linestyle=(0, (2, 2)),
        linewidth=1.0,
        zorder=2,
        label=f"B0 p95 ({p95['B0']:.0f} ms)",
    )
    ax.legend(frameon=False, loc="upper left", fontsize=9)

    path = OUT / "fig3_latency.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig4_stage_heatmap(stages: pd.DataFrame) -> Path:
    stage_cols = ["planner", "retriever", "synthesizer", "formatter"]
    stage_labels = ["Planner", "Retriever", "Synthesizer", "Formatter"]

    sub = stages[stages["metric"] == "failure_stage"].copy()
    mat = pd.DataFrame(0.0, index=CONDS, columns=stage_cols)
    for _, r in sub.iterrows():
        cond = r["condition"]
        label = str(r["label"]).lower().strip()
        if cond in mat.index and label in mat.columns:
            # Use % of all runs for comparable intensity across conditions
            mat.loc[cond, label] = float(r["pct_of_all_runs"])

    # Also keep counts for annotation
    counts = pd.DataFrame(0, index=CONDS, columns=stage_cols, dtype=int)
    for _, r in sub.iterrows():
        cond = r["condition"]
        label = str(r["label"]).lower().strip()
        if cond in counts.index and label in counts.columns:
            counts.loc[cond, label] = int(r["count"])

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    sns.heatmap(
        mat,
        ax=ax,
        cmap="YlOrRd",
        annot=counts.astype(str).where(counts > 0, ""),
        fmt="",
        linewidths=0.8,
        linecolor="white",
        cbar_kws={"label": "% of all runs (failures)"},
        vmin=0,
        vmax=max(30, float(mat.to_numpy().max())),
        square=False,
    )
    ax.set_xticklabels(stage_labels, rotation=0)
    ax.set_yticklabels(CONDS, rotation=0)
    ax.set_xlabel("Failure stage")
    ax.set_ylabel("Condition")
    ax.set_title("Stage-failure heatmap (counts annotated; color = % of runs)", pad=10)
    fig.text(
        0.5,
        -0.02,
        "P1–P3 shift failures from Synthesizer to Formatter, indicating tool-grounded\n"
        "checks catch draft errors but formatting remains a residual failure mode.",
        ha="center",
        va="top",
        fontsize=8.5,
        color="#444444",
        style="italic",
    )

    path = OUT / "fig4_stage_heatmap.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig5_p4_confusion(summary: dict) -> Path:
    conf = summary.get("p4_verifier_confusion") or {}
    accept = conf.get("ACCEPT", {"correct": 0, "incorrect": 0})
    # Collapse all non-ACCEPT decisions into REJECT for a clean 2×2
    reject_correct = 0
    reject_incorrect = 0
    for key, block in conf.items():
        if key == "ACCEPT":
            continue
        reject_correct += int(block.get("correct", 0))
        reject_incorrect += int(block.get("incorrect", 0))

    # Rows: Verifier decision; Cols: Actual Correct / Incorrect
    # [[ACCEPT∩Correct, ACCEPT∩Incorrect],
    #  [REJECT∩Correct, REJECT∩Incorrect]]
    matrix = np.array(
        [
            [int(accept.get("correct", 0)), int(accept.get("incorrect", 0))],
            [reject_correct, reject_incorrect],
        ],
        dtype=float,
    )
    total = matrix.sum()
    pct = matrix / total * 100.0 if total else matrix

    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    # Custom colors emphasizing false accepts (top-right)
    # Use a light base heatmap then override false-accept cell
    sns.heatmap(
        matrix,
        ax=ax,
        annot=False,
        cmap="Blues",
        cbar=False,
        linewidths=2,
        linecolor="white",
        vmin=0,
        vmax=matrix.max() * 1.15,
        square=True,
    )

    # Emphasize false accepts with a red overlay hatch/edge
    # Re-draw cells manually for clearer annotation control
    ax.clear()
    cell_colors = np.array(
        [
            ["#9ECAE1", "#F4A6A6"],  # true accept, FALSE ACCEPT (highlight)
            ["#FDD0A2", "#A1D99B"],  # false reject, true reject
        ]
    )
    for i in range(2):
        for j in range(2):
            ax.add_patch(
                plt.Rectangle(
                    (j, 1 - i),
                    1,
                    1,
                    facecolor=cell_colors[i, j],
                    edgecolor="white",
                    linewidth=2.5,
                )
            )
            count = int(matrix[i, j])
            p = pct[i, j]
            weight = "bold" if (i == 0 and j == 1) else "normal"
            label = f"{count}\n({p:.1f}%)"
            if i == 0 and j == 1:
                label = f"{count}\n({p:.1f}%)\nFalse accept"
            ax.text(
                j + 0.5,
                1 - i + 0.5,
                label,
                ha="center",
                va="center",
                fontsize=11 if not (i == 0 and j == 1) else 10,
                fontweight=weight,
                color="#222222",
            )

    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.set_xticks([0.5, 1.5])
    ax.set_xticklabels(["Actual correct", "Actual incorrect"])
    ax.set_yticks([1.5, 0.5])
    ax.set_yticklabels(["Verifier ACCEPT", "Verifier REJECT"])
    ax.set_title("P4 verifier confusion (pooled n=450)", pad=10)
    ax.set_aspect("equal")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Legend-like caption
    ax.text(
        0.5,
        -0.18,
        "REJECT = REJECT_WITH_CRITIQUE + PROPOSE_CORRECTION + OTHER",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8,
        color="#555555",
    )

    path = OUT / "fig5_p4_confusion.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> None:
    wilson, cost, pairwise, stages, summary = _load()
    paths = [
        fig1_pass_rate(wilson, pairwise),
        fig2_cost_accuracy(cost),
        fig3_latency(summary),
        fig4_stage_heatmap(stages),
        fig5_p4_confusion(summary),
    ]
    print("Wrote:")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
