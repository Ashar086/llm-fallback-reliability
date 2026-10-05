"""Question-level paired pass-rate tests (150 Hotpot questions × 3 trials)."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.contingency_tables import mcnemar

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "results_scaled" / "question_outcomes.csv"
OUT = ROOT / "results_scaled" / "stats" / "paired_question_tests.json"
CONDS = ["B0", "B1", "P1", "P2", "P3", "P4", "P5"]
BONF = 0.05 / 21

HIGHLIGHT = [
    ("P1", "B0"),
    ("P2", "B0"),
    ("P3", "B0"),
    ("P5", "B0"),
    ("P4", "B0"),
    ("B1", "B0"),
    ("P3", "P1"),
    ("P3", "P2"),
    ("P3", "P5"),
    ("P5", "P1"),
    ("P5", "P2"),
    ("P4", "P3"),
    ("P4", "P1"),
]


def question_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for c in CONDS:
        sub = df[df["condition"] == c]
        g = sub.groupby("question_id")["pass"].agg(["sum", "count"])
        g["majority"] = g["sum"] >= np.ceil(g["count"] / 2)
        g["frac"] = g["sum"] / g["count"]
        out[c] = g
    return out


def mcnemar_pair(qa: pd.DataFrame, qb: pd.DataFrame) -> dict:
    """qa/qb are majority tables; Δpp = gain of first condition (qa) over second (qb)."""
    ids = qa.index.intersection(qb.index)
    a = qa.loc[ids, "majority"].astype(bool)
    b = qb.loc[ids, "majority"].astype(bool)
    n01 = int((~a & b).sum())
    n10 = int((a & ~b).sum())
    n00 = int((~a & ~b).sum())
    n11 = int((a & b).sum())
    table = [[n00, n01], [n10, n11]]
    res = mcnemar(table, exact=False, correction=True)
    delta_pp = 100.0 * (a.mean() - b.mean())
    return {
        "n_questions": len(ids),
        "delta_pp_majority": round(delta_pp, 1),
        "mcnemar_p": float(res.pvalue),
        "discordant_b_gain": n01,
        "discordant_a_gain": n10,
        "n00": n00,
        "n11": n11,
    }


def wilcoxon_frac(qa: pd.DataFrame, qb: pd.DataFrame) -> dict:
    ids = qa.index.intersection(qb.index)
    a = qa.loc[ids, "frac"].values
    b = qb.loc[ids, "frac"].values
    # two-sided Wilcoxon on paired trial-pass fractions
    stat, p = stats.wilcoxon(b, a, zero_method="wilcox", alternative="two-sided")
    delta_pp = 100.0 * (b.mean() - a.mean())
    return {
        "wilcoxon_p_two_sided": float(p),
        "delta_pp_mean_frac": round(delta_pp, 1),
        "statistic": float(stat),
    }


def cohen_h(p1: float, p2: float) -> float:
    import math

    p1 = min(max(p1, 0.0), 1.0)
    p2 = min(max(p2, 0.0), 1.0)
    return 2.0 * math.asin(math.sqrt(p1)) - 2.0 * math.asin(math.sqrt(p2))


def main() -> None:
    df = pd.read_csv(CSV)
    df["pass"] = df["pass"].astype(bool)
    q = question_tables(df)

    per_cond_majority = {
        c: {
            "n_questions": int(len(q[c])),
            "pass_rate_majority": float(q[c]["majority"].mean()),
            "pass_rate_pooled": float(df[df["condition"] == c]["pass"].mean()),
        }
        for c in CONDS
    }

    pairs = {}
    for a, b in combinations(CONDS, 2):
        m = mcnemar_pair(q[a], q[b])
        w = wilcoxon_frac(q[a], q[b])
        pa = q[a]["majority"].mean()
        pb = q[b]["majority"].mean()
        entry = {**m, **w, "cohen_h_majority": round(cohen_h(pa, pb), 2)}
        entry["sig_bonferroni"] = entry["mcnemar_p"] < BONF
        pairs[f"{a}_vs_{b}"] = entry
        # reverse direction: flip Δpp / h, same p
        rev = dict(entry)
        rev["delta_pp_majority"] = round(-entry["delta_pp_majority"], 1)
        rev["cohen_h_majority"] = round(-entry["cohen_h_majority"], 2)
        rev["delta_pp_mean_frac"] = round(-entry["delta_pp_mean_frac"], 1)
        pairs[f"{b}_vs_{a}"] = rev

    highlight = {}
    for a, b in HIGHLIGHT:
        key = f"{a}_vs_{b}"
        # always compute a vs b with correct sign
        m = mcnemar_pair(q[a], q[b])
        w = wilcoxon_frac(q[a], q[b])
        entry = {
            **m,
            **w,
            "cohen_h_majority": round(cohen_h(q[a]["majority"].mean(), q[b]["majority"].mean()), 2),
            "sig_bonferroni": m["mcnemar_p"] < BONF,
        }
        highlight[key] = entry
        pairs[key] = entry

    payload = {
        "bonferroni_alpha": BONF,
        "definition": (
            "Per question: pass if majority of trials pass (>= ceil(n_trials/2)). "
            "McNemar test on paired majority outcomes across 150 questions; "
            "Wilcoxon signed-rank on paired trial-pass fractions."
        ),
        "per_condition": per_cond_majority,
        "highlight_pairs": highlight,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(highlight, indent=2))


if __name__ == "__main__":
    main()
