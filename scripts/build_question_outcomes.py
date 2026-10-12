"""Build question_outcomes.csv from logs/{condition}/trial_{n}/*.json."""

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

MAIN_CONDS = ["B0", "B1", "P1", "P2", "P3", "P4", "P5"]
MAIN_TRIALS = [1, 2, 3]


def load_logs(
    condition: str,
    trials: list[int],
    *,
    logs_dir: Path | None = None,
    question_ids: set[str] | None = None,
) -> list[dict]:
    base = logs_dir or config.LOGS_DIR
    rows: list[dict] = []
    for trial in trials:
        tdir = base / condition / f"trial_{trial}"
        if not tdir.is_dir():
            continue
        for path in sorted(tdir.glob("*.json")):
            if path.name.startswith("_"):
                continue
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            qid = rec.get("question_id") or path.stem
            if question_ids is not None and qid not in question_ids:
                continue
            passed = bool((rec.get("final") or {}).get("pass"))
            rows.append(
                {
                    "condition": condition,
                    "question_id": qid,
                    "trial": trial,
                    "pass": passed,
                }
            )
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results_scaled" / "question_outcomes.csv",
    )
    p.add_argument("--logs-dir", type=Path, default=config.LOGS_DIR)
    args = p.parse_args()

    rows: list[dict] = []
    for c in MAIN_CONDS:
        rows.extend(load_logs(c, MAIN_TRIALS, logs_dir=args.logs_dir))

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit(f"No log rows found under {args.logs_dir}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote {args.output} ({len(df)} rows, {df['condition'].nunique()} conditions)")


if __name__ == "__main__":
    main()
