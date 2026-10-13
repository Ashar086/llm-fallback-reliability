# Reliability & Fallback Design Patterns for Multi-Agent LLM Systems

Reproduction code and data for a controlled comparison of orchestration-level
fallback strategies in a multi-agent LLM pipeline
(Planner → Retriever → Synthesizer → Formatter).

**Authors.** Muhammad Ashar Ishfaq (The Islamia University of Bahawalpur),
Muhammad Asad Ishfaq (Indiana University Bloomington).

When a stage fails mid-run, systems may stop, blindly retry, apply tool-grounded
checks, restore a checkpoint, degrade, or call a second verifier. This repository
implements those conditions on a fixed HotpotQA multi-hop testbed and reports
pass rate, latency, and cost under a shared scorer.

**Main experiment (matches the camera-ready paper).** Primary significance tests
use **150 paired questions** (majority across three trials) with **McNemar's
test** and **Bonferroni** correction over 21 condition pairs
(α = 0.05/21 ≈ 0.002381). Pooled **450 runs** per condition (150 × 3) are used
only for descriptive rates, Wilson CIs, latency, and cost.

**Primary Claude Sonnet runs** for the main matrix completed **2026-07-27**
(`claude-sonnet-4-6`, temperature 0). Model APIs change over time; pin packages
below and treat that date as the experiment snapshot.

---

## Entry points

| Script | Role |
|--------|------|
| `run_pipeline.py` | Run one condition/trial (writes under `logs/`) |
| `scripts/run_stats.py` | Wilson CIs, McNemar, cost, stability, summary |
| `scripts/paired_question_stats.py` | Full paired-question JSON |
| `scripts/make_figures_scaled.py` | Figures from `results/stats/` |
| `scripts/appendix_paired_stats.py` | P1 ablation (+ optional probes) |
| `scripts/build_question_outcomes.py` | Rebuild outcomes CSV from `logs/` |
| `scripts/audit_mcnemar_tex.py` | Cross-check paper TeX vs stats JSON |

`results/` holds committed question-level outcomes and stats for the paper
(formerly named `results_scaled` during the scaled 150-question campaign).

---

## Conditions

| ID | Name | Role |
|----|------|------|
| B0 | No fallback | Baseline |
| B1 | Blind retry | Baseline |
| P1 | Tool-grounded retry | Targeted |
| P2 | Deterministic checkpointing | Targeted |
| P3 | Graceful degradation | Targeted |
| P4 | Cross-agent verification | Targeted |
| P5 | Composed P1+P2 | Tested composition |

Primary LLM stages use Claude Sonnet (`claude-sonnet-4-6`) at temperature 0.
Haiku is used only on P3's rare cheap path.

---

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY
```

Never commit `.env`.

---

## Running experiments

```bash
python run_pipeline.py --condition B0
python run_pipeline.py --condition P1 --trial 1
python run_pipeline.py --condition P5 --trial 2 --resume
```

- `--condition`: `B0`, `B1`, `P1`, `P2`, `P3`, `P4`, or `P5`
- `--trial N`: logs under `logs/{condition}/trial_N/`
- `--resume`: skip questions that already have logs
- `--mock`: offline stub (no API calls)

```bash
python -m pipeline.aggregate P1 --trial 1
```

---

## Reproducing statistics and figures

**Main Hotpot experiment (150 questions × 3 trials).** The public release
includes `results/question_outcomes.csv` so tables and McNemar tests can be
rebuilt **without** re-running the pipeline or holding the original `logs/`.
To regenerate that CSV from local run logs (optional):

```bash
python scripts/build_question_outcomes.py   # reads logs/{B0..P5}/trial_{1,2,3}/
python scripts/build_experiment_summary.py
python scripts/run_stats.py
python scripts/paired_question_stats.py
python scripts/make_figures_scaled.py
python scripts/audit_mcnemar_tex.py
```

**Appendix ablation (50 IDs × 2 trials).** With local logs for `P1R`, `P1C`,
`P1S` (or use committed `results/stats/appendix/`):

```bash
python scripts/appendix_paired_stats.py
```

**2Wiki / GPT-4o-mini probes.** Outcome CSVs for these probes are **not** in
the public release (see
[`results/appendix_probes/README.md`](results/appendix_probes/README.md)).
The paper reports descriptive pooled rates only.

Canonical outputs:

- [`results/stats/statistical_summary.md`](results/stats/statistical_summary.md)
- [`results/stats/paired_question_highlight.csv`](results/stats/paired_question_highlight.csv)
- [`results/stats/paired_question_all_pairs.csv`](results/stats/paired_question_all_pairs.csv) — full 21-pair McNemar matrix
- [`results/stats/paired_question_tests.json`](results/stats/paired_question_tests.json)
- [`results/stats/appendix/p1_ablation_paired.json`](results/stats/appendix/p1_ablation_paired.json)

Legacy pooled z-tests under `results/stats/pairwise_pvalues*.csv` are
diagnostic only and are not the primary inferential analysis.

---

## Data

HotpotQA distractor validation subset under [`data/`](data/)
(`questions.json`, `corpus/`, `dataset_meta.json`). See [`data/README.md`](data/README.md).

**Source / license.** Content is derived from [HotpotQA](https://hotpotqa.github.io/)
(Yang et al., EMNLP 2018), licensed **CC BY-SA 4.0**. Our subset was built with
`scripts/build_hotpot_subset.py` via Hugging Face `datasets`.

---

## Citation

```bibtex
@misc{ishfaq2026fallback,
  title        = {Reliability \& Fallback Design Patterns for Multi-Agent LLM Systems},
  author       = {Ishfaq, Muhammad Ashar and Ishfaq, Muhammad Asad},
  year         = {2026},
  note         = {NeurIPS 2026 Workshop: Who Verifies the Agents?},
  howpublished = {\url{https://github.com/Ashar086/llm-fallback-reliability}}
}
```

See also [`CITATION.cff`](CITATION.cff). After the camera-ready OpenReview /
Zenodo DOI is public, update the `url` / `doi` fields there and the GitHub
repository **About → Website**.

---

## License

Code: MIT (`LICENSE`). HotpotQA-derived text under `data/`: **CC BY-SA 4.0**.
