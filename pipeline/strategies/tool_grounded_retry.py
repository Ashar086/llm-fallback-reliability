"""P1 — Tool-grounded retry-with-verification (CRITIC-style external feedback)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import config
from pipeline.state import PipelineState


def _tag_last_log(
    logs: list[dict[str, Any]],
    *,
    attempt: int,
    verification_reason: str | None = None,
) -> list[dict[str, Any]]:
    if not logs:
        return logs
    tagged = list(logs)
    last = dict(tagged[-1])
    last["attempt"] = attempt
    if verification_reason is not None:
        last["verification_reason"] = verification_reason
    tagged[-1] = last
    return tagged


def verify_stage(
    stage_name: str, state: PipelineState, update: dict[str, Any]
) -> str | None:
    """Return a concrete verification_reason if the stage output fails an external check.

    Feedback is always a checkable fact (empty retrieval, citation ∉ retrieved set,
    schema/parse failure) — never generic self-critique.
    """
    if update.get("failed"):
        reason = update.get("failure_reason") or f"{stage_name}: hard failure"
        # Schema / JSON parse failures are externally checkable
        if "malformed" in reason.lower() or "expecting value" in reason.lower():
            return (
                f"SCHEMA_VIOLATION: {reason}. "
                "Respond with ONLY valid JSON matching the required schema; "
                "no prose outside the JSON object."
            )
        return f"HARD_FAIL: {reason}"

    if stage_name == "retriever":
        docs = update.get("retrieved_docs") or []
        if not docs:
            return (
                "EMPTY_RETRIEVAL: 0 documents returned for the sub-questions. "
                "Expanding search (higher top_k + original question query)."
            )
        max_score = max((float(d.get("score") or 0.0) for d in docs), default=0.0)
        if max_score < config.RETRIEVER_MIN_SCORE:
            return (
                f"LOW_RELEVANCE: max retrieval score {max_score:.4f} "
                f"< threshold {config.RETRIEVER_MIN_SCORE}. "
                "Expanding search (higher top_k + original question query)."
            )
        return None

    if stage_name == "synthesizer":
        retrieved_ids = {d["doc_id"] for d in (state.get("retrieved_docs") or [])}
        citations = list(update.get("draft_citations") or [])
        missing = sorted({c for c in citations if c not in retrieved_ids})
        if missing:
            allowed = sorted(retrieved_ids) or ["(none)"]
            return (
                f"UNGROUNDED_CITATIONS: citations {missing} are not in the retrieved "
                f"document set. Regenerate draft_citations using ONLY IDs from: {allowed}."
            )
        return None

    if stage_name == "formatter":
        final_answer = update.get("final_answer")
        citations = update.get("citations")
        confidence = update.get("confidence")
        problems = []
        if not isinstance(final_answer, str) or not final_answer.strip():
            problems.append("final_answer must be a non-empty string")
        if not isinstance(citations, list):
            problems.append("citations must be a list of doc_id strings")
        if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
            problems.append("confidence must be a float in [0, 1]")
        # Citation grounding vs retrieved set
        retrieved_ids = {d["doc_id"] for d in (state.get("retrieved_docs") or [])}
        if isinstance(citations, list) and retrieved_ids:
            missing = sorted({str(c) for c in citations if str(c) not in retrieved_ids})
            if missing:
                problems.append(
                    f"citations {missing} not in retrieved set {sorted(retrieved_ids)}"
                )
        if problems:
            return "SCHEMA_VIOLATION: " + "; ".join(problems)
        return None

    if stage_name == "planner":
        subs = update.get("sub_questions") or []
        if not isinstance(subs, list) or not subs:
            return (
                "SCHEMA_VIOLATION: sub_questions must be a non-empty JSON list of strings."
            )
        return None

    return None


def wrap_tool_grounded_retry(stage_name: str, node_fn: Callable) -> Callable:
    """Re-run only the failed stage with concrete external tool/schema feedback.

    Cap: config.P1_MAX_RETRIES additional attempts after the first.
    """

    max_retries = config.P1_MAX_RETRIES

    def wrapped(state: PipelineState) -> dict[str, Any]:
        if state.get("failed"):
            return {}

        accumulated_logs = list(state.get("stage_logs") or [])
        last_update: dict[str, Any] = {}
        feedback: str | None = None
        expand = False

        for attempt in range(1, max_retries + 2):
            working: dict[str, Any] = {
                **state,
                **{k: v for k, v in last_update.items() if k != "stage_logs"},
                "stage_logs": accumulated_logs,
                "failed": False,
                "failure_reason": None,
                "retry_feedback": feedback,
                "retriever_expand": expand,
            }
            update = node_fn(working)
            new_logs = list(update.get("stage_logs") or accumulated_logs)

            reason = verify_stage(stage_name, working, update)
            new_logs = _tag_last_log(
                new_logs,
                attempt=attempt,
                verification_reason=reason,
            )
            accumulated_logs = new_logs
            last_update = {**update, "stage_logs": accumulated_logs}

            if reason is None:
                return {
                    **last_update,
                    "failed": False,
                    "failure_reason": None,
                    "retry_feedback": None,
                    "retriever_expand": False,
                    "stage_logs": accumulated_logs,
                }

            # Verification failed — prepare tool-grounded retry
            if attempt > max_retries:
                return {
                    **last_update,
                    "failed": True,
                    "failure_reason": (
                        f"{stage_name}: verification failed after {max_retries} "
                        f"tool-grounded retries — {reason}"
                    ),
                    "retry_feedback": None,
                    "retriever_expand": False,
                    "stage_logs": accumulated_logs,
                }

            feedback = reason
            # Retriever has no LLM prompt: expand search parameters as tool recovery
            expand = stage_name == "retriever" and (
                reason.startswith("EMPTY_RETRIEVAL") or reason.startswith("LOW_RELEVANCE")
            )
            # Clear failed so the next node_fn call runs; keep prior outputs until replaced
            last_update = {
                **last_update,
                "failed": False,
                "failure_reason": None,
            }

        return {
            **last_update,
            "failed": True,
            "failure_reason": f"{stage_name}: tool-grounded retry exhausted",
            "stage_logs": accumulated_logs,
        }

    wrapped.__name__ = f"tool_grounded_{stage_name}"
    return wrapped
