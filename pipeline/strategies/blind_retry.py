"""B1 — Blind retry strawman (no new information on retry)."""

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


def wrap_blind_retry(stage_name: str, node_fn: Callable) -> Callable:
    """Re-run the same stage with identical inputs on hard-fail; no new feedback.

    Cap: config.B1_MAX_RETRIES additional attempts after the first.
    Every attempt is logged (attempt index) so cost/latency include all burns.
    """

    max_retries = config.B1_MAX_RETRIES

    def wrapped(state: PipelineState) -> dict[str, Any]:
        if state.get("failed"):
            return {}

        accumulated_logs = list(state.get("stage_logs") or [])
        last_update: dict[str, Any] = {}

        for attempt in range(1, max_retries + 2):  # 1..max_retries+1
            working: dict[str, Any] = {
                **state,
                **{k: v for k, v in last_update.items() if k != "stage_logs"},
                "stage_logs": accumulated_logs,
                "failed": False,
                "failure_reason": None,
                # Blind: never inject feedback or expand retrieval
                "retry_feedback": None,
                "retriever_expand": False,
            }
            update = node_fn(working)
            new_logs = list(update.get("stage_logs") or accumulated_logs)
            new_logs = _tag_last_log(
                new_logs,
                attempt=attempt,
                verification_reason=(
                    "blind_retry_after_hard_fail" if attempt > 1 else None
                ),
            )
            accumulated_logs = new_logs
            last_update = {**update, "stage_logs": accumulated_logs}

            if not update.get("failed"):
                return {
                    **last_update,
                    "failed": False,
                    "failure_reason": None,
                    "stage_logs": accumulated_logs,
                    "retry_feedback": None,
                }

            # Hard-fail: retry same stage with same inputs (no new info)
            if attempt > max_retries:
                break

        return {
            **last_update,
            "failed": True,
            "failure_reason": last_update.get("failure_reason")
            or f"{stage_name}: blind retry exhausted",
            "stage_logs": accumulated_logs,
        }

    wrapped.__name__ = f"blind_retry_{stage_name}"
    return wrapped
