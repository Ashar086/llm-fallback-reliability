"""Build results/experiment_summary.json from question_outcomes.csv."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "results" / "question_outcomes.csv"
FALLBACK_COST = {
    "B0": 0.0052,
    "B1": 0.0085,
    "P1": 0.0072,
    "P2": 0.0073,
    "P3": 0.0073,
    "P4": 0.0183,
    "P5": 0.0071,
}


def main() -> None:
    if not CSV.exists():
        raise SystemExit(f"Missing {CSV}; run scripts/build_question_outcomes.py first")
    df = pd.read_csv(CSV)
    df["pass"] = df["pass"].astype(bool)
    blocks = []
    for cond, sub in df.groupby("condition"):
        n = len(sub)
        k = int(sub["pass"].sum())
        blocks.append(
            {
                "condition": cond,
                "pass_rate": k / n if n else 0.0,
                "n_runs": n,
                "n_passed": k,
                "avg_cost_per_question": FALLBACK_COST.get(str(cond), 0.0),
            }
        )
    out = {"source": str(CSV.name), "conditions": blocks}
    path = ROOT / "results" / "experiment_summary.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
