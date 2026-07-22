"""Strategy registry: wrap base nodes or route to orchestrators (P2–P4)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pipeline.nodes import formatter_node, planner_node, retriever_node, synthesizer_node
from pipeline.strategies.blind_retry import wrap_blind_retry
from pipeline.strategies.checkpointing import run_checkpointed_pipeline
from pipeline.strategies.cross_agent_verification import run_cross_agent_pipeline
from pipeline.strategies.graceful_degradation import run_degraded_pipeline
from pipeline.strategies.tool_grounded_retry import wrap_tool_grounded_retry

NodeFn = Callable[[dict[str, Any]], dict[str, Any]]

BASE_NODES: dict[str, NodeFn] = {
    "planner": planner_node,
    "retriever": retriever_node,
    "synthesizer": synthesizer_node,
    "formatter": formatter_node,
}

# Conditions that run a custom orchestrator instead of LangGraph node wraps
ORCHESTRATED_CONDITIONS = {
    "P2": run_checkpointed_pipeline,
    "P3": run_degraded_pipeline,
    "P4": run_cross_agent_pipeline,
}


def get_nodes_for_condition(condition: str) -> dict[str, NodeFn]:
    """Return node callables for graph-based conditions. B0 = unmodified nodes."""
    if condition == "B0":
        return dict(BASE_NODES)
    if condition == "B1":
        return {name: wrap_blind_retry(name, fn) for name, fn in BASE_NODES.items()}
    if condition == "P1":
        return {
            name: wrap_tool_grounded_retry(name, fn) for name, fn in BASE_NODES.items()
        }
    if condition in ORCHESTRATED_CONDITIONS:
        return dict(BASE_NODES)
    raise ValueError(f"Unknown condition {condition!r}")


def run_orchestrated(condition: str, item: dict[str, Any]) -> dict[str, Any]:
    if condition not in ORCHESTRATED_CONDITIONS:
        raise ValueError(f"{condition} is not an orchestrated condition")
    return ORCHESTRATED_CONDITIONS[condition](item)
