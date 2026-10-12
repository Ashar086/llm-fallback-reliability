# Appendix probe outcomes (not included in this release)

**Status.** `2wiki_outcomes.csv` and `gpt4o_mini_outcomes.csv` are **not**
shipped with the public repository. The paper reports only **descriptive**
pooled rates for those probes and does **not** claim they are reproducible
from GitHub alone.

If you obtain the original per-question logs, place CSVs here to regenerate
paired McNemar tests:

- `2wiki_outcomes.csv` — 50 2Wiki questions × 2 trials × {B0,B1,P1,P3}
- `gpt4o_mini_outcomes.csv` — 50 Hotpot IDs × 2 trials × {B0,P1,P3}

Schema (same as `results_scaled/question_outcomes.csv`):

| column | type |
|--------|------|
| `condition` | str |
| `question_id` | str |
| `trial` | int |
| `pass` | bool |

Then run:

```bash
python scripts/appendix_paired_stats.py
```

Outputs land in `results_scaled/stats/appendix/`.

**What is reproducible from this release without these CSVs:** the main
150×3 Hotpot experiment (`question_outcomes.csv`) and the P1 check ablation
(`stats/appendix/p1_ablation_outcomes.csv`).
