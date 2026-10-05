# Reliability & Fallback Design Patterns for Multi-Agent LLM Systems

Reproduction code and data for a controlled comparison of orchestration-level
fallback strategies in a multi-agent LLM pipeline
(Planner → Retriever → Synthesizer → Formatter).

**Authors.** Muhammad Ashar Ishfaq (The Islamia University of Bahawalpur),
Muhammad Asad Ishfaq (The Islamia University of Bahawalpur).

When a stage fails mid-run, systems may stop, blindly retry, apply tool-grounded
checks, restore a checkpoint, degrade, or call a second verifier. This repository
implements those conditions on a fixed HotpotQA multi-hop testbed and reports
pass rate, latency, and cost under a shared scorer.

Primary significance tests use **150 paired questions** (majority outcome across
three trials) with McNemar's test and Bonferroni correction. Pooled **450 runs**
per condition are used only for descriptive rates, Wilson CIs, latency, and cost.

---
### Conditions

| ID | Name | Role | Strategy Description |
| :--- | :--- | :--- | :--- |
| **B0** | No fallback | Baseline | Immediate halt on failure |
| **B1** | Blind retry | Baseline | Naive retry with identical prompt/context |
| **P1** | Tool-grounded retry | Targeted | Inspect tool error output before re-attempting |
| **P2** | Deterministic checkpointing | Targeted | Roll back to last verified stage state |
| **P3** | Graceful degradation | Targeted | Fall back to lightweight fast-path (Claude Haiku) |
| **P4** | Cross-agent verification | Targeted | Secondary verifier agent critique |
| **P5** | Composed P1+P2 | Tested composition | Checkpointing + tool-grounded recovery |
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

```bash
python run_stats.py
python scripts/paired_question_stats.py
python scripts/make_figures_scaled.py
python scripts/audit_mcnemar_tex.py
```

Canonical outputs:

- [`results_scaled/stats/statistical_summary.md`](results_scaled/stats/statistical_summary.md)
- [`results_scaled/stats/paired_question_highlight.csv`](results_scaled/stats/paired_question_highlight.csv)
- [`results_scaled/stats/paired_question_tests.json`](results_scaled/stats/paired_question_tests.json)

Legacy pooled z-tests under `results_scaled/stats/pairwise_pvalues*.csv` are
diagnostic only and are not the primary inferential analysis.

---

## Data

HotpotQA distractor validation subset under [`data/`](data/)
(`questions.json`, `corpus/`, `dataset_meta.json`). See [`data/README.md`](data/README.md).

---

## Citation

```bibtex
@misc{ishfaq2026fallback,
  title        = {Reliability \& Fallback Design Patterns for Multi-Agent LLM Systems},
  author       = {Ishfaq, Muhammad Ashar and Ishfaq, Muhammad Asad},
  year         = {2026},
  howpublished = {\url{https://github.com/Ashar086/llm-fallback-reliability}}
}
```

See also [`CITATION.cff`](CITATION.cff).

---

## License

MIT. See [`LICENSE`](LICENSE).
