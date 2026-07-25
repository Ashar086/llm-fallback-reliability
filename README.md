# Reliability & Fallback Design Patterns for Multi-Agent LLM Systems

Code, data, and paper sources for a controlled comparison of fallback strategies
in a multi-agent LLM pipeline. When a Planner → Retriever → Synthesizer →
Formatter graph fails mid-run, what should you do? Stop, blind-retry, tool-check
and retry, roll back to a checkpoint, degrade, or call a second verifier agent?

**Authors.** Muhammad Ashar Ishfaq and Muhammad Asad Ishfaq (The Islamia
University of Bahawalpur).

**Headline finding.** Tool-grounded retry (P1), deterministic checkpointing
(P2), and graceful degradation (P3) significantly beat a no-fallback baseline
on pass rate at modest extra cost. Blind retry (B1) and a cross-agent
verification gate (P4) did not, even though they cost more and stretch p95
latency.

**Paper.** Markdown draft: [`full_draft.md`](full_draft.md). NeurIPS 2026
workshop LaTeX (Overleaf-ready): [`overleaf_neurips/`](overleaf_neurips/).
Prebuilt PDFs: [`paper_submission.pdf`](paper_submission.pdf) (named) and
[`paper_submission_anonymized.pdf`](paper_submission_anonymized.pdf) (blind).

---

## Six conditions

| ID | Name | What it does |
|----|------|----------------|
| **B0** | No fallback | One pass; fail and stop |
| **B1** | Blind retry | Re-run the same stage or graph up to *k* times, with no new evidence |
| **P1** | Tool-grounded retry | External checks (empty retrieval, bad citations, schema); retry only the failed stage with that feedback |
| **P2** | Deterministic checkpointing | Save trusted state; on failure, roll back and re-run forward |
| **P3** | Graceful degradation | After retries or budget fail, skip planning, optionally switch to Haiku, or return a low-confidence partial |
| **P4** | Cross-agent verification | Verifier agent gates Synthesizer → Formatter; on reject, at most one re-synth |

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

- `--condition`: one of `B0`, `B1`, `P1`, `P2`, `P3`, `P4`
- `--trial N`: write logs under `logs/{condition}/trial_N/`
- `--resume`: skip questions that already have a log in that folder
- `--mock`: offline stub LLM (no API calls; plumbing checks only)

Logs are JSON per question. Aggregate one condition with:

```bash
python -m pipeline.aggregate P1 --trial 1
```

---

## Reproduce tables and figures

Published numbers are in [`significance_results.md`](significance_results.md)
(ground truth for the paper). Figures:

```bash
# Needs logs under logs/{B0..P4}/trial_{1,2[,3]}/ as in the paper runs
python scripts/significance_analysis.py   # regenerates significance_results.md
python scripts/make_figures.py            # writes figures/fig1_*.png ... fig3_*.png
python scripts/compare_conditions.py      # quick side-by-side table (optional)
```

`make_figures.py` embeds the pooled numbers from `significance_results.md`.
It does not re-score logs. Re-running the full six-condition trial matrix
costs on the order of a few USD of Anthropic API usage (see the paper and
past trial totals).

---

## Dataset

HotpotQA distractor validation subset, **included** under `data/`:

- `data/questions.json`: 40 multi-hop questions
- `data/corpus/`: 100 docs (80 supporting + 20 distractors)
- `data/dataset_meta.json`: filters and IDs

Selection filters (also in meta / `scripts/build_hotpot_subset.py`): short gold
answers (at most 60 chars / 6 tokens), no yes/no, at least 2 supporting titles,
bridge-type preferred, deterministic sort-then-take-40. To rebuild from
Hugging Face:

```bash
pip install datasets
python scripts/build_hotpot_subset.py
```

---

## Paper (NeurIPS / Overleaf)

Upload the [`overleaf_neurips/`](overleaf_neurips/) folder to Overleaf (or zip
its contents). Main file: `overleaf_neurips/main.tex`. It uses the official
NeurIPS 2026 style (`neurips_2026.sty`) in double-blind workshop mode.

1. Overleaf → New Project → Upload Project (zip the folder contents)
2. Set main document to `main.tex`
3. Edit `\workshoptitle{...}` to your workshop name
4. Blind review: `\usepackage[dblblindworkshop]{neurips_2026}`
5. Camera-ready: `\usepackage[dblblindworkshop, final]{neurips_2026}`

See [`overleaf_neurips/README.md`](overleaf_neurips/README.md).

---

## Repo structure

```
run_pipeline.py                 # CLI entrypoint
config.py                       # model names, pricing, retry knobs
pipeline/                       # graph, nodes, scoring, logging, strategies/
  strategies/                   # B1, P1-P4 wrappers / orchestrators
data/                           # questions + corpus + meta
scripts/                        # subset builder, significance, figures
figures/                        # fig1-fig3 PNGs
full_draft.md                   # markdown paper draft
overleaf_neurips/               # NeurIPS 2026 LaTeX (Overleaf)
paper_submission.pdf            # named PDF
paper_submission_anonymized.pdf # blind PDF
significance_results.md         # pooled stats used in the paper
framework_design.md             # pattern specs
lit_scan.md                     # related-work source list
CITATION.cff                    # citation metadata
logs/                           # local run outputs (gitignored)
```

---

## How to cite

```bibtex
@misc{ishfaq2026fallback,
  title        = {Reliability \& Fallback Design Patterns for Multi-Agent LLM Systems},
  author       = {Ishfaq, Muhammad Ashar and Ishfaq, Muhammad Asad},
  year         = {2026},
  note         = {Preprint; NeurIPS workshop submission},
  howpublished = {\url{https://github.com/Ashar086/llm-fallback-reliability}}
}
```

Plain text:

> Muhammad Ashar Ishfaq and Muhammad Asad Ishfaq. (2026). *Reliability &
> Fallback Design Patterns for Multi-Agent LLM Systems*. Preprint; NeurIPS
> workshop submission.

See also [`CITATION.cff`](CITATION.cff).

---

## License

MIT. See [`LICENSE`](LICENSE).

---

## Feedback

Issues and PRs are welcome: bugs in the harness, clearer docs, replication on
other models or tasks, or comments on the draft in `full_draft.md` /
`overleaf_neurips/main.tex`.
