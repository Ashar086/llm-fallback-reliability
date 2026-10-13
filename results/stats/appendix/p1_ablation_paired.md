# P1 ablation (paired McNemar)

Separate 50-question Hotpot subset (not the main 150-question set). Pass if n_pass >= ceil(n_trials/2); with 2 trials a 1-1 split counts as pass. McNemar on 50 paired questions; Bonferroni alpha=0.05/7 (≈0.00714) over the seven unique table comparisons.

**n_questions=50**, trials=2, pooled runs per variant=100.

## Pooled pass % (Wilson 95% CI on 100 runs)

- B0: 62.0% [52.2, 70.9] (62/100 runs)
- P1-full: 79.0% [70.0, 85.8] (79/100 runs)
- P1R: 61.0% [51.2, 70.0] (61/100 runs)
- P1C: 57.0% [47.2, 66.3] (57/100 runs)
- P1S: 74.0% [64.6, 81.6] (74/100 runs)

## McNemar comparisons (question-level majority)

- P1-full vs B0: Δpp=+12.0, p=0.0771 (ns Bonferroni)
- P1-full vs P1R: Δpp=+16.0, p=0.0433 (ns Bonferroni)
- P1-full vs P1C: Δpp=+18.0, p=0.0265 (ns Bonferroni)
- P1-full vs P1S: Δpp=+4.0, p=0.4795 (ns Bonferroni)
- B0 vs P1R: Δpp=+4.0, p=0.6831 (ns Bonferroni)
- B0 vs P1C: Δpp=+6.0, p=0.4497 (ns Bonferroni)
- B0 vs P1S: Δpp=-8.0, p=0.2207 (ns Bonferroni)
