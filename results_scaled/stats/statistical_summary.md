# Statistical Analysis Summary

Camera-ready canonical analysis for the HotpotQA main experiment (matches `overleaf_neurips/main.tex`).

## Analysis layers

1. **Inferential (canonical):** 150 paired questions -> majority pass across 3 trials -> two-sided McNemar (continuity correction) -> Bonferroni over 21 pairs (alpha=0.002381). Primary p-values and Delta-pp in the paper use this layer.
2. **Descriptive:** 450 logged runs per condition -> pooled pass rate, Wilson 95% CI, latency p50/p95, average $/question. These are *not* treated as independent observations for significance.
3. **Appendix-only:** P1 ablation / 2Wiki / GPT-4o-mini probes use pooled two-proportion z-tests on their own smaller subsets (clearly labeled in the paper appendix). They are **not** the canonical HotpotQA significance path.

Legacy pooled z-tests are still written to `pairwise_pvalues_tidy.csv` for diagnostics; **do not quote them as camera-ready significance.**

## Inferential results (150 paired questions, McNemar)

### Highlight pairs (Bonferroni alpha=0.002381)

| Comparison | Maj.% A | Maj.% B | Delta-pp (A-B) | McNemar p | sig |
|------------|--------:|--------:|----------:|----------:|:---:|
| P1 vs B0 | 76.0% | 54.7% | +21.3 | 1.06e-07 | ** |
| P2 vs B0 | 75.3% | 54.7% | +20.7 | 8.14e-07 | ** |
| P3 vs B0 | 78.7% | 54.7% | +24.0 | 5.43e-09 | ** |
| P5 vs B0 | 74.0% | 54.7% | +19.3 | 4.93e-07 | ** |
| P4 vs B0 | 69.3% | 54.7% | +14.7 | 7.23e-05 | ** |
| P3 vs P1 | 78.7% | 76.0% | +2.7 | 0.1336 | ns |
| P3 vs P2 | 78.7% | 75.3% | +3.3 | 0.1306 | ns |
| P3 vs P5 | 78.7% | 74.0% | +4.7 | 0.0233 | ns |
| P4 vs P1 | 69.3% | 76.0% | -6.7 | 0.0044 | ns |
| P4 vs P3 | 69.3% | 78.7% | -9.3 | 0.0005 | ** |
| B1 vs B0 | 60.7% | 54.7% | +6.0 | 0.0265 | ns |
| P5 vs P1 | 74.0% | 76.0% | -2.0 | 0.3711 | ns |
| P5 vs P2 | 74.0% | 75.3% | -1.3 | 0.7237 | ns |

### Key findings (McNemar)

- P1 vs B0: significant, McNemar p=1.06e-07, dpp=+21.3 (majority), h=0.45 (medium effect)
- P2 vs B0: significant, McNemar p=8.14e-07, dpp=+20.7 (majority), h=0.44 (medium effect)
- P3 vs B0: significant, McNemar p=5.43e-09, dpp=+24.0 (majority), h=0.52 (large effect)
- P5 vs B0: significant, McNemar p=4.93e-07, dpp=+19.3 (majority), h=0.41 (medium effect)
- P4 vs B0: significant, McNemar p=7.23e-05, dpp=+14.7 (majority), h=0.30 (medium effect)
- B1 vs B0: not significant, McNemar p=0.0265, dpp=+6.0 (majority), h=0.12 (small effect)
- P3 vs P1: not significant, McNemar p=0.1336 (dpp=+2.7)
- P3 vs P2: not significant, McNemar p=0.1306
- P3 vs P5: not significant, McNemar p=0.0233
- P5 vs P1: not significant, McNemar p=0.3711 (tested P1+P2 composition)
- P4 vs P3: significant, McNemar p=0.0005 (P3 higher pass rate; P4 still significant vs B0)

### Composition (P5)
Pooled descriptive pass rates: P5=74.7%, P1=76.0%, P2=76.2%.
Question-level majority: P5=74.0%, P1=76.0%, P2=75.3%.
P5 vs P1: McNemar p=0.3711 (not significant). Interpretation: no additional benefit from the tested P1+P2 composition (not a general claim about all stacking).

### P4 interpretation
P4 vs B0: McNemar p=7.23e-05 (significant); P4 does beat B0.
P4 vs P3: McNemar p=0.0005 (significant). P4 costs 2.5x more than P3 for 10.0 pp lower pooled pass rate. Conclusion: significant vs B0, but worse cost--accuracy than P3 (do not claim P4 fails to beat the no-fallback baseline).

## Descriptive results (450 logged runs)

Pooled rates / Wilson CIs / cost below use all 450 runs. Use for tables and figures; use McNemar above for significance stars.

### Wilson 95% confidence intervals (pooled runs)

| Condition | Pass Rate | CI Lower | CI Upper | n_runs |
|-----------|----------:|---------:|---------:|-------:|
| B0 | 55.3% | 50.7% | 59.9% | 450 |
| B1 | 61.1% | 56.5% | 65.5% | 450 |
| P1 | 76.0% | 71.8% | 79.7% | 450 |
| P2 | 76.2% | 72.1% | 79.9% | 450 |
| P3 | 78.2% | 74.2% | 81.8% | 450 |
| P4 | 68.2% | 63.8% | 72.4% | 450 |
| P5 | 74.7% | 70.5% | 78.5% | 450 |

### Cost efficiency (pooled)

| Condition | Pass Rate | $/Q | Pass/$ | Cost/1000 successes | × vs P3 |
|-----------|----------:|----:|-------:|--------------------:|--------:|
| B0 | 55.3% | $0.0052 | 106.9 | $9.35 | 0.71× |
| B1 | 61.1% | $0.0085 | 72.3 | $13.83 | 1.15× |
| P1 | 76.0% | $0.0072 | 104.9 | $9.53 | 0.99× |
| P2 | 76.2% | $0.0073 | 104.8 | $9.54 | 0.99× |
| P3 | 78.2% | $0.0073 | 106.8 | $9.36 | 1.00× |
| P4 | 68.2% | $0.0183 | 37.2 | $26.85 | 2.50× |
| P5 | 74.7% | $0.0071 | 104.7 | $9.55 | 0.97× |

### Question stability (within 3 trials)

| Condition | Fully reliable (3/3) | Fully unreliable (0/3) | Unstable mixed |
|-----------|---------------------:|-----------------------:|---------------:|
| B0 | 50.0% | 38.7% | 11.3% |
| B1 | 54.7% | 32.0% | 13.3% |
| P1 | 74.0% | 22.0% | 4.0% |
| P2 | 74.0% | 20.7% | 5.3% |
| P3 | 75.3% | 19.3% | 5.3% |
| P4 | 62.7% | 27.3% | 10.0% |
| P5 | 72.0% | 22.0% | 6.0% |

## Legacy pooled z-tests (diagnostic only)

These treat 450 runs as independent and are **optimistic**. Kept for regression checks against older drafts; camera-ready claims must use McNemar p-values above.

- P1 vs B0: pooled z-test p=6.63e-11 (legacy; not camera-ready)
- P2 vs B0: pooled z-test p=4.00e-11 (legacy; not camera-ready)
- P3 vs B0: pooled z-test p=3.12e-13 (legacy; not camera-ready)
- P5 vs B0: pooled z-test p=1.20e-09 (legacy; not camera-ready)
- P4 vs B0: pooled z-test p=6.93e-05 (legacy; not camera-ready)
- P3 vs P1: pooled z-test p=0.4275 (legacy; not camera-ready)
- P3 vs P2: pooled z-test p=0.4744 (legacy; not camera-ready)
- P3 vs P5: pooled z-test p=0.2088 (legacy; not camera-ready)
- P4 vs P1: pooled z-test p=0.0093 (legacy; not camera-ready)
- P4 vs P3: pooled z-test p=0.0007 (legacy; not camera-ready)
- B1 vs B0: pooled z-test p=0.0789 (legacy; not camera-ready)
- P5 vs P1: pooled z-test p=0.6427 (legacy; not camera-ready)
- P5 vs P2: pooled z-test p=0.5877 (legacy; not camera-ready)

## Paper-ready sentences (McNemar-aligned)
- "P1, P2, P3, and P5 each significantly outperform B0 under question-level McNemar tests with Bonferroni correction (each p < 1e-6; 150 paired questions), with pooled pass rates 76.0%, 76.2%, 78.2%, 74.7% versus 55.3% (450 runs)."
- "P3 achieves the highest pooled pass rate at $0.0073/Q among the targeted cluster."
- "P4 significantly beats B0 (McNemar p=7.23e-05) but has lower pass rate and 2.5× higher cost than P3 (P4 vs P3: p=0.0005)."
- "The tested P1+P2 composition (P5) does not significantly beat P1 (McNemar p=0.3711); we report no additional benefit from this composition (other stacks were not evaluated)."
- "B1 (blind retry) does not significantly beat B0 after Bonferroni (McNemar p=0.0265; pooled 61.1% vs 55.3%)."

---
*Generated by `run_stats.py`. Inferential: 150 paired questions, majority -> McNemar, Bonferroni alpha=0.002381. Descriptive: 450 logged runs/condition. See also `paired_question_highlight.csv` and `paired_question_tests.json`.*
