# Appendix probe outcomes (optional)

Place question-level outcome CSVs here to regenerate appendix McNemar tests:

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
