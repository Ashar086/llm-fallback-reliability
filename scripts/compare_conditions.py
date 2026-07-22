from pathlib import Path

from pipeline.aggregate import aggregate, aggregate_p4_breakdown

CONDS = ["B0", "B1", "P1", "P2", "P3", "P4"]
print("log counts:", {c: len(list((Path("logs") / c).glob("*.json"))) for c in CONDS})
print()
print(f"{'Cond':<4} {'Pass%':>7} {'n':>6} {'p50ms':>8} {'p95ms':>8} {'avg_ms':>8} {'cost':>9} {'avg$':>8}")
print("-" * 62)
for c in CONDS:
    s = aggregate(c)
    if s["n_questions"] == 0:
        print(f"{c:<4} {'—':>7} {'0/0':>6} {'—':>8} {'—':>8} {'—':>8} {'—':>9} {'—':>8}")
        continue
    print(
        f"{c:<4} {s['pass_rate']*100:6.1f}% "
        f"{s['n_passed']:2d}/{s['n_questions']:<2d} "
        f"{s['latency_ms']['p50']:8.0f} "
        f"{s['latency_ms']['p95']:8.0f} "
        f"{s['latency_ms']['avg']:8.0f} "
        f"${s['cost_usd']['total']:8.4f} "
        f"${s['cost_usd']['avg']:7.4f}"
    )

p4 = aggregate_p4_breakdown()
if p4["n_questions"]:
    print()
    print("P4 verifier breakdown")
    print(f"  ACCEPT                : {p4['n_accept']}")
    print(f"  REJECT_WITH_CRITIQUE  : {p4['n_reject']}")
    print(f"  PROPOSE_CORRECTION    : {p4['n_propose']}")
    print(f"  second synth rounds   : {p4['n_second_synth_round']}")
    print(f"  avg verifier tokens   : {p4['avg_verifier_tokens']:.0f}")
    print(f"  avg verifier cost     : ${p4['avg_verifier_cost_usd']:.4f}")
    print(f"  total verifier cost   : ${p4['total_verifier_cost_usd']:.4f}")
    print(f"  total verifier tokens : {p4['total_verifier_tokens']}")
