"""Shared question-level pass-rate statistics (McNemar, Wilson)."""

from __future__ import annotations

import math
from itertools import combinations
from typing import Iterable

import numpy as np
import pandas as pd
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.proportion import proportion_confint


def cohen_h(p1: float, p2: float) -> float:
    p1 = min(max(p1, 0.0), 1.0)
    p2 = min(max(p2, 0.0), 1.0)
    return 2.0 * math.asin(math.sqrt(p1)) - 2.0 * math.asin(math.sqrt(p2))


def question_majority_table(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Group by condition -> per-question majority pass and trial fraction."""
    out: dict[str, pd.DataFrame] = {}
    for cond, sub in df.groupby("condition"):
        g = sub.groupby("question_id")["pass"].agg(["sum", "count"])
        g["majority"] = g["sum"] >= np.ceil(g["count"] / 2)
        g["frac"] = g["sum"] / g["count"]
        out[str(cond)] = g
    return out


def mcnemar_pair(
    qa: pd.DataFrame, qb: pd.DataFrame, *, question_ids: Iterable[str] | None = None
) -> dict:
    """McNemar on paired majority outcomes; Δpp = gain of qa over qb."""
    ids = qa.index.intersection(qb.index)
    if question_ids is not None:
        want = set(question_ids)
        ids = ids.intersection(want)
    ids = ids.sort_values()
    a = qa.loc[ids, "majority"].astype(bool)
    b = qb.loc[ids, "majority"].astype(bool)
    n01 = int((~a & b).sum())
    n10 = int((a & ~b).sum())
    n00 = int((~a & ~b).sum())
    n11 = int((a & b).sum())
    table = [[n00, n01], [n10, n11]]
    res = mcnemar(table, exact=False, correction=True)
    pa, pb = float(a.mean()), float(b.mean())
    return {
        "n_questions": len(ids),
        "pass_a_majority": pa,
        "pass_b_majority": pb,
        "delta_pp_majority": round(100.0 * (pa - pb), 1),
        "mcnemar_p": float(res.pvalue),
        "discordant_b_gain": n01,
        "discordant_a_gain": n10,
        "cohen_h_majority": round(cohen_h(pa, pb), 2),
    }


def wilson_pooled(df: pd.DataFrame, condition: str) -> dict:
    sub = df[df["condition"] == condition]
    n = len(sub)
    k = int(sub["pass"].sum())
    rate = k / n if n else 0.0
    lo, hi = proportion_confint(k, n, alpha=0.05, method="wilson") if n else (0.0, 0.0)
    return {
        "condition": condition,
        "n_runs": n,
        "n_pass": k,
        "pass_rate_pooled": rate,
        "wilson_lo": float(lo),
        "wilson_hi": float(hi),
    }


def all_pairwise_mcnemar(
    qtables: dict[str, pd.DataFrame],
    conditions: list[str],
    *,
    bonferroni_pairs: int | None = None,
) -> pd.DataFrame:
    rows = []
    alpha = 0.05 / bonferroni_pairs if bonferroni_pairs else None
    for a, b in combinations(conditions, 2):
        m = mcnemar_pair(qtables[a], qtables[b])
        row = {
            "condition_a": a,
            "condition_b": b,
            **m,
        }
        if alpha is not None:
            row["significant_bonferroni"] = m["mcnemar_p"] < alpha
        rows.append(row)
    return pd.DataFrame(rows)
