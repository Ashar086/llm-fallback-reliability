"""Question-level McNemar stats for appendix experiments (from logs)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from build_question_outcomes import load_logs
from stats_core import (
    all_pairwise_mcnemar,
    mcnemar_pair,
    question_majority_table,
    wilson_pooled,
)

OUT_DIR = ROOT / "results" / "stats" / "appendix"
ABLATION_TRIALS = [1, 2]
ABLATION_VARIANTS = ["B0", "P1", "P1R", "P1C", "P1S"]
# Display names in paper
DISPLAY = {
    "P1": "P1-full",
    "P1R": "P1R",
    "P1C": "P1C",
    "P1S": "P1S",
    "B0": "B0",
}


def ablation_question_ids(logs_dir: Path) -> set[str]:
    ids: set[str] = set()
    for variant in ("P1R", "P1C", "P1S"):
        for trial in ABLATION_TRIALS:
            tdir = logs_dir / variant / f"trial_{trial}"
            for path in tdir.glob("*.json"):
                if path.name.startswith("_"):
                    continue
                try:
                    rec = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    rec = {"question_id": path.stem}
                ids.add(rec.get("question_id") or path.stem)
    return ids


def build_ablation_frame(logs_dir: Path) -> pd.DataFrame:
    qids = ablation_question_ids(logs_dir)
    rows: list[dict] = []
    for cond in ABLATION_VARIANTS:
        rows.extend(
            load_logs(
                cond,
                ABLATION_TRIALS,
                logs_dir=logs_dir,
                question_ids=qids,
            )
        )
    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("No ablation rows loaded")
    return df


def fmt_p(p: float) -> str:
    if p < 1e-4:
        return f"{p:.2e}"
    return f"{p:.4f}"


def run_ablation(logs_dir: Path) -> dict:
    df = build_ablation_frame(logs_dir)
    n_q = df["question_id"].nunique()
    q = question_majority_table(df)
    # Seven unique unordered pairs shown in the paper table (P1 vs B0 counted once;
    # self-cells are placeholders, not tests).
    comparisons = [
        ("P1-full", "P1", "B0"),
        ("P1-full", "P1", "P1R"),
        ("P1-full", "P1", "P1C"),
        ("P1-full", "P1", "P1S"),
        ("B0", "B0", "P1R"),
        ("B0", "B0", "P1C"),
        ("B0", "B0", "P1S"),
    ]
    n_tests = len(comparisons)  # 7
    bonf = 0.05 / n_tests

    wilson_rows = []
    test_rows = []
    for cond in ABLATION_VARIANTS:
        w = wilson_pooled(df, cond)
        w["display"] = DISPLAY.get(cond, cond)
        w["n_questions"] = n_q
        wilson_rows.append(w)

    for label_a, key_a, key_b in comparisons:
        m = mcnemar_pair(q[key_a], q[key_b])
        test_rows.append(
            {
                "comparison": f"{label_a} vs {DISPLAY.get(key_b, key_b)}",
                "condition_a": key_a,
                "condition_b": key_b,
                "n_questions": m["n_questions"],
                "delta_pp_majority": m["delta_pp_majority"],
                "mcnemar_p": m["mcnemar_p"],
                "mcnemar_p_bonferroni_alpha": bonf,
                "significant_bonferroni": m["mcnemar_p"] < bonf,
                "test": (
                    "McNemar; pass if sum >= ceil(n_trials/2) "
                    "(2 trials: >=1 of 2, so 1-1 ties count as pass)"
                ),
            }
        )

    payload = {
        "experiment": "p1_check_ablation",
        "n_questions": n_q,
        "trials_per_question": 2,
        "tie_rule": (
            "pass if n_pass >= ceil(n_trials/2); with 2 trials a 1-1 split is a pass"
        ),
        "bonferroni_family": (
            "7 unique pairs: P1 vs B0; {P1R,P1C,P1S} vs P1; {P1R,P1C,P1S} vs B0"
        ),
        "note": (
            "Separate 50-question Hotpot subset (not the main 150-question set). "
            "Pass if n_pass >= ceil(n_trials/2); with 2 trials a 1-1 split counts "
            f"as pass. McNemar on 50 paired questions; Bonferroni alpha=0.05/{n_tests} "
            f"(â‰ˆ{bonf:.5f}) over the seven unique table comparisons."
        ),
        "wilson_pooled": wilson_rows,
        "comparisons": test_rows,
    }
    return payload


def run_from_csv(csv_path: Path, name: str, bonferroni_pairs: int) -> dict:
    df = pd.read_csv(csv_path)
    df["pass"] = df["pass"].astype(bool)
    n_q = df["question_id"].nunique()
    q = question_majority_table(df)
    conds = sorted(df["condition"].unique())
    bonf = 0.05 / bonferroni_pairs if bonferroni_pairs else None
    wilson_rows = [wilson_pooled(df, c) for c in conds]
    comp = all_pairwise_mcnemar(
        q, conds, bonferroni_pairs=bonferroni_pairs if bonferroni_pairs else None
    )
    return {
        "experiment": name,
        "source_csv": str(csv_path),
        "n_questions": int(n_q),
        "wilson_pooled": wilson_rows,
        "comparisons": comp.to_dict(orient="records"),
        "bonferroni_alpha": bonf,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--logs-dir", type=Path, default=config.LOGS_DIR)
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    abl = run_ablation(args.logs_dir)
    abl_csv = OUT_DIR / "p1_ablation_outcomes.csv"
    build_ablation_frame(args.logs_dir).to_csv(abl_csv, index=False)
    print(f"Wrote {abl_csv}")
    out_json = OUT_DIR / "p1_ablation_paired.json"
    out_json.write_text(json.dumps(abl, indent=2), encoding="utf-8")

    # Human-readable summary for paper editing
    lines = [
        "# P1 ablation (paired McNemar)",
        "",
        abl["note"],
        "",
        f"**n_questions={abl['n_questions']}**, trials=2, pooled runs per variant=100.",
        "",
        "## Pooled pass % (Wilson 95% CI on 100 runs)",
        "",
    ]
    for w in abl["wilson_pooled"]:
        pct = 100.0 * w["pass_rate_pooled"]
        lo, hi = 100.0 * w["wilson_lo"], 100.0 * w["wilson_hi"]
        lines.append(
            f"- {w['display']}: {pct:.1f}% [{lo:.1f}, {hi:.1f}] "
            f"({w['n_pass']}/{w['n_runs']} runs)"
        )
    lines.append("")
    lines.append("## McNemar comparisons (question-level majority)")
    lines.append("")
    for t in abl["comparisons"]:
        sig = "sig" if t["significant_bonferroni"] else "ns"
        lines.append(
            f"- {t['comparison']}: Î”pp={t['delta_pp_majority']:+.1f}, "
            f"p={fmt_p(t['mcnemar_p'])} ({sig} Bonferroni)"
        )

    md_path = OUT_DIR / "p1_ablation_paired.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_json}")
    print(f"Wrote {md_path}")

    probe_dir = ROOT / "results" / "appendix_probes"
    for label, fname, n_bonf in [
        ("2wiki", "2wiki_outcomes.csv", 6),
        ("gpt4o_mini", "gpt4o_mini_outcomes.csv", 3),
    ]:
        csv_path = probe_dir / fname
        if not csv_path.exists():
            print(f"Skip {label}: missing {csv_path}")
            continue
        payload = run_from_csv(csv_path, label, n_bonf)
        out = OUT_DIR / f"{label}_paired.json"
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
