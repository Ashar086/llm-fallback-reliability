# Overleaf / NeurIPS 2026 LaTeX project

Official NeurIPS 2026 style (`neurips_2026.sty`) with paper content matching
`../full_draft.md`.

**Authors:** Muhammad Ashar Ishfaq, Muhammad Asad Ishfaq (The Islamia University
of Bahawalpur). Hidden under `dblblindworkshop` until camera-ready `final`.

## Upload to Overleaf

1. Zip the contents of this folder (or upload files individually).
2. Overleaf → New Project → Upload Project.
3. Set the main document to `main.tex` (Menu → Main document).
4. Compile with **pdfLaTeX** (default). BibTeX runs automatically on Overleaf.

## Submission mode (default)

```latex
\usepackage[dblblindworkshop]{neurips_2026}
\workshoptitle{NeurIPS 2026 Workshop}
```

Edit `\workshoptitle{...}` to your real workshop name before submitting.

Acknowledgments / funding (`\begin{ack}...`) are hidden in anonymous mode and
appear with the `final` option.

## Camera-ready (after acceptance)

```latex
\usepackage[dblblindworkshop, final]{neurips_2026}
```

## Files

| File | Role |
|------|------|
| `main.tex` | Paper |
| `references.bib` | 13 cited works |
| `neurips_2026.sty` | Official NeurIPS 2026 style |
| `figures/` | Fig 1–3 PNGs |
| `checklist.tex` | Official checklist (optional; include if your venue requires it) |
