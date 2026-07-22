"""Scoring utilities for the multi-hop QA testbed."""

from __future__ import annotations

import re
from typing import Protocol


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def exact_match_or_substring(prediction: str, gold: str) -> bool:
    """Pass if prediction matches gold, contains it, or covers all gold tokens.

    Placeholder scorer for the B0 scaffold. Handles verbose model answers
    against short gold phrases (e.g. gold "Neil Armstrong, Ohio" inside a
    full sentence). Replace via `get_scorer()` for the 100–200 question set.
    """
    if not prediction or not gold:
        return False
    p = _normalize(prediction)
    g = _normalize(gold)
    if not p or not g:
        return False
    if p == g or g in p or p in g:
        return True
    # Token coverage: every gold token appears in the prediction
    g_tokens = g.split()
    p_tokens = set(p.split())
    return bool(g_tokens) and all(t in p_tokens for t in g_tokens)


class Scorer(Protocol):
    def __call__(self, prediction: str, gold: str) -> bool: ...


def get_scorer(name: str = "exact_substring") -> Scorer:
    """Extension point for later scorers (e.g. LLM-judge).

    Currently only ``exact_substring`` is implemented. Add branches here
    (e.g. ``llm_judge``) without changing call sites in run_pipeline.py.
    """
    if name == "exact_substring":
        return exact_match_or_substring
    # Future: if name == "llm_judge": return llm_judge_scorer
    raise ValueError(f"Unknown scorer: {name!r}. Available: exact_substring")
