"""Thin Anthropic Claude wrapper used by all pipeline stages."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass

from dotenv import load_dotenv

import config

load_dotenv()

# Offline smoke-test mode: python run_pipeline.py --mock
USE_MOCK_LLM = os.environ.get("MOCK_LLM", "").strip().lower() in {"1", "true", "yes"}


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


_client = None


def get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic

        _client = Anthropic()
    return _client


def _mock_call(system: str, user: str) -> LLMResult:
    """Deterministic stand-in so the B0 graph can be smoke-tested without API keys."""
    t0 = time.perf_counter()
    sys_l = system.lower()
    if "planner" in sys_l:
        q = user.replace("Question:", "").strip()
        text = json.dumps(
            {
                "sub_questions": [
                    f"What is the first fact needed for: {q[:60]}",
                    f"What is the second fact needed for: {q[:60]}",
                ]
            }
        )
    elif "synthesizer" in sys_l:
        cites = re.findall(r"\[(doc_\d+)\]", user)
        cite_list = list(dict.fromkeys(cites))[:3] or ["doc_01"]
        # Lightweight heuristics so --mock can exercise scoring against placeholder golds
        draft = "Mock synthesized answer based on retrieved evidence."
        u = user.lower()
        if "armstrong" in u and "ohio" in u:
            draft = "Neil Armstrong, Ohio"
        elif "chlorophyll" in u and ("blue" in u or "red" in u):
            draft = "Chlorophyll, blue and red"
        elif "guido" in u or ("python" in u and "1991" in u):
            draft = "Guido van Rossum, 1991"
        elif "andes" in u and "south america" in u:
            draft = "Andes, South America"
        elif "april 30" in u or ("hitler" in u and "ve day" in u):
            draft = "April 30, 1945, VE Day"
        elif "marie curie" in u or ("physics" in u and "chemistry" in u and "nobel" in u):
            draft = "Physics and Chemistry, Alfred Nobel"
        elif "ming" in u:
            draft = "Ming Dynasty, 1368–1644"
        elif "turing" in u:
            draft = "Turing Award, Alan Turing"
        text = json.dumps({"draft_answer": draft, "draft_citations": cite_list})
    elif "formatter" in sys_l:
        m = re.search(r"Draft answer:\s*(.+)", user)
        ans = m.group(1).strip().split("\n")[0] if m else "Mock answer"
        cites = re.findall(r'"(doc_\d+)"', user)
        text = json.dumps(
            {
                "final_answer": ans,
                "citations": cites or ["doc_01"],
                "confidence": 0.5,
            }
        )
    else:
        text = json.dumps({"ok": True})
    latency_ms = (time.perf_counter() - t0) * 1000.0
    return LLMResult(
        text=text,
        input_tokens=len(user.split()),
        output_tokens=len(text.split()),
        latency_ms=latency_ms,
    )


def call_claude(system: str, user: str, model: str | None = None) -> LLMResult:
    """Call Claude with the configured (or overridden) model; return text + usage + latency."""
    if USE_MOCK_LLM:
        return _mock_call(system, user)

    use_model = model or config.MODEL_NAME
    client = get_client()
    t0 = time.perf_counter()
    response = client.messages.create(
        model=use_model,
        max_tokens=config.MAX_TOKENS,
        temperature=config.TEMPERATURE,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    latency_ms = (time.perf_counter() - t0) * 1000.0
    text_parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    return LLMResult(
        text="".join(text_parts).strip(),
        input_tokens=int(response.usage.input_tokens),
        output_tokens=int(response.usage.output_tokens),
        latency_ms=latency_ms,
    )
