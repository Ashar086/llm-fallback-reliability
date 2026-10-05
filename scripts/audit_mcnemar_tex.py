#!/usr/bin/env python3
"""Cross-check main.tex reported p-values vs paired_question_tests.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON = ROOT / "results_scaled" / "stats" / "paired_question_tests.json"
SUMMARY = ROOT / "results_scaled" / "stats" / "statistical_summary.md"
CSV = ROOT / "results_scaled" / "stats" / "paired_question_highlight.csv"
TEX = ROOT / "overleaf_neurips" / "main.tex"

# LaTeX uses \times; values must match JSON within rounding
EXPECTED_TEX = {
    "P1_vs_B0": ("1.06\\times 10^{-7}", 1.06e-7, 21.3),
    "P2_vs_B0": ("8.14\\times 10^{-7}", 8.14e-7, 20.7),
    "P3_vs_B0": ("5.43\\times 10^{-9}", 5.43e-9, 24.0),
    "P5_vs_B0": ("4.93\\times 10^{-7}", 4.93e-7, 19.3),
    "P4_vs_B0": ("7.23\\times 10^{-5}", 7.23e-5, 14.7),
    "B1_vs_B0": ("0.0265", 0.0265, 6.0),
    "P5_vs_P1": ("0.371", 0.371, -2.0),
    "P4_vs_P3": ("5.12\\times 10^{-4}", 5.12e-4, -9.3),
}

BANNED = [
    "strictly inferior",
    "reliability ceiling",
    "0.0789",
    "450 questions",
    "p < 0.001",
]


def main() -> None:
    data = json.loads(JSON.read_text(encoding="utf-8"))
    tex = TEX.read_text(encoding="utf-8")
    summary = SUMMARY.read_text(encoding="utf-8") if SUMMARY.exists() else ""
    csv = pd_read_csv() if CSV.exists() else None

    print("=== Banned phrase scan (main.tex) ===")
    for phrase in BANNED:
        hit = phrase.lower() in tex.lower()
        print(f"  {'FOUND' if hit else 'ok  '}: {phrase!r}")

    print("=== Banned phrase scan (statistical_summary.md) ===")
    if not summary:
        print("  MISSING summary file")
    else:
        # Active-claim bans (ignore the labeled Legacy z-test block)
        legacy_split = summary.split("## Legacy pooled z-tests")
        active = legacy_split[0]
        for phrase in BANNED + ["strictly dominated", "ceiling independent"]:
            hit = phrase.lower() in active.lower()
            print(f"  {'FOUND' if hit else 'ok  '}: {phrase!r} (active section)")
        if len(legacy_split) > 1 and "0.0789" in legacy_split[1]:
            print("  ok  : '0.0789' appears only in Legacy diagnostic block")
        for need in [
            "150 paired questions",
            "McNemar",
            "450 logged runs",
            "Appendix-only",
            "Legacy pooled z-tests",
            "McNemar-aligned",
        ]:
            print(f"  {'OK' if need in summary else 'MISSING'}: summary has {need!r}")

    print("=== Highlight pairs (JSON vs paper / CSV) ===")
    for key, (tex_s, p_exp, dpp_exp) in EXPECTED_TEX.items():
        row = data["highlight_pairs"][key]
        p = row["mcnemar_p"]
        dpp = row["delta_pp_majority"]
        p_ok = abs(p - p_exp) / max(p_exp, 1e-20) < 0.02 or abs(p - p_exp) < 5e-4
        dpp_ok = abs(dpp - dpp_exp) < 0.15
        tex_ok = tex_s in tex
        print(
            f"  {key}: JSON p={p:.4g} dpp={dpp:+.1f} | "
            f"p_match={p_ok} dpp_match={dpp_ok} tex={tex_ok}"
        )
        if csv is not None:
            a, b = key.split("_vs_")
            crow = csv[(csv.condition_a == a) & (csv.condition_b == b)]
            if len(crow) == 1:
                cd = float(crow.iloc[0]["delta_pp_majority"])
                cp = float(crow.iloc[0]["mcnemar_p"])
                print(f"         CSV dpp={cd:+.1f} p={cp:.4g} csv_dpp_ok={abs(cd-dpp)<0.15}")


def pd_read_csv():
    import pandas as pd

    return pd.read_csv(CSV)


if __name__ == "__main__":
    main()
