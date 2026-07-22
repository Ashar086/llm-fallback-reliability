"""Aggregate summary stats from /logs/{condition}/*.json for paper reporting."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

# Allow `python -m pipeline.aggregate` and `python pipeline/aggregate.py`
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile; p in [0, 100]."""
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    k = (len(xs) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(xs[int(k)])
    return float(xs[f] * (c - k) + xs[c] * (k - f))


def load_condition_logs(
    condition: str,
    logs_dir: Path | None = None,
    *,
    trial: int | None = None,
) -> list[dict[str, Any]]:
    """Load per-question logs.

    Layout:
      - legacy: /logs/{condition}/*.json
      - trials: /logs/{condition}/trial_{n}/*.json
    If trial is set, load that trial only. If None and trial_* dirs exist,
    load only direct *.json under condition (legacy), not nested trials.
    """
    base = (logs_dir or config.LOGS_DIR) / condition
    if trial is not None:
        base = base / f"trial_{trial}"
    if not base.exists():
        return []
    records = []
    for path in sorted(base.glob("*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def print_summary(stats: dict[str, Any]) -> None:
    print("=" * 60)
    print(f"AGGREGATE SUMMARY ({stats['condition']})")
    print(f"  n questions : {stats['n_questions']}")
    print(f"  n passed    : {stats['n_passed']}")
    print(f"  n failed    : {stats['n_failed']}")
    print(f"  pass rate   : {stats['pass_rate'] * 100:.1f}%")
    lat = stats["latency_ms"]
    print(f"  latency avg : {lat['avg']:.0f} ms")
    print(f"  latency p50 : {lat['p50']:.0f} ms")
    print(f"  latency p95 : {lat['p95']:.0f} ms")
    cost = stats["cost_usd"]
    print(f"  cost total  : ${cost['total']:.4f}")
    print(f"  cost avg    : ${cost['avg']:.4f}")
    tok = stats["tokens"]
    print(f"  tokens total: {tok['total']}")
    print(f"  tokens avg  : {tok['avg']:.0f}")
    # Optional P4 verification-overhead line (does not change core table fields)
    if stats.get("condition") == "P4" or stats.get("p4"):
        p4 = stats.get("p4") or {}
        if p4:
            print(
                f"  verify overhead avg: ${p4.get('avg_verifier_cost_usd', 0):.4f} "
                f"/ {p4.get('avg_verifier_tokens', 0):.0f} tokens "
                f"(ACCEPT={p4.get('n_accept', 0)}, "
                f"REJECT={p4.get('n_reject', 0)}, "
                f"PROPOSE={p4.get('n_propose', 0)})"
            )
    print("=" * 60)


def aggregate_p4_breakdown(
    logs_dir: Path | None = None, *, trial: int | None = None
) -> dict[str, Any]:
    """Optional P4-only stats: outcome counts + avg verifier token/cost overhead."""
    records = load_condition_logs("P4", logs_dir, trial=trial)
    n = len(records)
    counts = {"ACCEPT": 0, "REJECT_WITH_CRITIQUE": 0, "PROPOSE_CORRECTION": 0, "OTHER": 0}
    v_costs = []
    v_tokens = []
    n_second = 0
    for r in records:
        fin = r.get("final") or {}
        outcome = fin.get("verifier_outcome") or "OTHER"
        if outcome not in counts:
            # Prefer last verifier stage if final missing
            for s in reversed(r.get("stages") or []):
                if s.get("verifier_outcome"):
                    outcome = s["verifier_outcome"]
                    break
            if outcome not in counts:
                counts["OTHER"] += 1
            else:
                counts[outcome] += 1
        else:
            counts[outcome] += 1
        vt = fin.get("verifier_tokens") or {}
        v_tokens.append(int(vt.get("total") or 0))
        v_costs.append(float(fin.get("verifier_cost_usd") or 0.0))
        if fin.get("second_synth_round"):
            n_second += 1
    return {
        "n_questions": n,
        "n_accept": counts["ACCEPT"],
        "n_reject": counts["REJECT_WITH_CRITIQUE"],
        "n_propose": counts["PROPOSE_CORRECTION"],
        "n_other": counts["OTHER"],
        "n_second_synth_round": n_second,
        "avg_verifier_tokens": (sum(v_tokens) / n) if n else 0.0,
        "avg_verifier_cost_usd": (sum(v_costs) / n) if n else 0.0,
        "total_verifier_cost_usd": sum(v_costs),
        "total_verifier_tokens": sum(v_tokens),
    }


def aggregate(
    condition: str, logs_dir: Path | None = None, *, trial: int | None = None
) -> dict[str, Any]:
    records = load_condition_logs(condition, logs_dir, trial=trial)
    n = len(records)
    if n == 0:
        out = {
            "condition": condition,
            "n_questions": 0,
            "n_passed": 0,
            "n_failed": 0,
            "pass_rate": 0.0,
            "latency_ms": {"avg": 0.0, "p50": 0.0, "p95": 0.0},
            "cost_usd": {"total": 0.0, "avg": 0.0},
            "tokens": {"total": 0, "avg": 0.0},
        }
        if condition == "P4":
            out["p4"] = aggregate_p4_breakdown(logs_dir, trial=trial)
        return out

    n_passed = sum(1 for r in records if r.get("final", {}).get("pass"))
    n_failed = n - n_passed
    latencies = [float(r["final"]["total_latency_ms"]) for r in records]
    costs = [float(r["final"]["estimated_cost_usd"]) for r in records]
    tokens = [int(r["final"]["total_tokens"]["total"]) for r in records]

    out = {
        "condition": condition,
        "n_questions": n,
        "n_passed": n_passed,
        "n_failed": n_failed,
        "pass_rate": n_passed / n,
        "latency_ms": {
            "avg": sum(latencies) / n,
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
        },
        "cost_usd": {
            "total": sum(costs),
            "avg": sum(costs) / n,
        },
        "tokens": {
            "total": sum(tokens),
            "avg": sum(tokens) / n,
        },
    }
    if condition == "P4":
        out["p4"] = aggregate_p4_breakdown(logs_dir, trial=trial)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate logs for a condition folder")
    parser.add_argument("condition", nargs="?", default="B0", help="Condition name (default: B0)")
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=None,
        help="Override logs root (default: config.LOGS_DIR)",
    )
    parser.add_argument("--trial", type=int, default=None, help="Aggregate a specific trial_N")
    args = parser.parse_args()
    stats = aggregate(args.condition, args.logs_dir, trial=args.trial)
    print_summary(stats)


if __name__ == "__main__":
    main()
