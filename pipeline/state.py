"""Typed pipeline state.

Designed so later steps can inject faults at stage boundaries (mutate
fields between nodes) and attach fallbacks (P1–P4, B1) without rewriting
the core schema. Stage logs are stubs for Step 2.2 consolidation.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class StageLog(TypedDict):
    """Per-node structured log (optional fields used by B1/P1 strategies)."""

    stage: str
    input: Any
    output: Any
    latency_ms: float
    input_tokens: int
    output_tokens: int
    error: str | None
    # Optional — present on retry attempts (B1/P1/P2/P3); ignored by aggregate core fields
    attempt: NotRequired[int]
    verification_reason: NotRequired[str | None]
    model: NotRequired[str | None]
    event: NotRequired[str | None]  # e.g. checkpoint_save, rollback, degrade
    degradation_tier: NotRequired[int]
    low_confidence: NotRequired[bool]


class RetrievedDoc(TypedDict):
    doc_id: str
    title: str
    text: str
    score: float
    sub_question: str


class PipelineState(TypedDict):
    # --- Identity / dataset ---
    question_id: str
    question: str
    gold_answer: str
    supporting_doc_ids: list[str]

    # --- Stage outputs (fault-injection points) ---
    # Planner
    sub_questions: NotRequired[list[str]]
    # Retriever
    retrieved_docs: NotRequired[list[RetrievedDoc]]
    # Synthesizer
    draft_answer: NotRequired[str]
    draft_citations: NotRequired[list[str]]
    # Formatter
    final_answer: NotRequired[str]
    citations: NotRequired[list[str]]
    confidence: NotRequired[float]
    formatted_output: NotRequired[dict[str, Any]]

    # --- Logging / control ---
    stage_logs: list[StageLog]
    failed: bool
    failure_reason: NotRequired[str]
    # Reserved for later fallbacks (unused in B0)
    condition: NotRequired[str]  # e.g. "B0", "B1", "P1"
    checkpoint: NotRequired[dict[str, Any]]
    # Optional feedback string appended to LLM user prompts on P1/P2/P3 retries
    retry_feedback: NotRequired[str | None]
    # When set, retriever expands search (P1 empty/low-score recovery)
    retriever_expand: NotRequired[bool]
    # P2/P3 control fields
    model_override: NotRequired[str | None]
    checkpoints: NotRequired[list[dict[str, Any]]]
    rollback_count: NotRequired[int]
    degradation_tier: NotRequired[int]  # 0=none, 1=skip-plan, 2=cheap-model, 3=partial
    low_confidence: NotRequired[bool]
    skip_planner: NotRequired[bool]
