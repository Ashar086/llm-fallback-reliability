# Statistical Validity Pass (Trials 1–3, targeted)

Phase 3 Steps 3.1–3.2 plus a **targeted Trial 3** for B0, B1, P1, P2, P3 (the edge-band comparisons from the n=80 screen). P4 remains at 2 trials. Temperature=0. Pass-rate inference uses pooled question outcomes (n=120 for B0/B1/P1/P2/P3; n=80 for P4). Latency/cost shown per trial plus the simple mean across available trials.

## 1. Per-trial results (side by side)

| Cond | T1 Pass% | T2 Pass% | T3 Pass% | T1 cost | T2 cost | T3 cost | Avg Pass% | Avg cost |
|------|---------:|---------:|---------:|--------:|--------:|--------:|----------:|---------:|
| B0 | 57.5% (23/40) | 62.5% (25/40) | 60.0% (24/40) | $0.2312 | $0.2514 | $0.2405 | 60.0% | $0.2410 |
| B1 | 62.5% (25/40) | 67.5% (27/40) | 62.5% (25/40) | $0.4231 | $0.4524 | $0.4228 | 64.2% | $0.4327 |
| P1 | 77.5% (31/40) | 75.0% (30/40) | 75.0% (30/40) | $0.3017 | $0.2945 | $0.2992 | 75.8% | $0.2985 |
| P2 | 75.0% (30/40) | 75.0% (30/40) | 77.5% (31/40) | $0.2999 | $0.2956 | $0.3062 | 75.8% | $0.3006 |
| P3 | 77.5% (31/40) | 80.0% (32/40) | 77.5% (31/40) | $0.2988 | $0.2988 | $0.3020 | 78.3% | $0.2999 |
| P4 | 67.5% (27/40) | 72.5% (29/40) | — | $0.6417 | $0.6702 | — | 70.0% | $0.6560 |

### Latency (p50 / p95) by trial

| Cond | T1 p50 | T2 p50 | T3 p50 | T1 p95 | T2 p95 | T3 p95 |
|------|-------:|-------:|-------:|-------:|-------:|-------:|
| B0 | 6119 | 6512 | 7027 | 8732 | 9697 | 10608 |
| B1 | 6681 | 7376 | 7189 | 32728 | 36602 | 35948 |
| P1 | 6991 | 7305 | 6999 | 9353 | 10948 | 9602 |
| P2 | 6841 | 6808 | 7013 | 9559 | 10630 | 8730 |
| P3 | 7257 | 7197 | 7121 | 8716 | 9941 | 11308 |
| P4 | 11460 | 9616 | — | 30708 | 28845 | — |

## 2. Pooled pass-rate results

| Cond | Trials | n | Pass | Fail | Pass% | lat p50 | lat p95 | cost total | cost avg/Q |
|------|-------:|--:|-----:|-----:|------:|--------:|--------:|-----------:|-----------:|
| B0 | 3 | 120 | 72 | 48 | 60.0% | 6512 | 10397 | $0.7231 | $0.0060 |
| B1 | 3 | 120 | 77 | 43 | 64.2% | 7139 | 34506 | $1.2982 | $0.0108 |
| P1 | 3 | 120 | 91 | 29 | 75.8% | 7093 | 10398 | $0.8954 | $0.0075 |
| P2 | 3 | 120 | 91 | 29 | 75.8% | 6926 | 9591 | $0.9017 | $0.0075 |
| P3 | 3 | 120 | 94 | 26 | 78.3% | 7236 | 10369 | $0.8996 | $0.0075 |
| P4 | 2 | 80 | 56 | 24 | 70.0% | 10427 | 30708 | $1.3119 | $0.0164 |

Note: pairwise tests below use each condition's own pooled n (unequal n is fine for two-proportion z / Fisher).

### Pairwise pass-rate tests (pooled)

| A vs B | A n | B n | A pass% | B pass% | Δpp | z | p(z) | p(Fisher) | sig |
|--------|----:|----:|--------:|--------:|----:|--:|------:|----------:|-----|
| P1 vs B0 | 120 | 120 | 75.8% | 60.0% | +15.8 | 2.627 | 0.0086 | 0.0125 | ** |
| P2 vs B0 | 120 | 120 | 75.8% | 60.0% | +15.8 | 2.627 | 0.0086 | 0.0125 | ** |
| P3 vs B0 | 120 | 120 | 78.3% | 60.0% | +18.3 | 3.075 | 0.0021 | 0.0032 | ** |
| P4 vs B0 | 80 | 120 | 70.0% | 60.0% | +10.0 | 1.443 | 0.1489 | 0.1766 | ns |
| B1 vs B0 | 120 | 120 | 64.2% | 60.0% | +4.2 | 0.665 | 0.5059 | 0.5947 | ns |
| P1 vs B1 | 120 | 120 | 75.8% | 64.2% | +11.7 | 1.972 | 0.0486 | 0.0667 | * |
| P3 vs B1 | 120 | 120 | 78.3% | 64.2% | +14.2 | 2.425 | 0.0153 | 0.0221 | * |
| P1 vs P2 | 120 | 120 | 75.8% | 75.8% | +0.0 | 0.000 | 1.0000 | 1.0000 | ns |
| P1 vs P3 | 120 | 120 | 75.8% | 78.3% | -2.5 | -0.461 | 0.6450 | 0.7589 | ns |
| P2 vs P3 | 120 | 120 | 75.8% | 78.3% | -2.5 | -0.461 | 0.6450 | 0.7589 | ns |
| P1 vs P4 | 120 | 80 | 75.8% | 70.0% | +5.8 | 0.916 | 0.3598 | 0.4144 | ns |
| P2 vs P4 | 120 | 80 | 75.8% | 70.0% | +5.8 | 0.916 | 0.3598 | 0.4144 | ns |
| P3 vs P4 | 120 | 80 | 78.3% | 70.0% | +8.3 | 1.333 | 0.1824 | 0.1876 | ns |

Full pairwise matrix (z-test p-values only):

|  | B0 | B1 | P1 | P2 | P3 | P4 |
|--|------|------|------|------|------|------|
| B0 | — | 0.5059 | 0.0086 | 0.0086 | 0.0021 | 0.1489 |
| B1 | 0.5059 | — | 0.0486 | 0.0486 | 0.0153 | 0.3919 |
| P1 | 0.0086 | 0.0486 | — | 1.0000 | 0.6450 | 0.3598 |
| P2 | 0.0086 | 0.0486 | 1.0000 | — | 0.6450 | 0.3598 |
| P3 | 0.0021 | 0.0153 | 0.6450 | 0.6450 | — | 0.1824 |
| P4 | 0.1489 | 0.3919 | 0.3598 | 0.3598 | 0.1824 | — |

## 3. Remaining edge-band comparisons

After the targeted Trial 3, any pair still in p ∈ [0.03, 0.10] is listed below. Pairs that moved clearly in/out of significance are discussed in §4.

| Comparison | Δpp | p (edge test) | Note |
|------------|----:|--------------:|------|
| P1 vs B1 | +11.7 | 0.0486 (z) | z/Fisher disagree at α=0.05 |
| P2 vs B1 | +11.7 | 0.0486 (z) | z/Fisher disagree at α=0.05 |

## 4. Plain-language summary for the paper

### Defensible findings

- **P1 > B0** (75.8% vs 60.0%, Δ=+15.8 pp, n=120 vs 120, z p=0.0086, Fisher p=0.0125)
- **P2 > B0** (75.8% vs 60.0%, Δ=+15.8 pp, n=120 vs 120, z p=0.0086, Fisher p=0.0125)
- **P3 > B0** (78.3% vs 60.0%, Δ=+18.3 pp, n=120 vs 120, z p=0.0021, Fisher p=0.0032)

### Statistically indistinguishable vs B0

- **B1 vs B0** not significant at α=0.05 (64.2% vs 60.0%, n=120 vs 120, Fisher p=0.5947)
- **P4 vs B0** not significant at α=0.05 (70.0% vs 60.0%, n=80 vs 120, Fisher p=0.1766)

### P1 / P2 / P3 cluster

- P1 vs P2: indistinguishable (Δ=+0.0 pp, Fisher p=1.0000)
- P1 vs P3: indistinguishable (Δ=-2.5 pp, Fisher p=0.7589)
- P2 vs P3: indistinguishable (Δ=-2.5 pp, Fisher p=0.7589)
- P3 vs B1: 78.3% vs 64.2% (Δ=+14.2 pp, z p=0.0153, Fisher p=0.0221, *)

### Cost / latency (descriptive only)

Report per-trial values and their mean; do not over-claim cost significance from a handful of trial totals. Qualitatively: P4 remains the expensive outlier; B1 has high p95 from blind retries; P1–P3 cluster on cost.

### Further trials?

Some pairs remain near the decision boundary (B1 vs P1, B1 vs P2). A further trial is optional and only worth it if that specific claim is central to the paper.

---

*Generated by `scripts/significance_analysis.py`. α=0.05 two-sided; no multiple-comparison correction applied (exploratory pairwise screen — note this in the paper).*
