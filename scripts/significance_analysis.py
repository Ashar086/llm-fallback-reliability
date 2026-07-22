"""Pooled two-proportion / Fisher tests + multi-trial side-by-side report."""

from __future__ import annotations

import math
from itertools import combinations
from pathlib import Path
from typing import Any

from pipeline.aggregate import aggregate, load_condition_logs, percentile

CONDS = ["B0", "B1", "P1", "P2", "P3", "P4"]
# Targeted 3rd trial was run for these only (P4 stays at 2 trials).
TRIAL3_CONDS = {"B0", "B1", "P1", "P2", "P3"}
ROOT = Path(__file__).resolve().parents[1]


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def two_proportion_z(s1: int, n1: int, s2: int, n2: int) -> dict[str, float]:
    if n1 == 0 or n2 == 0:
        return {"z": 0.0, "p": 1.0, "p1": 0.0, "p2": 0.0, "diff": 0.0}
    p1 = s1 / n1
    p2 = s2 / n2
    p_pool = (s1 + s2) / (n1 + n2)
    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2))
    if se == 0.0:
        z, p = 0.0, 1.0
    else:
        z = (p1 - p2) / se
        p = 2.0 * (1.0 - _norm_cdf(abs(z)))
    return {"z": z, "p": p, "p1": p1, "p2": p2, "diff": p1 - p2}


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    if min(a, b, c, d) < 0:
        return 1.0

    def log_fact(n: int) -> float:
        return sum(math.log(i) for i in range(1, n + 1)) if n > 0 else 0.0

    def log_hyper(aa: int, bb: int, cc: int, dd: int) -> float:
        n = aa + bb + cc + dd
        return (
            log_fact(aa + bb)
            + log_fact(cc + dd)
            + log_fact(aa + cc)
            + log_fact(bb + dd)
            - log_fact(aa)
            - log_fact(bb)
            - log_fact(cc)
            - log_fact(dd)
            - log_fact(n)
        )

    observed = math.exp(log_hyper(a, b, c, d))
    row1 = a + b
    col1 = a + c
    n = a + b + c + d
    lo = max(0, col1 - (n - row1))
    hi = min(row1, col1)
    p_two = 0.0
    for aa in range(lo, hi + 1):
        bb = row1 - aa
        cc = col1 - aa
        dd = n - aa - bb - cc
        if min(bb, cc, dd) < 0:
            continue
        prob = math.exp(log_hyper(aa, bb, cc, dd))
        if prob <= observed + 1e-15:
            p_two += prob
    return min(1.0, p_two)


def available_trials(condition: str) -> list[int]:
    trials = []
    for t in (1, 2, 3, 4):
        n = len(load_condition_logs(condition, trial=t))
        if n > 0:
            trials.append(t)
    return trials


def trial_stats(condition: str, trial: int) -> dict[str, Any]:
    return aggregate(condition, trial=trial)


def pooled_counts(condition: str) -> tuple[int, int]:
    """Pool all available trials for this condition."""
    s = 0
    n = 0
    for t in available_trials(condition):
        recs = load_condition_logs(condition, trial=t)
        n += len(recs)
        s += sum(1 for r in recs if r.get("final", {}).get("pass"))
    return s, n


def pooled_latency_cost(condition: str) -> dict[str, Any]:
    lats: list[float] = []
    costs: list[float] = []
    for t in available_trials(condition):
        for r in load_condition_logs(condition, trial=t):
            fin = r.get("final") or {}
            lats.append(float(fin.get("total_latency_ms") or 0))
            costs.append(float(fin.get("estimated_cost_usd") or 0))
    n = len(lats) or 1
    return {
        "n": len(lats),
        "n_trials": len(available_trials(condition)),
        "lat_avg": sum(lats) / n if lats else 0.0,
        "lat_p50": percentile(lats, 50) if lats else 0.0,
        "lat_p95": percentile(lats, 95) if lats else 0.0,
        "cost_total": sum(costs),
        "cost_avg": sum(costs) / n if lats else 0.0,
    }


def fmt_p(p: float) -> str:
    if p < 0.001:
        return f"{p:.3e}"
    return f"{p:.4f}"


def sig_stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def _est_cost(condition: str) -> float:
    return float(trial_stats(condition, 1)["cost_usd"]["total"])


def build_markdown() -> str:
    lines: list[str] = []
    has_t3 = any(
        len(load_condition_logs(c, trial=3)) == 40 for c in TRIAL3_CONDS
    )
    title = (
        "# Statistical Validity Pass (Trials 1–3, targeted)"
        if has_t3
        else "# Statistical Validity Pass (Trials 1–2)"
    )
    lines.append(title)
    lines.append("")
    if has_t3:
        lines.append(
            "Phase 3 Steps 3.1–3.2 plus a **targeted Trial 3** for "
            "B0, B1, P1, P2, P3 (the edge-band comparisons from the n=80 "
            "screen). P4 remains at 2 trials. Temperature=0. Pass-rate "
            "inference uses pooled question outcomes (n=120 for "
            "B0/B1/P1/P2/P3; n=80 for P4). Latency/cost shown per trial "
            "plus the simple mean across available trials."
        )
    else:
        lines.append(
            "Phase 3 Steps 3.1–3.2. Temperature=0; two independent full runs "
            "of the same 40-question set. Pass-rate inference uses pooled "
            "question outcomes (n=80 per condition)."
        )
    lines.append("")

    # --- Side by side ---
    lines.append("## 1. Per-trial results (side by side)")
    lines.append("")
    if has_t3:
        lines.append(
            "| Cond | T1 Pass% | T2 Pass% | T3 Pass% | "
            "T1 cost | T2 cost | T3 cost | Avg Pass% | Avg cost |"
        )
        lines.append(
            "|------|---------:|---------:|---------:|"
            "--------:|--------:|--------:|----------:|---------:|"
        )
    else:
        lines.append(
            "| Cond | T1 Pass% | T2 Pass% | T1 cost | T2 cost | "
            "Avg Pass% | Avg cost |"
        )
        lines.append(
            "|------|---------:|---------:|--------:|--------:|"
            "----------:|---------:|"
        )

    for c in CONDS:
        trials = available_trials(c)
        stats = {t: trial_stats(c, t) for t in trials}
        rates = [stats[t]["pass_rate"] for t in trials]
        costs = [stats[t]["cost_usd"]["total"] for t in trials]
        avg_pass = sum(rates) / len(rates)
        avg_cost = sum(costs) / len(costs)

        def cell(t: int) -> str:
            if t not in stats:
                return "—"
            s = stats[t]
            return f"{s['pass_rate']*100:.1f}% ({s['n_passed']}/{s['n_questions']})"

        def cost_cell(t: int) -> str:
            if t not in stats:
                return "—"
            return f"${stats[t]['cost_usd']['total']:.4f}"

        if has_t3:
            lines.append(
                f"| {c} | {cell(1)} | {cell(2)} | {cell(3)} | "
                f"{cost_cell(1)} | {cost_cell(2)} | {cost_cell(3)} | "
                f"{avg_pass*100:.1f}% | ${avg_cost:.4f} |"
            )
        else:
            lines.append(
                f"| {c} | {cell(1)} | {cell(2)} | "
                f"{cost_cell(1)} | {cost_cell(2)} | "
                f"{avg_pass*100:.1f}% | ${avg_cost:.4f} |"
            )
    lines.append("")

    # Latency detail table
    lines.append("### Latency (p50 / p95) by trial")
    lines.append("")
    lines.append(
        "| Cond | T1 p50 | T2 p50 | T3 p50 | T1 p95 | T2 p95 | T3 p95 |"
    )
    lines.append(
        "|------|-------:|-------:|-------:|-------:|-------:|-------:|"
    )
    for c in CONDS:
        stats = {t: trial_stats(c, t) for t in available_trials(c)}

        def lat(t: int, key: str) -> str:
            if t not in stats:
                return "—"
            return f"{stats[t]['latency_ms'][key]:.0f}"

        lines.append(
            f"| {c} | {lat(1,'p50')} | {lat(2,'p50')} | {lat(3,'p50')} | "
            f"{lat(1,'p95')} | {lat(2,'p95')} | {lat(3,'p95')} |"
        )
    lines.append("")

    # --- Pooled ---
    lines.append("## 2. Pooled pass-rate results")
    lines.append("")
    lines.append(
        "| Cond | Trials | n | Pass | Fail | Pass% | lat p50 | lat p95 | "
        "cost total | cost avg/Q |"
    )
    lines.append(
        "|------|-------:|--:|-----:|-----:|------:|--------:|--------:|"
        "-----------:|-----------:|"
    )
    pooled: dict[str, tuple[int, int]] = {}
    for c in CONDS:
        s, n = pooled_counts(c)
        pooled[c] = (s, n)
        pc = pooled_latency_cost(c)
        lines.append(
            f"| {c} | {pc['n_trials']} | {n} | {s} | {n - s} | "
            f"{100.0 * s / n:.1f}% | {pc['lat_p50']:.0f} | {pc['lat_p95']:.0f} | "
            f"${pc['cost_total']:.4f} | ${pc['cost_avg']:.4f} |"
        )
    lines.append("")
    lines.append(
        "Note: pairwise tests below use each condition's own pooled n "
        "(unequal n is fine for two-proportion z / Fisher)."
    )
    lines.append("")

    focus_pairs = [
        ("P1", "B0"),
        ("P2", "B0"),
        ("P3", "B0"),
        ("P4", "B0"),
        ("B1", "B0"),
        ("P1", "B1"),
        ("P3", "B1"),
        ("P1", "P2"),
        ("P1", "P3"),
        ("P2", "P3"),
        ("P1", "P4"),
        ("P2", "P4"),
        ("P3", "P4"),
    ]

    lines.append("### Pairwise pass-rate tests (pooled)")
    lines.append("")
    lines.append(
        "| A vs B | A n | B n | A pass% | B pass% | Δpp | z | p(z) | "
        "p(Fisher) | sig |"
    )
    lines.append(
        "|--------|----:|----:|--------:|--------:|----:|--:|------:|"
        "----------:|-----|"
    )

    edge_flags: list[dict[str, Any]] = []

    def compare(a: str, b: str) -> dict[str, Any]:
        sa, na = pooled[a]
        sb, nb = pooled[b]
        zres = two_proportion_z(sa, na, sb, nb)
        fisher_p = fisher_exact(sa, na - sa, sb, nb - sb)
        return {
            "a": a,
            "b": b,
            "sa": sa,
            "na": na,
            "sb": sb,
            "nb": nb,
            **zres,
            "fisher_p": fisher_p,
            "stars": sig_stars(min(zres["p"], fisher_p)),
        }

    for a, b in focus_pairs:
        r = compare(a, b)
        lines.append(
            f"| {a} vs {b} | {r['na']} | {r['nb']} | "
            f"{r['p1']*100:.1f}% | {r['p2']*100:.1f}% | "
            f"{r['diff']*100:+.1f} | {r['z']:.3f} | {fmt_p(r['p'])} | "
            f"{fmt_p(r['fisher_p'])} | {r['stars']} |"
        )

    for a, b in combinations(CONDS, 2):
        r = compare(a, b)
        for pname, pv in (("z", r["p"]), ("Fisher", r["fisher_p"])):
            if 0.03 <= pv <= 0.10:
                edge_flags.append({**r, "which_p": pname, "p_edge": pv})
                break

    lines.append("")
    lines.append("Full pairwise matrix (z-test p-values only):")
    lines.append("")
    lines.append("|  | " + " | ".join(CONDS) + " |")
    lines.append("|--" + "|------" * len(CONDS) + "|")
    for a in CONDS:
        cells = []
        for b in CONDS:
            if a == b:
                cells.append("—")
            else:
                cells.append(fmt_p(compare(a, b)["p"]))
        lines.append(f"| {a} | " + " | ".join(cells) + " |")
    lines.append("")

    # --- Edge / further trials ---
    lines.append("## 3. Remaining edge-band comparisons")
    lines.append("")
    if has_t3:
        lines.append(
            "After the targeted Trial 3, any pair still in p ∈ [0.03, 0.10] "
            "is listed below. Pairs that moved clearly in/out of significance "
            "are discussed in §4."
        )
        lines.append("")
    if not edge_flags:
        lines.append(
            "No pairwise comparison remains in the edge band "
            "(p ∈ [0.03, 0.10]). No further trial is recommended on "
            "significance grounds."
        )
    else:
        lines.append("| Comparison | Δpp | p (edge test) | Note |")
        lines.append("|------------|----:|--------------:|------|")
        seen: set[tuple[str, str]] = set()
        for e in edge_flags:
            key = tuple(sorted([e["a"], e["b"]]))
            if key in seen:
                continue
            seen.add(key)
            if e["p1"] >= e["p2"]:
                left, right, dpp = e["a"], e["b"], e["diff"]
            else:
                left, right, dpp = e["b"], e["a"], -e["diff"]
            note = ""
            if (e["p"] < 0.05) != (e["fisher_p"] < 0.05):
                note = "z/Fisher disagree at α=0.05"
            lines.append(
                f"| {left} vs {right} | {dpp*100:+.1f} | "
                f"{fmt_p(e['p_edge'])} ({e['which_p']}) | {note} |"
            )
    lines.append("")

    # --- Summary ---
    lines.append("## 4. Plain-language summary for the paper")
    lines.append("")
    b0_s, b0_n = pooled["B0"]
    b0_rate = b0_s / b0_n

    defensible = []
    borderline = []
    indistinct = []
    for c in ["B1", "P1", "P2", "P3", "P4"]:
        r = compare(c, "B0")
        z_sig = r["p"] < 0.05
        f_sig = r["fisher_p"] < 0.05
        n_note = f"n={r['na']} vs {r['nb']}"
        if z_sig and f_sig and r["diff"] > 0:
            defensible.append(
                f"**{c} > B0** ({r['p1']*100:.1f}% vs {b0_rate*100:.1f}%, "
                f"Δ={r['diff']*100:+.1f} pp, {n_note}, "
                f"z p={fmt_p(r['p'])}, Fisher p={fmt_p(r['fisher_p'])})"
            )
        elif (z_sig or f_sig) and r["diff"] > 0:
            borderline.append(
                f"**{c} vs B0** borderline — tests disagree "
                f"({r['p1']*100:.1f}% vs {b0_rate*100:.1f}%, "
                f"Δ={r['diff']*100:+.1f} pp, {n_note}, "
                f"z p={fmt_p(r['p'])}, Fisher p={fmt_p(r['fisher_p'])})"
            )
        else:
            indistinct.append(
                f"**{c} vs B0** not significant at α=0.05 "
                f"({r['p1']*100:.1f}% vs {b0_rate*100:.1f}%, "
                f"{n_note}, Fisher p={fmt_p(r['fisher_p'])})"
            )

    cluster_notes = []
    for a, b in [("P1", "P2"), ("P1", "P3"), ("P2", "P3")]:
        r = compare(a, b)
        pmin = min(r["p"], r["fisher_p"])
        if pmin >= 0.05:
            cluster_notes.append(
                f"{a} vs {b}: indistinguishable "
                f"(Δ={r['diff']*100:+.1f} pp, Fisher p={fmt_p(r['fisher_p'])})"
            )
        else:
            cluster_notes.append(
                f"{a} vs {b}: distinguishable "
                f"(Δ={r['diff']*100:+.1f} pp, Fisher p={fmt_p(r['fisher_p'])})"
            )

    # P3 vs B1 was an edge pair
    p3b1 = compare("P3", "B1")
    p3b1_note = (
        f"P3 vs B1: {p3b1['p1']*100:.1f}% vs {p3b1['p2']*100:.1f}% "
        f"(Δ={p3b1['diff']*100:+.1f} pp, z p={fmt_p(p3b1['p'])}, "
        f"Fisher p={fmt_p(p3b1['fisher_p'])}, {sig_stars(min(p3b1['p'], p3b1['fisher_p']))})"
    )

    lines.append("### Defensible findings")
    lines.append("")
    if defensible:
        for d in defensible:
            lines.append(f"- {d}")
    else:
        lines.append("- No pattern clearly beats B0 on both tests at α=0.05.")
    lines.append("")
    if borderline:
        lines.append("### Borderline (treat cautiously)")
        lines.append("")
        for d in borderline:
            lines.append(f"- {d}")
        lines.append("")
    lines.append("### Statistically indistinguishable vs B0")
    lines.append("")
    for d in indistinct:
        lines.append(f"- {d}")
    lines.append("")
    lines.append("### P1 / P2 / P3 cluster")
    lines.append("")
    for note in cluster_notes:
        lines.append(f"- {note}")
    lines.append(f"- {p3b1_note}")
    lines.append("")
    lines.append("### Cost / latency (descriptive only)")
    lines.append("")
    lines.append(
        "Report per-trial values and their mean; do not over-claim cost "
        "significance from a handful of trial totals. Qualitatively: P4 "
        "remains the expensive outlier; B1 has high p95 from blind retries; "
        "P1–P3 cluster on cost."
    )
    lines.append("")
    lines.append("### Further trials?")
    lines.append("")
    if edge_flags:
        pairs = sorted({tuple(sorted([e["a"], e["b"]])) for e in edge_flags})
        lines.append(
            "Some pairs remain near the decision boundary "
            f"({', '.join(f'{a} vs {b}' for a, b in pairs)}). "
            "A further trial is optional and only worth it if that specific "
            "claim is central to the paper."
        )
    else:
        lines.append(
            "No remaining edge-band pairs after the targeted Trial 3. "
            "Stop here for pass-rate claims."
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "*Generated by `scripts/significance_analysis.py`. "
        "α=0.05 two-sided; no multiple-comparison correction applied "
        "(exploratory pairwise screen — note this in the paper).*"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    missing = []
    for c in CONDS:
        for t in (1, 2):
            n = len(load_condition_logs(c, trial=t))
            if n != 40:
                missing.append(f"{c}/trial_{t}: {n}/40")
    for c in TRIAL3_CONDS:
        n = len(load_condition_logs(c, trial=3))
        if n not in (0, 40):
            missing.append(f"{c}/trial_3: {n}/40 (partial)")
    if missing:
        print("WARNING: incomplete trials:")
        for m in missing:
            print(" ", m)
    md = build_markdown()
    out = ROOT / "significance_results.md"
    out.write_text(md, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
