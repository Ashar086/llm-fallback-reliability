"""LangGraph wiring for multi-agent QA.

Graph topology is fixed: planner → retriever → synthesizer → formatter → END

Conditions (B0/B1/P1) differ only by which strategy wraps each node — not by
forking the graph. B0 uses bare nodes; B1/P1 wrap via pipeline.strategies.
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from pipeline.state import PipelineState
from pipeline.strategies import get_nodes_for_condition


def _route_after_stage(state: PipelineState) -> Literal["continue", "abort"]:
    """Abort remaining stages once failed is set."""
    if state.get("failed"):
        return "abort"
    return "continue"


def build_graph(condition: str = "B0"):
    nodes = get_nodes_for_condition(condition)
    graph = StateGraph(PipelineState)

    graph.add_node("planner", nodes["planner"])
    graph.add_node("retriever", nodes["retriever"])
    graph.add_node("synthesizer", nodes["synthesizer"])
    graph.add_node("formatter", nodes["formatter"])

    graph.set_entry_point("planner")

    for src, dst in [
        ("planner", "retriever"),
        ("retriever", "synthesizer"),
        ("synthesizer", "formatter"),
    ]:
        graph.add_conditional_edges(
            src,
            _route_after_stage,
            {"continue": dst, "abort": END},
        )

    graph.add_conditional_edges(
        "formatter",
        _route_after_stage,
        {"continue": END, "abort": END},
    )

    return graph.compile()


def run_question(
    graph,
    item: dict[str, Any],
    *,
    condition: str = "B0",
    scorer=None,
) -> PipelineState:
    """Run one question under the given condition.

    B1 additionally re-runs the *full graph* up to B1_MAX_RETRIES times when the
    pipeline succeeds but the final scorer fails (blind; no new information).
    P2/P3 use dedicated orchestrators (checkpointing / graceful degradation).
    All attempts' stage_logs are accumulated so cost/latency include retries.
    """
    import config
    from pipeline.strategies import ORCHESTRATED_CONDITIONS, run_orchestrated

    if condition in ORCHESTRATED_CONDITIONS:
        result = run_orchestrated(condition, item)
        result["condition"] = condition
        return result  # type: ignore[return-value]

    max_outer = config.B1_MAX_RETRIES if condition == "B1" and scorer is not None else 0
    accumulated_logs: list[dict[str, Any]] = []
    last_result: PipelineState | None = None

    for outer_attempt in range(1, max_outer + 2):
        initial: PipelineState = {
            "question_id": item["id"],
            "question": item["question"],
            "gold_answer": item["gold_answer"],
            "supporting_doc_ids": list(item.get("supporting_doc_ids") or []),
            "stage_logs": list(accumulated_logs),
            "failed": False,
            "condition": condition,
            "retry_feedback": None,
            "retriever_expand": False,
        }
        result = graph.invoke(initial)
        logs = list(result.get("stage_logs") or [])
        # Tag outer-loop scorer retries
        if outer_attempt > 1 and logs:
            for i in range(len(accumulated_logs), len(logs)):
                entry = dict(logs[i])
                entry.setdefault("verification_reason", "blind_full_graph_retry_after_score_fail")
                entry.setdefault("attempt", entry.get("attempt") or outer_attempt)
                logs[i] = entry
        accumulated_logs = logs
        result = {**result, "stage_logs": accumulated_logs, "condition": condition}
        last_result = result  # type: ignore[assignment]

        if result.get("failed"):
            break

        if scorer is None or condition != "B1":
            break

        pred = result.get("final_answer") or ""
        gold = item["gold_answer"]
        if scorer(pred, gold):
            break

        if outer_attempt > max_outer:
            break
        accumulated_logs = list(accumulated_logs) + [
            {
                "stage": "scorer",
                "input": {"final_answer": pred, "gold_answer": gold},
                "output": None,
                "latency_ms": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "error": "score_fail",
                "attempt": outer_attempt,
                "verification_reason": "blind_retry_triggered_by_score_fail",
            }
        ]

    assert last_result is not None
    return last_result
