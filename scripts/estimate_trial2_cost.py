"""Estimate Trial-2 API cost from Trial-1 log totals."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONDS = ["B0", "B1", "P1", "P2", "P3", "P4"]


def main() -> None:
    print(f"{'Cond':<4} {'n':>3} {'pass':>5} {'cost_usd':>10} {'tokens':>8} {'avg$/q':>10}")
    print("-" * 48)
    total = 0.0
    for c in CONDS:
        d = ROOT / "logs" / c
        files = [p for p in d.glob("*.json") if p.parent == d]
        cost = 0.0
        toks = 0
        npass = 0
        for p in files:
            rec = json.loads(p.read_text(encoding="utf-8"))
            fin = rec.get("final") or {}
            cost += float(fin.get("estimated_cost_usd") or 0.0)
            tt = fin.get("total_tokens") or {}
            toks += int(tt.get("total") or 0)
            if fin.get("pass"):
                npass += 1
        total += cost
        avg = cost / max(len(files), 1)
        print(
            f"{c:<4} {len(files):3d} {npass:5d} ${cost:9.4f} {toks:8d} ${avg:9.4f}"
        )

    print("-" * 48)
    print(f"Trial-1 total cost (all 6 conditions): ${total:.4f}")
    print(f"Estimated Trial-2 cost (same usage):   ${total:.4f}")
    print(f"Conservative +15%:                     ${total * 1.15:.4f}")
    print(f"Conservative +25%:                     ${total * 1.25:.4f}")
    print()
    lo, hi = 2.0, 3.5
    in_band = lo <= total <= hi
    print(f"Target band for Trial-2: ${lo:.1f}–${hi:.1f}")
    print(f"Within band? {in_band} (point estimate ${total:.2f})")
    if total < lo:
        print("NOTE: below band — cheaper than expected; safe to proceed.")
    elif total > hi:
        print("NOTE: ABOVE band — stop and discuss before spending.")
    else:
        print("NOTE: within band — ready to proceed on your go-ahead.")


if __name__ == "__main__":
    main()
