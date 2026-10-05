# Reliability & Fallback Design Patterns for Multi-Agent LLM Systems

Code, data, and paper sources for a controlled comparison of fallback strategies
in a multi-agent LLM pipeline. When a Planner → Retriever → Synthesizer →
Formatter graph fails mid-run, what should you do? Stop, blind-retry, tool-check
and retry, roll back to a checkpoint, degrade, or call a second verifier agent?

**Authors.** Muhammad Ashar Ishfaq (The Islamia University of Bahawalpur) and
Muhammad Asad Ishfaq (Indiana University Bloomington).

**Status:** Accepted to the **NeurIPS 2026 Workshop "Who Verifies the Agents?"**
(VerifyAgents), camera-ready.

**Headline finding.** Targeted fallbacks (P1–P3, P5) significantly beat
no-fallback under question-level McNemar tests when they address common
recoverable failure modes (especially schema/JSON breakage on Claude Sonnet).
Blind retry (B1) does not after Bonferroni correction. A cross-agent verifier
(P4) beats B0 but is worse than P3 on cost and accuracy. Gains are
failure-mode-dependent (GPT-4o-mini probe shows little lift when structural
failures are rare).

**Paper.** Camera-ready LaTeX: [`overleaf_neurips/`](overleaf_neurips/).
Prebuilt PDF: [`paper_submission.pdf`](paper_submission.pdf).

---

## System Architecture

<p align="center">
  <img src="figures/Agent%20Orchestrator%20Fallback-2026-09-03-160610.png" alt="Reliability & Fallback Design Patterns Architecture" width="100%">
</p>

*Figure: Controlled comparison between standard blind retry cascading (Panel A)
and state-isolated deterministic fallback architecture (Panel B).*

---

## Conditions

| ID | Name | What it does |
|----|------|----------------|
| **B0** | No fallback | One pass; fail and stop |
| **B1** | Blind retry | Re-run the same stage or graph up to *k* times, with no new evidence |
| **P1** | Tool-grounded retry | External checks (empty retrieval, bad citations, schema); retry only the failed stage with that feedback |
| **P2** | Deterministic checkpointing | Save trusted state; on failure, roll back and re-run forward |
| **P3** | Graceful degradation | After retries or budget fail, skip planning, optionally switch to Haiku, or return a low-confidence partial |
| **P4** | Cross-agent verification | Verifier agent gates Synthesizer → Formatter; on reject, at most one re-synth |
| **P5** | Composed P1+P2 | Tool-grounded retry first; on continued failure, checkpoint rollback |

All primary LLM stages use Claude Sonnet (`claude-sonnet-4-6`) at temperature 0.
Haiku shows up only on P3’s rare cheap path.

---

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then put your Anthropic key in .env
```

You need `ANTHROPIC_API_KEY` in `.env`. Never commit that file.

---

## Run a condition

```bash
python run_pipeline.py --condition B0
python run_pipeline.py --condition P1 --trial 1
python run_pipeline.py --condition P4 --trial 2 --resume
```

- `--condition`: one of `B0`, `B1`, `P1`, `P2`, `P3`, `P4`, `P5`
- `--trial N`: write logs under `logs/{condition}/trial_N/`
- `--resume`: skip questions that already have a log in that folder
- `--mock`: offline stub LLM (no API calls; plumbing checks only)

Logs are JSON per question. Aggregate one condition with:

```bash
python -m pipeline.aggregate P1 --trial 1
```

---

## Reproduce tables and figures (camera-ready)

**Inferential (canonical):** 150 paired HotpotQA questions → majority pass
across 3 trials → McNemar → Bonferroni (`α = 0.05/21`).

**Descriptive:** 450 logged runs per condition → pooled pass rate + Wilson CI,
latency, cost.

```bash
python run_stats.py                      # writes results_scaled/stats/
python scripts/paired_question_stats.py  # McNemar JSON
python scripts/make_figures_scaled.py    # figures_scaled/ + overleaf figures
python scripts/audit_mcnemar_tex.py      # cross-check paper vs stats
```

Canonical summary: [`results_scaled/stats/statistical_summary.md`](results_scaled/stats/statistical_summary.md).  
Highlight table: [`results_scaled/stats/paired_question_highlight.csv`](results_scaled/stats/paired_question_highlight.csv).

Legacy pooled two-proportion z-tests are still emitted under
`results_scaled/stats/pairwise_pvalues*.csv` for diagnostics only — **do not
quote them as camera-ready significance.**

---

## Dataset

HotpotQA distractor validation subset under `data/` (scaled experiment: 150
questions; see `data/questions.json` and `data/dataset_meta.json`).

---

## Paper (NeurIPS / Overleaf)

Upload [`overleaf_neurips/`](overleaf_neurips/) to Overleaf. Main file:
`overleaf_neurips/main.tex`.

Camera-ready package option:

```latex
\usepackage[dblblindworkshop, final]{neurips_2026}
```

See [`overleaf_neurips/README.md`](overleaf_neurips/README.md).

---

## Repo structure

```
run_pipeline.py                 # CLI entrypoint
run_stats.py                    # McNemar-canonical + descriptive stats
config.py                       # model names, pricing, retry knobs
pipeline/                       # graph, nodes, scoring, logging, strategies/
scripts/                        # paired stats, figures, ablations, probes
results_scaled/stats/           # camera-ready statistical outputs
data/                           # questions + corpus + meta
figures/                        # architecture diagram + older figs
figures_scaled/                 # regenerated result figures
overleaf_neurips/               # NeurIPS 2026 LaTeX (camera-ready)
paper_submission.pdf            # named PDF
CITATION.cff                    # citation metadata
logs/                           # local run outputs (gitignored)
```

---

## Citation

```bibtex
@misc{ishfaq2026fallback,
  title        = {Reliability \& Fallback Design Patterns for Multi-Agent LLM Systems},
  author       = {Ishfaq, Muhammad Ashar and Ishfaq, Muhammad Asad},
  year         = {2026},
  note         = {Accepted to NeurIPS 2026 Workshop Who Verifies the Agents?},
  howpublished = {\url{https://github.com/Ashar086/llm-fallback-reliability}}
}
```

See also [`CITATION.cff`](CITATION.cff).

---

## License

MIT. See [`LICENSE`](LICENSE).

---

## Feedback

Issues and PRs are welcome: bugs in the harness, clearer docs, replication on
other models or tasks, or comments on `overleaf_neurips/main.tex`.
