"""P2 — Deterministic checkpointing with rollback to last trusted state."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
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
# Fields produced by each stage (cleared when rolling back past that stage)
STAGE_OUTPUT_KEYS = {
    "planner": ["sub_questions"],
    "retriever": ["retrieved_docs"],
    "synthesizer": ["draft_answer", "draft_citations"],
    "formatter": [
        "final_answer",
        "citations",
        "confidence",
        "formatted_output",
    ],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens_in_logs(logs: list[dict[str, Any]]) -> int:
    return sum(
        int(s.get("input_tokens") or 0) + int(s.get("output_tokens") or 0) for s in logs
    )


def _snapshot_state(state: dict[str, Any], after_stage: str) -> dict[str, Any]:
    """Immutable checkpoint: stage boundary + deep-copied trusted fields."""
    keep = {
        "question_id",
        "question",
        "gold_answer",
        "supporting_doc_ids",
        "condition",
        "sub_questions",
        "retrieved_docs",
        "draft_answer",
        "draft_citations",
        "final_answer",
        "citations",
        "confidence",
        "formatted_output",
    }
    snap = {k: copy.deepcopy(state[k]) for k in keep if k in state}
    return {
        "after_stage": after_stage,
        "timestamp": _now(),
        "state": snap,
    }


def _restore_from_checkpoint(
    base: dict[str, Any], checkpoint: dict[str, Any] | None
) -> dict[str, Any]:
    """Discard outputs after the checkpoint stage; restore trusted snapshot."""
    restored = {
        "question_id": base["question_id"],
        "question": base["question"],
        "gold_answer": base["gold_answer"],
        "supporting_doc_ids": list(base.get("supporting_doc_ids") or []),
        "condition": "P2",
        "stage_logs": list(base.get("stage_logs") or []),
        "failed": False,
        "failure_reason": None,
        "retry_feedback": None,
        "retriever_expand": False,
        "model_override": None,
        "checkpoints": list(base.get("checkpoints") or []),
        "rollback_count": int(base.get("rollback_count") or 0),
        "degradation_tier": 0,
        "low_confidence": False,
    }
    if checkpoint is None:
        return restored

    snap = copy.deepcopy(checkpoint["state"])
    restored.update(snap)
    after = checkpoint["after_stage"]
    # Clear outputs of stages after the checkpoint boundary
    if after in STAGE_ORDER:
        idx = STAGE_ORDER.index(after)
        for stage in STAGE_ORDER[idx + 1 :]:
            for key in STAGE_OUTPUT_KEYS[stage]:
                restored.pop(key, None)
    return restored


def _append_event(state: dict[str, Any], **fields: Any) -> None:
    logs = list(state.get("stage_logs") or [])
    logs.append(
        {
            "stage": fields.get("stage", "checkpoint"),
            "input": fields.get("input"),
            "output": fields.get("output"),
            "latency_ms": float(fields.get("latency_ms") or 0.0),
            "input_tokens": 0,
            "output_tokens": 0,
            "error": fields.get("error"),
            "event": fields.get("event"),
            "verification_reason": fields.get("verification_reason"),
            "attempt": fields.get("attempt"),
        }
    )
    state["stage_logs"] = logs


def _merge_update(state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = {**state, **update}
    # Prefer update's stage_logs (node already appended)
    if "stage_logs" in update:
        merged["stage_logs"] = update["stage_logs"]
    return merged


def _run_stage(
    state: dict[str, Any], stage_name: str, *, feedback: str | None = None
) -> dict[str, Any]:
    working = {
        **state,
        "failed": False,
        "failure_reason": None,
        "retry_feedback": feedback,
        "retriever_expand": bool(
            feedback
            and stage_name == "retriever"
            and (
                feedback.startswith("EMPTY_RETRIEVAL")
                or feedback.startswith("LOW_RELEVANCE")
            )
        ),
    }
    update = STAGE_FNS[stage_name](working)
    return _merge_update(working, update)


def run_checkpointed_pipeline(item: dict[str, Any]) -> dict[str, Any]:
    """Execute planner→…→formatter with checkpoints and capped rollbacks.

    On verification/hard fail at stage i: restore last checkpoint, re-execute
    from the stage *after* that checkpoint through the end (one-shot hint on
    the immediate next stage only). Cap: CHECKPOINT_MAX_ROLLBACKS cycles.
    """
    state: dict[str, Any] = {
        "question_id": item["id"],
        "question": item["question"],
        "gold_answer": item["gold_answer"],
        "supporting_doc_ids": list(item.get("supporting_doc_ids") or []),
        "stage_logs": [],
        "failed": False,
        "condition": "P2",
        "checkpoints": [],
        "rollback_count": 0,
        "retry_feedback": None,
        "retriever_expand": False,
        "model_override": None,
        "degradation_tier": 0,
        "low_confidence": False,
    }

    max_rollbacks = config.CHECKPOINT_MAX_ROLLBACKS
    # Pointer into STAGE_ORDER; may rewind on rollback
    i = 0
    one_shot_hint: str | None = None

    while i < len(STAGE_ORDER):
        stage_name = STAGE_ORDER[i]
        hint = one_shot_hint
        one_shot_hint = None  # consume once

        before_logs = len(state.get("stage_logs") or [])
        state = _run_stage(state, stage_name, feedback=hint)
        # Tag latest stage log attempt
        logs = list(state.get("stage_logs") or [])
        if len(logs) > before_logs:
            last = dict(logs[-1])
            last["attempt"] = int(state.get("rollback_count") or 0) + 1
            if hint:
                last["verification_reason"] = hint
            logs[-1] = last
            state["stage_logs"] = logs

        reason = verify_stage(stage_name, state, state)
        if reason is None and not state.get("failed"):
            # Trusted — save checkpoint
            cp = _snapshot_state(state, after_stage=stage_name)
            cps = list(state.get("checkpoints") or [])
            cps.append(cp)
            state["checkpoints"] = cps
            _append_event(
                state,
                stage="checkpoint",
                event="checkpoint_save",
                input={"after_stage": stage_name},
                output={"timestamp": cp["timestamp"], "n_checkpoints": len(cps)},
            )
            i += 1
            continue

        # Failure — rollback if budget remains
        rollbacks = int(state.get("rollback_count") or 0)
        if rollbacks >= max_rollbacks:
            state["failed"] = True
            state["failure_reason"] = (
                f"{stage_name}: verification failed after {max_rollbacks} "
                f"rollback cycles — {reason or state.get('failure_reason')}"
            )
            _append_event(
                state,
                stage=stage_name,
                event="rollback_exhausted",
                error=state["failure_reason"],
                verification_reason=reason,
            )
            break

        checkpoints = list(state.get("checkpoints") or [])
        last_cp = checkpoints[-1] if checkpoints else None
        from_stage = stage_name
        to_stage = last_cp["after_stage"] if last_cp else "(initial)"

        state["rollback_count"] = rollbacks + 1
        _append_event(
            state,
            stage="checkpoint",
            event="rollback",
            input={"from_stage": from_stage, "to_checkpoint": to_stage},
            output={"rollback_count": state["rollback_count"]},
            verification_reason=reason,
            error=reason,
        )

        # Discard untrusted suffix; restore last trusted snapshot
        logs_keep = list(state.get("stage_logs") or [])
        rb_count = state["rollback_count"]
        cps_keep = list(checkpoints)  # keep history of checkpoints
        state = _restore_from_checkpoint(state, last_cp)
        state["stage_logs"] = logs_keep
        state["rollback_count"] = rb_count
        state["checkpoints"] = cps_keep

        # Re-execute from stage after checkpoint (or from planner if none)
        if last_cp is None:
            i = 0
        else:
            i = STAGE_ORDER.index(last_cp["after_stage"]) + 1
        one_shot_hint = reason  # only for the immediate next stage run
        if i >= len(STAGE_ORDER):
            # Failed on a stage with no forward work — treat as exhausted
            state["failed"] = True
            state["failure_reason"] = reason or "rollback with nowhere to re-execute"
            break

    if not state.get("failed") and not state.get("final_answer"):
        state["failed"] = True
        state["failure_reason"] = state.get("failure_reason") or "incomplete pipeline"

    # Drop bulky checkpoint payloads from returned state (already logged events)
    # but keep count metadata for debugging
    state["checkpoint"] = {
        "n_saved": len(state.get("checkpoints") or []),
        "rollback_count": int(state.get("rollback_count") or 0),
    }
    return state
