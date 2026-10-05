# Overleaf / NeurIPS 2026 LaTeX project

Official NeurIPS 2026 style (`neurips_2026.sty`) for the VerifyAgents workshop
revision with scaled experiments (150 HotpotQA questions × 3 trials × 7 conditions;
n=450 per condition), plus terminal failure-type analysis (Fig. 6 / Table) and a
2WikiMultihopQA generalization check.

**Authors:** Muhammad Ashar Ishfaq, Muhammad Asad Ishfaq (The Islamia University
of Bahawalpur). Hidden under `dblblindworkshop` until camera-ready `final`.

**Code / logs:** https://github.com/Ashar086/llm-fallback-reliability

## Upload to Overleaf

1. Upload `overleaf_neurips_scaled.zip` from the repo root (or zip this folder).
2. Overleaf → New Project → Upload Project.
3. Set the main document to `main.tex` (Menu → Main document).
4. Compile with **pdfLaTeX** (default). BibTeX runs automatically on Overleaf.

## Submission mode (default)

```latex
\usepackage[dblblindworkshop]{neurips_2026}
\workshoptitle{NeurIPS 2026 Workshop}
```

Edit `\workshoptitle{...}` to your real workshop name before submitting
(e.g. VerifyAgents).

Acknowledgments / funding (`\begin{ack}...`) are hidden in anonymous mode and
appear with the `final` option.

## Camera-ready (after acceptance)

```latex
\usepackage[dblblindworkshop, final]{neurips_2026}
```

## Files

| File | Role |
|------|------|
| `main.tex` | Paper (scaled 150Q / 7-condition revision + Phase 2–4 addenda) |
| `references.bib` | Cited works |
| `figures/fig1`–`fig6` | Results figures (pass rate, Pareto, latency, stage heatmap, P4 confusion, failure types) |
| `checklist.tex` | NeurIPS checklist (if used) |
| `neurips_2026.sty` | Official style |
