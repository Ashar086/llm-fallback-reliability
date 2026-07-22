"""P3 — Graceful degradation (skip-plan → cheap model → partial+flag)."""

from __future__ import annotations

from typing import Any

import config
from pipeline.nodes import formatter_node, planner_node, retriever_node, synthesizer_node
from pipeline.strategies.tool_grounded_retry import verify_stage

STAGE_ORDER = ["planner", "retriever", "synthesizer", "formatter"]
STAGE_FNS = {
    "planner": planner_node,
    "retriever": retriever_node,
    "synthesizer": synthesizer_node,
    "formatter": formatter_node,
}


def _append_event(state: dict[str, Any], **fields: Any) -> None:
    logs = list(state.get("stage_logs") or [])
    logs.append(
        {
            "stage": fields.get("stage", "degrade"),
            "input": fields.get("input"),
            "output": fields.get("output"),
            "latency_ms": float(fields.get("latency_ms") or 0.0),
            "input_tokens": 0,
            "output_tokens": 0,
            "error": fields.get("error"),
            "event": fields.get("event"),
            "verification_reason": fields.get("verification_reason"),
            "degradation_tier": fields.get("degradation_tier"),
            "low_confidence": fields.get("low_confidence"),
            "attempt": fields.get("attempt"),
            "model": fields.get("model"),
        }
    )
    state["stage_logs"] = logs


def _token_total(state: dict[str, Any]) -> int:
    return sum(
        int(s.get("input_tokens") or 0) + int(s.get("output_tokens") or 0)
        for s in (state.get("stage_logs") or [])
    )


def _merge(state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = {**state, **update}
    if "stage_logs" in update:
        merged["stage_logs"] = update["stage_logs"]
    return merged


def _run_stage(
    state: dict[str, Any],
    stage_name: str,
    *,
    feedback: str | None = None,
    expand: bool = False,
) -> dict[str, Any]:
    working = {
        **state,
        "failed": False,
        "failure_reason": None,
        "retry_feedback": feedback,
        "retriever_expand": expand,
    }
    update = STAGE_FNS[stage_name](working)
    merged = _merge(working, update)
    # Tag model on latest log if LLM stage
    if stage_name in {"planner", "synthesizer", "formatter"}:
        logs = list(merged.get("stage_logs") or [])
        if logs:
            last = dict(logs[-1])
            last["model"] = state.get("model_override") or config.MODEL_NAME
            logs[-1] = last
            merged["stage_logs"] = logs
    return merged


def _run_stage_with_retries(
    state: dict[str, Any], stage_name: str, max_retries: int
) -> tuple[dict[str, Any], str | None]:
    """P1-style tool-grounded retries; returns (state, unresolved_reason|None)."""
    feedback: str | None = None
    expand = False
    last_reason: str | None = None

    for attempt in range(1, max_retries + 2):
        if _token_total(state) > config.P3_TOKEN_BUDGET:
            return state, "TOKEN_BUDGET_EXCEEDED"

        state = _run_stage(state, stage_name, feedback=feedback, expand=expand)
        logs = list(state.get("stage_logs") or [])
        if logs:
            last = dict(logs[-1])
            last["attempt"] = attempt
            logs[-1] = last
            state["stage_logs"] = logs

        reason = verify_stage(stage_name, state, state)
        if reason is None and not state.get("failed"):
            return state, None

        last_reason = reason or state.get("failure_reason") or f"{stage_name} failed"
        if attempt > max_retries:
            return state, last_reason

        feedback = last_reason
        expand = stage_name == "retriever" and (
            last_reason.startswith("EMPTY_RETRIEVAL")
            or last_reason.startswith("LOW_RELEVANCE")
        )
        state["failed"] = False
        state["failure_reason"] = None

    return state, last_reason


def _emit_partial(state: dict[str, Any], reason: str) -> dict[str, Any]:
    """Tier 3: partial answer + low_confidence flag (still scorable)."""
    draft = (state.get("draft_answer") or "").strip()
    final = (state.get("final_answer") or draft or "").strip()
    if not final:
        final = (
            f"Unable to complete multi-hop QA with high confidence. "
            f"Partial context: question={state.get('question')!r}."
        )
    citations = list(state.get("citations") or state.get("draft_citations") or [])
    state["final_answer"] = final
    state["citations"] = citations
    state["confidence"] = min(float(state.get("confidence") or 0.25), 0.25)
    state["formatted_output"] = {
        "final_answer": final,
        "citations": citations,
        "confidence": state["confidence"],
        "low_confidence": True,
    }
    state["low_confidence"] = True
    state["degradation_tier"] = 3
    state["failed"] = False
    state["failure_reason"] = None
    _append_event(
        state,
        stage="degrade",
        event="degrade_tier_3_partial",
        degradation_tier=3,
        low_confidence=True,
        verification_reason=reason,
        output={"final_answer": final},
    )
    return state


def _run_suffix(
    state: dict[str, Any],
    stages: list[str],
    *,
    max_retries: int,
) -> tuple[dict[str, Any], str | None]:
    for stage_name in stages:
        if _token_total(state) > config.P3_TOKEN_BUDGET:
            return state, "TOKEN_BUDGET_EXCEEDED"
        state, reason = _run_stage_with_retries(state, stage_name, max_retries)
        if reason is not None:
            return state, reason
    return state, None


def run_degraded_pipeline(item: dict[str, Any]) -> dict[str, Any]:
    """Normal path with P1-style retries; on exhaustion/budget, degrade tiers 1→2→3."""
    state: dict[str, Any] = {
        "question_id": item["id"],
        "question": item["question"],
        "gold_answer": item["gold_answer"],
        "supporting_doc_ids": list(item.get("supporting_doc_ids") or []),
        "stage_logs": [],
        "failed": False,
        "condition": "P3",
        "retry_feedback": None,
        "retriever_expand": False,
        "model_override": None,
        "degradation_tier": 0,
        "low_confidence": False,
        "skip_planner": False,
    }

    max_retries = config.P3_MAX_RETRIES

    # --- Tier 0: full multi-hop path ---
    state, reason = _run_suffix(state, STAGE_ORDER, max_retries=max_retries)
    if reason is None:
        state["degradation_tier"] = 0
        return state

    # --- Tier 1: skip multi-hop planning ---
    _append_event(
        state,
        stage="degrade",
        event="degrade_tier_1_skip_planner",
        degradation_tier=1,
        verification_reason=reason,
        input={"trigger": reason, "token_total": _token_total(state)},
    )
    state["degradation_tier"] = 1
    state["skip_planner"] = True
    state["sub_questions"] = [state["question"]]  # single retrieve+answer pass
    state["failed"] = False
    state["failure_reason"] = None
    # Clear downstream outputs from failed tier-0 attempt
    for k in (
        "retrieved_docs",
        "draft_answer",
        "draft_citations",
        "final_answer",
        "citations",
        "confidence",
        "formatted_output",
    ):
        state.pop(k, None)

    state, reason = _run_suffix(
        state, ["retriever", "synthesizer", "formatter"], max_retries=max_retries
    )
    if reason is None:
        return state

    # --- Tier 2: cheap model for remaining stages ---
    _append_event(
        state,
        stage="degrade",
        event="degrade_tier_2_cheap_model",
        degradation_tier=2,
        verification_reason=reason,
        model=config.CHEAP_MODEL_NAME,
        input={"trigger": reason, "token_total": _token_total(state)},
    )
    state["degradation_tier"] = 2
    state["model_override"] = config.CHEAP_MODEL_NAME
    state["failed"] = False
    state["failure_reason"] = None
    # Keep sub_questions; refresh retrieve→format on cheap model
    for k in (
        "retrieved_docs",
        "draft_answer",
        "draft_citations",
        "final_answer",
        "citations",
        "confidence",
        "formatted_output",
    ):
        state.pop(k, None)

    if not state.get("sub_questions"):
        state["sub_questions"] = [state["question"]]

    state, reason = _run_suffix(
        state, ["retriever", "synthesizer", "formatter"], max_retries=max_retries
    )
    if reason is None:
        return state

    # --- Tier 3: partial + low_confidence (not a hard pipeline failure) ---
    return _emit_partial(state, reason or "degraded_partial")
