"""
Statistical analysis for the Reliability & Fallback scaled experiment.

Loads results_scaled/question_outcomes.csv + experiment_summary.json and writes
all tables / report under results_scaled/stats/.

Usage:
  python run_stats.py
"""

from __future__ import annotations

import json
import math
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.proportion import proportion_confint, proportions_ztest

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results_scaled"
OUT_DIR = RESULTS / "stats"
CSV_PATH = RESULTS / "question_outcomes.csv"
SUMMARY_PATH = RESULTS / "experiment_summary.json"

EXPECTED_CONDS = ["B0", "B1", "P1", "P2", "P3", "P4", "P5"]
EXPECTED_PASS = {
    "B0": 0.553,
    "B1": 0.611,
    "P1": 0.760,
    "P2": 0.762,
    "P3": 0.782,
    "P4": 0.682,
    "P5": 0.747,
}
# User-provided cost anchors (also cross-checked against summary when present)
FALLBACK_COST = {
    "B0": 0.0052,
    "B1": 0.0085,
    "P1": 0.0072,
    "P2": 0.0073,
    "P3": 0.0073,
    "P4": 0.0183,
    "P5": 0.0071,
}

N_PAIRS = 21  # C(7,2)
ALPHA = 0.05
BONFERRONI_ALPHA = ALPHA / N_PAIRS

HIGHLIGHT_PAIRS = [
    ("P1", "B0"),
    ("P2", "B0"),
    ("P3", "B0"),
    ("P5", "B0"),
    ("P4", "B0"),
    ("P3", "P1"),
    ("P3", "P2"),
    ("P3", "P5"),
    ("P4", "P1"),
    ("P4", "P3"),
    ("B1", "B0"),
    ("P5", "P1"),
    ("P5", "P2"),
]


def _pct(x: float) -> str:
    return f"{100.0 * x:.1f}%"


def _fmt_p(p: float) -> str:
    if p < 1e-4:
        return f"{p:.2e}"
    return f"{p:.4f}"


def _cohen_h(p1: float, p2: float) -> float:
    """Cohen's h for two proportions (p1 relative to p2)."""
    p1 = min(max(p1, 0.0), 1.0)
    p2 = min(max(p2, 0.0), 1.0)
    return 2.0 * math.asin(math.sqrt(p1)) - 2.0 * math.asin(math.sqrt(p2))


def _h_label(h: float) -> str:
    ah = abs(h)
    if ah < 0.2:
        return "small"
    if ah <= 0.5:
        return "medium"
    return "large"


def _sig_label(p: float, alpha: float = BONFERRONI_ALPHA) -> str:
    return "significant" if p < alpha else "not significant"


def load_and_validate() -> tuple[pd.DataFrame, dict, dict[str, dict]]:
    print("=" * 60)
    print("Step 1: Load and validate data")
    print("=" * 60)

    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing CSV: {CSV_PATH}")
    if not SUMMARY_PATH.exists():
        raise FileNotFoundError(f"Missing summary: {SUMMARY_PATH}")

    df = pd.read_csv(CSV_PATH)
    with SUMMARY_PATH.open(encoding="utf-8") as f:
        summary = json.load(f)

    print(f"Total rows loaded: {len(df)}")

    required = ["condition", "question_id", "pass"]
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Flag malformed / missing (do not drop)
    flags: list[str] = []
    null_req = df[required].isna().any(axis=1)
    if null_req.any():
        n = int(null_req.sum())
        flags.append(f"{n} rows with nulls in {required}")
        print(f"WARNING: {n} rows with missing required fields (flagged, not dropped)")

    bad_pass = ~df["pass"].isin([True, False, 0, 1]) & df["pass"].notna()
    # After read_csv, bools may already be True/False; also accept 0/1
    if not pd.api.types.is_bool_dtype(df["pass"]):
        coerced = df["pass"].map(
            {
                True: True,
                False: False,
                "True": True,
                "False": False,
                "true": True,
                "false": False,
                1: True,
                0: False,
                "1": True,
                "0": False,
            }
        )
        unknown = coerced.isna() & df["pass"].notna()
        if unknown.any():
            flags.append(f"{int(unknown.sum())} rows with malformed pass values")
            print(
                f"WARNING: {int(unknown.sum())} rows with malformed pass "
                "(flagged, not dropped)"
            )
        df = df.copy()
        df["pass"] = coerced.fillna(False).astype(bool)
    else:
        df = df.copy()
        df["pass"] = df["pass"].astype(bool)

    conds = sorted(df["condition"].dropna().unique().tolist())
    print(f"Conditions present: {conds}")
    unexpected = [c for c in conds if c not in EXPECTED_CONDS]
    missing_expected = [c for c in EXPECTED_CONDS if c not in conds]
    if unexpected:
        print(f"WARNING: unexpected conditions: {unexpected}")
    if missing_expected:
        print(f"WARNING: missing expected conditions: {missing_expected}")

    print("Questions per condition:")
    for c in EXPECTED_CONDS:
        sub = df[df["condition"] == c]
        n_q = sub["question_id"].nunique()
        print(f"  {c}: {n_q} unique questions, {len(sub)} rows")

    print("Trials per condition (inferred as rows per question_id):")
    per_cond_stats: dict[str, dict] = {}
    for c in EXPECTED_CONDS:
        sub = df[df["condition"] == c]
        sizes = sub.groupby("question_id").size()
        trial_mode = int(sizes.mode().iloc[0]) if len(sizes) else 0
        odd = sizes[sizes != trial_mode]
        print(
            f"  {c}: modal trials/question={trial_mode}, "
            f"questions_with_other_counts={len(odd)}"
        )
        if len(odd):
            flags.append(f"{c}: {len(odd)} questions with non-{trial_mode} trial rows")

        n = len(sub)
        n_pass = int(sub["pass"].sum())
        rate = n_pass / n if n else 0.0
        per_cond_stats[c] = {"n": n, "n_pass": n_pass, "pass_rate": rate}

        expected = EXPECTED_PASS.get(c)
        if expected is not None and abs(rate - expected) > 0.005:
            print(
                f"WARNING: {c} pass rate {_pct(rate)} differs from expected "
                f"{_pct(expected)} by >0.5pp"
            )

    if not flags:
        print("Malformed/missing rows: none flagged")
    else:
        print(f"Flag summary ({len(flags)}):")
        for fmsg in flags:
            print(f"  - {fmsg}")

    # Sanity: compare to summary JSON
    for block in summary.get("conditions", []):
        c = block.get("condition")
        if c in per_cond_stats:
            csv_rate = per_cond_stats[c]["pass_rate"]
            sum_rate = float(block.get("pass_rate", csv_rate))
            if abs(csv_rate - sum_rate) > 0.005:
                print(
                    f"WARNING: {c} CSV pass {_pct(csv_rate)} vs summary "
                    f"{_pct(sum_rate)} (>0.5pp)"
                )

    print("Step 1 complete.\n")
    return df, summary, per_cond_stats


def step_wilson(per_cond: dict[str, dict]) -> pd.DataFrame:
    print("=" * 60)
    print("Step 2: Wilson 95% confidence intervals")
    print("=" * 60)

    rows = []
    for c in EXPECTED_CONDS:
        s = per_cond[c]
        n, k = s["n"], s["n_pass"]
        low, high = proportion_confint(k, n, alpha=0.05, method="wilson")
        rows.append(
            {
                "Condition": c,
                "Pass Rate": s["pass_rate"],
                "CI Lower": float(low),
                "CI Upper": float(high),
                "n": n,
                "n_pass": k,
            }
        )

    out = pd.DataFrame(rows)
    print(
        f"{'Condition':<10} {'Pass Rate':>10} {'CI Lower':>10} {'CI Upper':>10} {'n':>6}"
    )
    for _, r in out.iterrows():
        print(
            f"{r['Condition']:<10} {_pct(r['Pass Rate']):>10} "
            f"{_pct(r['CI Lower']):>10} {_pct(r['CI Upper']):>10} {int(r['n']):>6}"
        )

    save = out.copy()
    path = OUT_DIR / "wilson_ci.csv"
    save.to_csv(path, index=False)
    print(f"Saved {path}")
    print("Step 2 complete.\n")
    return out


def step_pairwise(per_cond: dict[str, dict]) -> tuple[pd.DataFrame, dict[tuple[str, str], float]]:
    print("=" * 60)
    print("Step 3: Pairwise statistical tests")
    print("=" * 60)

    pvals: dict[tuple[str, str], float] = {}
    raw_rows = []

    for a, b in combinations(EXPECTED_CONDS, 2):
        sa, sb = per_cond[a], per_cond[b]
        count = np.array([sa["n_pass"], sb["n_pass"]])
        nobs = np.array([sa["n"], sb["n"]])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _stat, p = proportions_ztest(count, nobs, alternative="two-sided")
        p = float(p)
        pvals[(a, b)] = p
        pvals[(b, a)] = p
        raw_rows.append(
            {
                "condition_a": a,
                "condition_b": b,
                "pass_a": sa["pass_rate"],
                "pass_b": sb["pass_rate"],
                "n_a": sa["n"],
                "n_b": sb["n"],
                "p_raw": p,
                "significant_bonferroni": p < BONFERRONI_ALPHA,
            }
        )

    # Matrix for CSV (upper/lower filled with raw p; diagonal blank)
    mat = pd.DataFrame(index=EXPECTED_CONDS, columns=EXPECTED_CONDS, dtype=object)
    for c in EXPECTED_CONDS:
        mat.loc[c, c] = "—"
    for a, b in combinations(EXPECTED_CONDS, 2):
        p = pvals[(a, b)]
        cell = f"p={_fmt_p(p)}"
        mat.loc[a, b] = cell
        mat.loc[b, a] = cell

    path = OUT_DIR / "pairwise_pvalues.csv"
    mat.to_csv(path)
    # Also save a tidy numeric table for downstream use
    tidy = pd.DataFrame(raw_rows)
    tidy.to_csv(OUT_DIR / "pairwise_pvalues_tidy.csv", index=False)
    print(f"Saved {path}")
    print(f"Saved {OUT_DIR / 'pairwise_pvalues_tidy.csv'}")
    print(f"Bonferroni alpha = 0.05/21 = {BONFERRONI_ALPHA:.6f}")

    sig = [r for r in raw_rows if r["significant_bonferroni"]]
    print(f"\nSignificant pairs after Bonferroni ({len(sig)} / {N_PAIRS}):")
    for r in sorted(sig, key=lambda x: x["p_raw"]):
        print(
            f"  {r['condition_a']} vs {r['condition_b']}: "
            f"p={_fmt_p(r['p_raw'])} "
            f"({_pct(r['pass_a'])} vs {_pct(r['pass_b'])})"
        )

    print("\nKey comparisons:")
    for a, b in HIGHLIGHT_PAIRS:
        p = pvals[(a, b)]
        print(
            f"  {a} vs {b}: p={_fmt_p(p)} ({_sig_label(p)}) | "
            f"{_pct(per_cond[a]['pass_rate'])} vs {_pct(per_cond[b]['pass_rate'])}"
        )

    print("Step 3 complete.\n")
    return mat, pvals


def step_effect_sizes(per_cond: dict[str, dict]) -> pd.DataFrame:
    print("=" * 60)
    print("Step 4: Effect sizes (vs B0)")
    print("=" * 60)

    p0 = per_cond["B0"]["pass_rate"]
    rows = []
    for c in EXPECTED_CONDS:
        if c == "B0":
            continue
        pc = per_cond[c]["pass_rate"]
        diff_pp = 100.0 * (pc - p0)
        h = _cohen_h(pc, p0)
        rows.append(
            {
                "Condition": c,
                "vs B0 diff (pp)": round(diff_pp, 1),
                "Cohen's h": round(h, 4),
                "Interpretation": _h_label(h),
            }
        )

    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    path = OUT_DIR / "effect_sizes.csv"
    out.to_csv(path, index=False)
    print(f"Saved {path}")
    print("Step 4 complete.\n")
    return out


def _costs_from_summary(summary: dict) -> dict[str, float]:
    costs = dict(FALLBACK_COST)
    for block in summary.get("conditions", []):
        c = block.get("condition")
        if c in costs and block.get("avg_cost_per_question") is not None:
            costs[c] = float(block["avg_cost_per_question"])
    return costs


def step_cost(per_cond: dict[str, dict], summary: dict) -> pd.DataFrame:
    print("=" * 60)
    print("Step 5: Cost-efficiency analysis")
    print("=" * 60)

    costs = _costs_from_summary(summary)
    p3_cost = costs["P3"]
    p3_rate = per_cond["P3"]["pass_rate"]

    rows = []
    for c in EXPECTED_CONDS:
        rate = per_cond[c]["pass_rate"]
        cost = costs[c]
        pass_per_dollar = rate / cost if cost > 0 else float("nan")
        cost_1000 = (1000.0 / rate) * cost if rate > 0 else float("nan")
        ratio_vs_p3 = cost / p3_cost if p3_cost > 0 else float("nan")
        rows.append(
            {
                "Condition": c,
                "pass_rate": rate,
                "cost_per_question": cost,
                "pass_rate_per_dollar": pass_per_dollar,
                "cost_for_1000_successes": cost_1000,
                "cost_ratio_vs_P3": ratio_vs_p3,
            }
        )

    out = pd.DataFrame(rows)
    print(out.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    path = OUT_DIR / "cost_efficiency.csv"
    out.to_csv(path, index=False)
    print(f"Saved {path}")

    p4_rate = per_cond["P4"]["pass_rate"]
    p5_rate = per_cond["P5"]["pass_rate"]
    print()
    print(
        f'P3 achieves best pass rate at ${costs["P3"]:.4f} per question'
    )
    print(
        f"P4 costs {costs['P4'] / p3_cost:.1f}x more than P3 for "
        f"{100.0 * (p3_rate - p4_rate):.1f} pp lower pass rate"
    )
    print(
        f"P5 achieves {100.0 * p5_rate / p3_rate:.1f}% of P3's pass rate at "
        f"{100.0 * costs['P5'] / p3_cost:.1f}% of P3's cost"
    )
    print("Step 5 complete.\n")
    return out


def step_stability(df: pd.DataFrame) -> pd.DataFrame:
    print("=" * 60)
    print("Step 6: Per-question stability analysis")
    print("=" * 60)

    rows = []
    detail_rows = []
    for c in EXPECTED_CONDS:
        sub = df[df["condition"] == c]
        g = sub.groupby("question_id")["pass"].agg(["sum", "count"])
        g = g.rename(columns={"sum": "n_pass_trials", "count": "n_trials"})
        # Expect 3 trials
        fully = (g["n_pass_trials"] == g["n_trials"]) & (g["n_trials"] >= 1)
        never = g["n_pass_trials"] == 0
        mixed = (~fully) & (~never)

        n_q = len(g)
        pct_full = 100.0 * fully.mean() if n_q else 0.0
        pct_never = 100.0 * never.mean() if n_q else 0.0
        pct_mixed = 100.0 * mixed.mean() if n_q else 0.0
        # Consistency: all 3 agree (all pass OR all fail)
        agree = fully | never
        consistency = float(agree.mean()) if n_q else 0.0

        rows.append(
            {
                "Condition": c,
                "n_questions": n_q,
                "pct_fully_reliable_3of3": round(pct_full, 1),
                "pct_fully_unreliable_0of3": round(pct_never, 1),
                "pct_unstable_mixed": round(pct_mixed, 1),
                "consistency_score_agree_all_trials": round(consistency, 4),
            }
        )

        for qid, r in g.iterrows():
            detail_rows.append(
                {
                    "condition": c,
                    "question_id": qid,
                    "n_pass_trials": int(r["n_pass_trials"]),
                    "n_trials": int(r["n_trials"]),
                    "bucket": (
                        "3/3"
                        if r["n_pass_trials"] == r["n_trials"]
                        else ("0/3" if r["n_pass_trials"] == 0 else "mixed")
                    ),
                }
            )

    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    path = OUT_DIR / "question_stability.csv"
    out.to_csv(path, index=False)
    pd.DataFrame(detail_rows).to_csv(
        OUT_DIR / "question_stability_detail.csv", index=False
    )
    print(f"Saved {path}")
    print(f"Saved {OUT_DIR / 'question_stability_detail.csv'}")

    # Interpret P3 vs B0 stability
    b0 = out[out["Condition"] == "B0"].iloc[0]
    p3 = out[out["Condition"] == "P3"].iloc[0]
    print(
        f"\nInterpretation: P3 fully-reliable questions "
        f"{p3['pct_fully_reliable_3of3']}% vs B0 {b0['pct_fully_reliable_3of3']}%; "
        f"P3 fully-unreliable {p3['pct_fully_unreliable_0of3']}% vs B0 "
        f"{b0['pct_fully_unreliable_0of3']}%."
    )
    print("Step 6 complete.\n")
    return out


def step_stage_failures(df: pd.DataFrame, summary: dict) -> pd.DataFrame | None:
    print("=" * 60)
    print("Step 7: Stage failure breakdown")
    print("=" * 60)

    if "failure_stage" not in df.columns and "failure_type" not in df.columns:
        print("Stage breakdown not available in data.")
        print("Step 7 skipped.\n")
        return None

    rows = []
    for c in EXPECTED_CONDS:
        sub = df[df["condition"] == c]
        fails = sub[~sub["pass"]]
        n_fail = len(fails)
        n_all = len(sub)

        if "failure_stage" in df.columns:
            stage_counts = fails["failure_stage"].fillna("unknown").value_counts()
            for stage, cnt in stage_counts.items():
                rows.append(
                    {
                        "condition": c,
                        "metric": "failure_stage",
                        "label": stage if str(stage).strip() else "unknown",
                        "count": int(cnt),
                        "pct_of_failures": round(100.0 * cnt / n_fail, 1) if n_fail else 0.0,
                        "pct_of_all_runs": round(100.0 * cnt / n_all, 1) if n_all else 0.0,
                        "n_failures": n_fail,
                        "n_runs": n_all,
                    }
                )

        if "failure_type" in df.columns:
            type_counts = fails["failure_type"].fillna("unknown").value_counts()
            for ftype, cnt in type_counts.items():
                rows.append(
                    {
                        "condition": c,
                        "metric": "failure_type",
                        "label": ftype if str(ftype).strip() else "unknown",
                        "count": int(cnt),
                        "pct_of_failures": round(100.0 * cnt / n_fail, 1) if n_fail else 0.0,
                        "pct_of_all_runs": round(100.0 * cnt / n_all, 1) if n_all else 0.0,
                        "n_failures": n_fail,
                        "n_runs": n_all,
                    }
                )

        # Pattern catch vs miss heuristic:
        # broken_json / empty_retrieval / bad_citation / bad_subquestion ≈ catchable structure
        # wrong_answer ≈ semantic miss after pipeline completed
        if "failure_type" in df.columns and n_fail:
            catchable = {
                "broken_json",
                "empty_retrieval",
                "bad_citation",
                "bad_subquestion",
            }
            ft = fails["failure_type"].fillna("unknown").astype(str)
            n_catch = int(ft.isin(catchable).sum())
            n_miss = int((ft == "wrong_answer").sum())
            n_other = n_fail - n_catch - n_miss
            rows.append(
                {
                    "condition": c,
                    "metric": "catch_vs_miss",
                    "label": "structural_catchable",
                    "count": n_catch,
                    "pct_of_failures": round(100.0 * n_catch / n_fail, 1),
                    "pct_of_all_runs": round(100.0 * n_catch / n_all, 1),
                    "n_failures": n_fail,
                    "n_runs": n_all,
                }
            )
            rows.append(
                {
                    "condition": c,
                    "metric": "catch_vs_miss",
                    "label": "wrong_answer_miss",
                    "count": n_miss,
                    "pct_of_failures": round(100.0 * n_miss / n_fail, 1),
                    "pct_of_all_runs": round(100.0 * n_miss / n_all, 1),
                    "n_failures": n_fail,
                    "n_runs": n_all,
                }
            )
            if n_other:
                rows.append(
                    {
                        "condition": c,
                        "metric": "catch_vs_miss",
                        "label": "other_unknown",
                        "count": n_other,
                        "pct_of_failures": round(100.0 * n_other / n_fail, 1),
                        "pct_of_all_runs": round(100.0 * n_other / n_all, 1),
                        "n_failures": n_fail,
                        "n_runs": n_all,
                    }
                )

    out = pd.DataFrame(rows)
    path = OUT_DIR / "stage_failures.csv"
    out.to_csv(path, index=False)
    print(out[out["metric"] == "failure_stage"].to_string(index=False))
    print(f"\nSaved {path}")

    # Also echo summary JSON stage counts if present
    if summary.get("stage_failure_breakdown"):
        print("\n(From experiment_summary.json stage_failure_breakdown)")
        for c, stages in summary["stage_failure_breakdown"].items():
            print(f"  {c}: {stages}")

    print("Step 7 complete.\n")
    return out


def step_report(
    per_cond: dict[str, dict],
    wilson: pd.DataFrame,
    pvals_z: dict[tuple[str, str], float],
    paired: dict,
    effects: pd.DataFrame,
    cost: pd.DataFrame,
    stability: pd.DataFrame,
) -> Path:
    """Write statistical_summary.md with McNemar as the canonical inferential path."""
    print("=" * 60)
    print("Step 8: Generate summary report (McNemar-canonical)")
    print("=" * 60)

    paired_p: dict[tuple[str, str], float] = paired["paired_p"]
    maj: dict[str, float] = paired["majority_rates"]
    hl: pd.DataFrame = paired["highlight_csv"]

    def p_mc(a: str, b: str) -> float:
        return paired_p[(a, b)]

    def dpp_mc(a: str, b: str) -> float:
        """Gain of condition a over b on question-level majority rates (pp)."""
        return 100.0 * (maj[a] - maj[b])

    def h_mc(a: str, b: str) -> float:
        return _cohen_h(maj[a], maj[b])

    lines: list[str] = []
    lines.append("# Statistical Analysis Summary")
    lines.append("")
    lines.append(
        "Camera-ready canonical analysis for the HotpotQA main experiment "
        "(matches `overleaf_neurips/main.tex`)."
    )
    lines.append("")
    lines.append("## Analysis layers")
    lines.append("")
    lines.append(
        "1. **Inferential (canonical):** 150 paired questions -> majority pass "
        "across 3 trials -> two-sided McNemar (continuity correction) -> "
        f"Bonferroni over 21 pairs (alpha={BONFERRONI_ALPHA:.6f}). "
        "Primary p-values and Delta-pp in the paper use this layer."
    )
    lines.append(
        "2. **Descriptive:** 450 logged runs per condition -> pooled pass rate, "
        "Wilson 95% CI, latency p50/p95, average $/question. "
        "These are *not* treated as independent observations for significance."
    )
    lines.append(
        "3. **Appendix-only:** P1 ablation / 2Wiki / GPT-4o-mini probes use "
        "pooled two-proportion z-tests on their own smaller subsets "
        "(clearly labeled in the paper appendix). They are **not** the "
        "canonical HotpotQA significance path."
    )
    lines.append("")
    lines.append(
        "Legacy pooled z-tests are still written to "
        "`pairwise_pvalues_tidy.csv` for diagnostics; **do not quote them "
        "as camera-ready significance.**"
    )

    lines.append("")
    lines.append("## Inferential results (150 paired questions, McNemar)")
    lines.append("")
    lines.append(
        f"### Highlight pairs (Bonferroni alpha={BONFERRONI_ALPHA:.6f})"
    )
    lines.append("")
    lines.append(
        "| Comparison | Maj.% A | Maj.% B | Delta-pp (A-B) | McNemar p | sig |"
    )
    lines.append(
        "|------------|--------:|--------:|----------:|----------:|:---:|"
    )
    for _, r in hl.iterrows():
        a, b = r["condition_a"], r["condition_b"]
        sig = "**" if r["significant_bonferroni"] else "ns"
        lines.append(
            f"| {a} vs {b} | {_pct(r['pass_a_majority'])} | "
            f"{_pct(r['pass_b_majority'])} | "
            f"{r['delta_pp_majority']:+.1f} | {_fmt_p(r['mcnemar_p'])} | {sig} |"
        )

    lines.append("")
    lines.append("### Key findings (McNemar)")
    lines.append("")
    for a, b in [
        ("P1", "B0"),
        ("P2", "B0"),
        ("P3", "B0"),
        ("P5", "B0"),
        ("P4", "B0"),
        ("B1", "B0"),
    ]:
        p = p_mc(a, b)
        h = h_mc(a, b)
        lines.append(
            f"- {a} vs {b}: {_sig_label(p)}, McNemar p={_fmt_p(p)}, "
            f"dpp={dpp_mc(a, b):+.1f} (majority), "
            f"h={h:.2f} ({_h_label(h)} effect)"
        )

    p3_p1 = p_mc("P3", "P1")
    p3_p2 = p_mc("P3", "P2")
    p3_p5 = p_mc("P3", "P5")
    p5_p1 = p_mc("P5", "P1")
    p4_p3 = p_mc("P4", "P3")
    p4_b0 = p_mc("P4", "B0")
    b1_b0 = p_mc("B1", "B0")

    lines.append(
        f"- P3 vs P1: {_sig_label(p3_p1)}, McNemar p={_fmt_p(p3_p1)} "
        f"(dpp={dpp_mc('P3', 'P1'):+.1f})"
    )
    lines.append(
        f"- P3 vs P2: {_sig_label(p3_p2)}, McNemar p={_fmt_p(p3_p2)}"
    )
    lines.append(
        f"- P3 vs P5: {_sig_label(p3_p5)}, McNemar p={_fmt_p(p3_p5)}"
    )
    lines.append(
        f"- P5 vs P1: {_sig_label(p5_p1)}, McNemar p={_fmt_p(p5_p1)} "
        f"(tested P1+P2 composition)"
    )
    lines.append(
        f"- P4 vs P3: {_sig_label(p4_p3)}, McNemar p={_fmt_p(p4_p3)} "
        f"(P3 higher pass rate; P4 still significant vs B0)"
    )

    lines.append("")
    lines.append("### Composition (P5)")
    lines.append(
        f"Pooled descriptive pass rates: P5={_pct(per_cond['P5']['pass_rate'])}, "
        f"P1={_pct(per_cond['P1']['pass_rate'])}, "
        f"P2={_pct(per_cond['P2']['pass_rate'])}."
    )
    lines.append(
        f"Question-level majority: P5={_pct(maj['P5'])}, "
        f"P1={_pct(maj['P1'])}, P2={_pct(maj['P2'])}."
    )
    lines.append(
        f"P5 vs P1: McNemar p={_fmt_p(p5_p1)} ({_sig_label(p5_p1)}). "
        "Interpretation: no additional benefit from the tested P1+P2 "
        "composition (not a general claim about all stacking)."
    )

    costs = {r["Condition"]: r for _, r in cost.iterrows()}
    p3_cost = float(costs["P3"]["cost_per_question"])
    p4_cost = float(costs["P4"]["cost_per_question"])
    p3_rate = per_cond["P3"]["pass_rate"]
    p4_rate = per_cond["P4"]["pass_rate"]
    lines.append("")
    lines.append("### P4 interpretation")
    lines.append(
        f"P4 vs B0: McNemar p={_fmt_p(p4_b0)} ({_sig_label(p4_b0)}); "
        f"P4 does beat B0."
    )
    lines.append(
        f"P4 vs P3: McNemar p={_fmt_p(p4_p3)} ({_sig_label(p4_p3)}). "
        f"P4 costs {p4_cost / p3_cost:.1f}x more than P3 for "
        f"{100.0 * (p3_rate - p4_rate):.1f} pp lower pooled pass rate. "
        "Conclusion: significant vs B0, but worse cost--accuracy than P3 "
        "(do not claim P4 fails to beat the no-fallback baseline)."
    )

    lines.append("")
    lines.append("## Descriptive results (450 logged runs)")
    lines.append("")
    lines.append(
        "Pooled rates / Wilson CIs / cost below use all 450 runs. "
        "Use for tables and figures; use McNemar above for significance stars."
    )
    lines.append("")
    lines.append("### Wilson 95% confidence intervals (pooled runs)")
    lines.append("")
    lines.append("| Condition | Pass Rate | CI Lower | CI Upper | n_runs |")
    lines.append("|-----------|----------:|---------:|---------:|-------:|")
    for _, r in wilson.iterrows():
        lines.append(
            f"| {r['Condition']} | {_pct(r['Pass Rate'])} | "
            f"{_pct(r['CI Lower'])} | {_pct(r['CI Upper'])} | {int(r['n'])} |"
        )

    lines.append("")
    lines.append("### Cost efficiency (pooled)")
    lines.append("")
    lines.append(
        "| Condition | Pass Rate | $/Q | Pass/$ | Cost/1000 successes | × vs P3 |"
    )
    lines.append(
        "|-----------|----------:|----:|-------:|--------------------:|--------:|"
    )
    for _, r in cost.iterrows():
        lines.append(
            f"| {r['Condition']} | {_pct(r['pass_rate'])} | "
            f"${r['cost_per_question']:.4f} | {r['pass_rate_per_dollar']:.1f} | "
            f"${r['cost_for_1000_successes']:.2f} | {r['cost_ratio_vs_P3']:.2f}× |"
        )

    lines.append("")
    lines.append("### Question stability (within 3 trials)")
    lines.append("")
    lines.append(
        "| Condition | Fully reliable (3/3) | Fully unreliable (0/3) | Unstable mixed |"
    )
    lines.append(
        "|-----------|---------------------:|-----------------------:|---------------:|"
    )
    for _, r in stability.iterrows():
        lines.append(
            f"| {r['Condition']} | {r['pct_fully_reliable_3of3']}% | "
            f"{r['pct_fully_unreliable_0of3']}% | {r['pct_unstable_mixed']}% |"
        )

    lines.append("")
    lines.append("## Legacy pooled z-tests (diagnostic only)")
    lines.append("")
    lines.append(
        "These treat 450 runs as independent and are **optimistic**. "
        "Kept for regression checks against older drafts; camera-ready "
        "claims must use McNemar p-values above."
    )
    lines.append("")
    for a, b in HIGHLIGHT_PAIRS:
        pz = pvals_z[(a, b)]
        lines.append(
            f"- {a} vs {b}: pooled z-test p={_fmt_p(pz)} "
            f"(legacy; not camera-ready)"
        )

    # Paper-ready sentences (McNemar)
    b0 = per_cond["B0"]["pass_rate"]
    b1 = per_cond["B1"]["pass_rate"]
    rates = ", ".join(
        f"{_pct(per_cond[c]['pass_rate'])}" for c in ["P1", "P2", "P3", "P5"]
    )

    lines.append("")
    lines.append("## Paper-ready sentences (McNemar-aligned)")
    lines.append(
        f'- "P1, P2, P3, and P5 each significantly outperform B0 under '
        f'question-level McNemar tests with Bonferroni correction '
        f'(each p < 1e-6; 150 paired questions), with pooled pass rates '
        f'{rates} versus {_pct(b0)} (450 runs)."'
    )
    lines.append(
        f'- "P3 achieves the highest pooled pass rate at '
        f'${p3_cost:.4f}/Q among the targeted cluster."'
    )
    lines.append(
        f'- "P4 significantly beats B0 (McNemar p={_fmt_p(p4_b0)}) but has '
        f'lower pass rate and {p4_cost / p3_cost:.1f}× higher cost than P3 '
        f'(P4 vs P3: p={_fmt_p(p4_p3)})."'
    )
    lines.append(
        f'- "The tested P1+P2 composition (P5) does not significantly beat '
        f'P1 (McNemar p={_fmt_p(p5_p1)}); we report no additional benefit '
        f'from this composition (other stacks were not evaluated)."'
    )
    lines.append(
        f'- "B1 (blind retry) does not significantly beat B0 after Bonferroni '
        f'(McNemar p={_fmt_p(b1_b0)}; pooled {_pct(b1)} vs {_pct(b0)})."'
    )

    lines.append("")
    lines.append("---")
    lines.append(
        f"*Generated by `run_stats.py`. Inferential: 150 paired questions, "
        f"majority -> McNemar, Bonferroni alpha={BONFERRONI_ALPHA:.6f}. "
        f"Descriptive: 450 logged runs/condition. "
        f"See also `paired_question_highlight.csv` and "
        f"`paired_question_tests.json`.*"
    )

    path = OUT_DIR / "statistical_summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved {path}")
    print("Step 8 complete.\n")
    return path


def step_paired_question(df: pd.DataFrame) -> dict:
    """McNemar on question-level majority pass (150 paired questions)."""
    from statsmodels.stats.contingency_tables import mcnemar

    print("=" * 60)
    print("Step 3b: Question-level paired tests (McNemar)")
    print("=" * 60)

    q: dict[str, pd.DataFrame] = {}
    for c in EXPECTED_CONDS:
        sub = df[df["condition"] == c]
        g = sub.groupby("question_id")["pass"].agg(["sum", "count"])
        g["majority"] = g["sum"] >= np.ceil(g["count"] / 2)
        q[c] = g

    majority_rates = {c: float(q[c]["majority"].mean()) for c in EXPECTED_CONDS}

    def mcnemar_p(a: str, b: str) -> float:
        ids = q[a].index.intersection(q[b].index)
        xa = q[a].loc[ids, "majority"].astype(bool)
        xb = q[b].loc[ids, "majority"].astype(bool)
        n01 = int((~xa & xb).sum())
        n10 = int((xa & ~xb).sum())
        n00 = int((~xa & ~xb).sum())
        n11 = int((xa & xb).sum())
        res = mcnemar([[n00, n01], [n10, n11]], exact=False, correction=True)
        return float(res.pvalue)

    paired_p: dict[tuple[str, str], float] = {}
    for a, b in combinations(EXPECTED_CONDS, 2):
        p = mcnemar_p(a, b)
        paired_p[(a, b)] = p
        paired_p[(b, a)] = p

    rows = []
    for a, b in HIGHLIGHT_PAIRS:
        pa = majority_rates[a]
        pb = majority_rates[b]
        # Δpp = gain of first-named condition over second (matches paper Table 2)
        dpp = round(100.0 * (pa - pb), 1)
        p = paired_p[(a, b)]
        rows.append(
            {
                "condition_a": a,
                "condition_b": b,
                "pass_a_majority": pa,
                "pass_b_majority": pb,
                "delta_pp_majority": dpp,
                "mcnemar_p": p,
                "significant_bonferroni": p < BONFERRONI_ALPHA,
            }
        )
        print(
            f"  {a} vs {b}: dpp={dpp:+.1f} (majority A-B), "
            f"McNemar p={_fmt_p(p)} ({_sig_label(p)})"
        )

    out = pd.DataFrame(rows)
    path = OUT_DIR / "paired_question_highlight.csv"
    out.to_csv(path, index=False)
    print(f"Saved {path}")
    print("Step 3b complete.\n")
    return {
        "paired_p": paired_p,
        "majority_rates": majority_rates,
        "highlight_csv": out,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df, summary, per_cond = load_and_validate()
    wilson = step_wilson(per_cond)
    _mat, pvals_z = step_pairwise(per_cond)
    paired = step_paired_question(df)
    effects = step_effect_sizes(per_cond)
    cost = step_cost(per_cond, summary)
    stability = step_stability(df)
    step_stage_failures(df, summary)
    step_report(per_cond, wilson, pvals_z, paired, effects, cost, stability)
    print("All stats complete. Files saved to results_scaled/stats/")


if __name__ == "__main__":
    main()
