"""Pipeline stage nodes: Planner → Retriever → Synthesizer → Formatter.

B0: no retries, no rollback, no degradation. On error, record failure and stop.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from pipeline.llm import call_claude
from pipeline.retriever import get_retriever
from pipeline.state import PipelineState, RetrievedDoc, StageLog

import config


def _model_for(state: PipelineState) -> str | None:
    """Optional per-run model override (P3 cheap tier); None → config.MODEL_NAME."""
    return state.get("model_override") or None


def _append_log(state: PipelineState, log: StageLog) -> list[StageLog]:
    logs = list(state.get("stage_logs") or [])
    logs.append(log)
    return logs


def _fail(state: PipelineState, stage: str, reason: str, **log_fields: Any) -> dict[str, Any]:
    log: StageLog = {
        "stage": stage,
        "input": log_fields.get("input"),
        "output": log_fields.get("output"),
        "latency_ms": float(log_fields.get("latency_ms", 0.0)),
        "input_tokens": int(log_fields.get("input_tokens", 0)),
        "output_tokens": int(log_fields.get("output_tokens", 0)),
        "error": reason,
    }
    return {
        "failed": True,
        "failure_reason": f"{stage}: {reason}",
        "stage_logs": _append_log(state, log),
    }


def _extract_json(text: str) -> Any:
    """Parse JSON from model output; tolerate optional markdown fences."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    return json.loads(cleaned)


def planner_node(state: PipelineState) -> dict[str, Any]:
    """Decompose the multi-hop question into sub-questions."""
    if state.get("failed"):
        return {}

    question = state["question"]
    system = (
        "You are the Planner in a multi-hop QA pipeline. "
        "Decompose the user's question into 2–4 concrete sub-questions that "
        "can be answered independently from a document corpus. "
        'Respond with ONLY valid JSON: {"sub_questions": ["...", "..."]}.'
    )
    user = f"Question: {question}"
    feedback = state.get("retry_feedback")
    if feedback:
        user = f"{user}\n\nTool feedback (must address):\n{feedback}"

    try:
        result = call_claude(system, user, model=_model_for(state))
        parsed = _extract_json(result.text)
        sub_questions = parsed.get("sub_questions")
        if not isinstance(sub_questions, list) or not sub_questions:
            return _fail(
                state,
                "planner",
                "malformed output: missing sub_questions list",
                input={"question": question},
                output=result.text,
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
        sub_questions = [str(q).strip() for q in sub_questions if str(q).strip()]
        log: StageLog = {
            "stage": "planner",
            "input": {"question": question, "retry_feedback": feedback},
            "output": {"sub_questions": sub_questions},
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "error": None,
        }
        return {
            "sub_questions": sub_questions,
            "retry_feedback": None,
            "stage_logs": _append_log(state, log),
        }
    except Exception as exc:  # B0: catch only to record failure cleanly
        return _fail(
            state,
            "planner",
            str(exc),
            input={"question": question},
            output=None,
        )


def retriever_node(state: PipelineState) -> dict[str, Any]:
    """Retrieve top-k corpus docs for each sub-question (local keyword RAG)."""
    if state.get("failed"):
        return {}

    sub_questions = state.get("sub_questions") or []
    if not sub_questions:
        return _fail(state, "retriever", "no sub_questions to retrieve for")

    t0 = time.perf_counter()
    try:
        retriever = get_retriever()
        expand = bool(state.get("retriever_expand"))
        top_k = config.RETRIEVER_TOP_K * (2 if expand else 1)
        queries = list(sub_questions)
        if expand and state.get("question"):
            queries = [state["question"], *queries]
        retrieved: list[RetrievedDoc] = []
        seen: set[tuple[str, str]] = set()
        for sq in queries:
            for doc, score in retriever.search(sq, top_k=top_k):
                key = (sq, doc.doc_id)
                if key in seen:
                    continue
                seen.add(key)
                retrieved.append(
                    {
                        "doc_id": doc.doc_id,
                        "title": doc.title,
                        "text": doc.text,
                        "score": score,
                        "sub_question": sq,
                    }
                )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        log: StageLog = {
            "stage": "retriever",
            "input": {
                "sub_questions": sub_questions,
                "expand": expand,
                "top_k": top_k,
            },
            "output": {
                "n_docs": len(retrieved),
                "doc_ids": [d["doc_id"] for d in retrieved],
                "max_score": max((d["score"] for d in retrieved), default=0.0),
            },
            "latency_ms": latency_ms,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": None,
        }
        return {
            "retrieved_docs": retrieved,
            "retriever_expand": False,
            "retry_feedback": None,
            "stage_logs": _append_log(state, log),
        }
    except Exception as exc:
        return _fail(
            state,
            "retriever",
            str(exc),
            input={"sub_questions": sub_questions},
            output=None,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )


def synthesizer_node(state: PipelineState) -> dict[str, Any]:
    """Draft an answer with citations grounded in retrieved evidence."""
    if state.get("failed"):
        return {}

    question = state["question"]
    docs = state.get("retrieved_docs") or []
    evidence_blocks = []
    for d in docs:
        evidence_blocks.append(
            f"[{d['doc_id']}] {d['title']}\n{d['text']}\n(retrieved for: {d['sub_question']})"
        )
    evidence = "\n\n".join(evidence_blocks) if evidence_blocks else "(no documents retrieved)"

    system = (
        "You are the Synthesizer in a multi-hop QA pipeline. "
        "Using ONLY the provided evidence documents, draft a concise answer. "
        "Cite documents by their doc_id in square brackets, e.g. [doc_01]. "
        "If evidence is insufficient, still give your best short answer and "
        "list whatever citations you used. "
        'Respond with ONLY valid JSON: '
        '{"draft_answer": "...", "draft_citations": ["doc_id", ...]}.'
    )
    user = f"Question: {question}\n\nEvidence:\n{evidence}"
    feedback = state.get("retry_feedback")
    if feedback:
        user = f"{user}\n\nTool feedback (must address):\n{feedback}"

    try:
        result = call_claude(system, user, model=_model_for(state))
        parsed = _extract_json(result.text)
        draft_answer = parsed.get("draft_answer")
        draft_citations = parsed.get("draft_citations", [])
        if not isinstance(draft_answer, str) or not draft_answer.strip():
            return _fail(
                state,
                "synthesizer",
                "malformed output: missing draft_answer",
                input={"question": question, "n_docs": len(docs)},
                output=result.text,
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
        if not isinstance(draft_citations, list):
            draft_citations = []
        draft_citations = [str(c) for c in draft_citations]
        log: StageLog = {
            "stage": "synthesizer",
            "input": {
                "question": question,
                "n_docs": len(docs),
                "retry_feedback": feedback,
            },
            "output": {
                "draft_answer": draft_answer,
                "draft_citations": draft_citations,
            },
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "error": None,
        }
        return {
            "draft_answer": draft_answer.strip(),
            "draft_citations": draft_citations,
            "retry_feedback": None,
            "stage_logs": _append_log(state, log),
        }
    except Exception as exc:
        return _fail(
            state,
            "synthesizer",
            str(exc),
            input={"question": question, "n_docs": len(docs)},
            output=None,
        )


def formatter_node(state: PipelineState) -> dict[str, Any]:
    """Emit structured JSON: final_answer, citations, confidence."""
    if state.get("failed"):
        return {}

    draft_answer = state.get("draft_answer") or ""
    draft_citations = state.get("draft_citations") or []
    n_docs = len(state.get("retrieved_docs") or [])

    system = (
        "You are the Formatter in a multi-hop QA pipeline. "
        "Convert the draft into a final structured answer. "
        "confidence must be a float in [0, 1]. "
        "Respond with ONLY valid JSON: "
        '{"final_answer": "...", "citations": ["doc_id", ...], "confidence": 0.0}.'
    )
    user = (
        f"Draft answer: {draft_answer}\n"
        f"Draft citations: {json.dumps(draft_citations)}\n"
        f"Number of retrieved docs: {n_docs}"
    )
    feedback = state.get("retry_feedback")
    if feedback:
        user = f"{user}\n\nTool feedback (must address):\n{feedback}"

    try:
        result = call_claude(system, user, model=_model_for(state))
        parsed = _extract_json(result.text)
        final_answer = parsed.get("final_answer")
        citations = parsed.get("citations", draft_citations)
        confidence = parsed.get("confidence", 0.5)
        if not isinstance(final_answer, str) or not final_answer.strip():
            return _fail(
                state,
                "formatter",
                "malformed output: missing final_answer",
                input={"draft_answer": draft_answer},
                output=result.text,
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
        if not isinstance(citations, list):
            citations = list(draft_citations)
        citations = [str(c) for c in citations]
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        formatted = {
            "final_answer": final_answer.strip(),
            "citations": citations,
            "confidence": confidence,
        }
        log: StageLog = {
            "stage": "formatter",
            "input": {
                "draft_answer": draft_answer,
                "draft_citations": draft_citations,
                "retry_feedback": feedback,
            },
            "output": formatted,
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "error": None,
        }
        return {
            "final_answer": formatted["final_answer"],
            "citations": citations,
            "confidence": confidence,
            "formatted_output": formatted,
            "retry_feedback": None,
            "stage_logs": _append_log(state, log),
        }
    except Exception as exc:
        return _fail(
            state,
            "formatter",
            str(exc),
            input={"draft_answer": draft_answer},
            output=None,
        )
