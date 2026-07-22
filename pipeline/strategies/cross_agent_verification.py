"""P4 — Cross-agent verification gate (Synthesizer → Formatter handoff)."""

from __future__ import annotations

import json
import re
from typing import Any

import config
from pipeline.llm import call_claude
from pipeline.logger import estimate_cost_usd
from pipeline.nodes import formatter_node, planner_node, retriever_node, synthesizer_node
from pipeline.strategies.tool_grounded_retry import verify_stage

# Strict gate prompt: checklist + prefer REJECT over soft ACCEPT / casual PROPOSE.
VERIFIER_SYSTEM = (
    "You are the Verifier agent in a multi-hop QA pipeline. "
    "You are NOT the Synthesizer. You gate whether a draft may propagate to the Formatter. "
    "Use ONLY the provided evidence documents — ignore outside knowledge.\n\n"
    "Run this checklist in order. If ANY item fails, you MUST NOT ACCEPT:\n"
    "A) Question addressed: draft directly answers the asked question (not a related tangent).\n"
    "B) Evidence support: every material claim in the draft is supported by the retrieved docs.\n"
    "C) Citation grounding: every draft_citation ID appears in Allowed citation IDs; "
    "cited docs actually support the claims they are attached to.\n"
    "D) No contradiction: draft does not contradict the retrieved evidence.\n\n"
    "Outcomes (choose exactly one):\n"
    "1. ACCEPT — only if A–D all pass. If uncertain on any item, do NOT accept.\n"
    "2. REJECT_WITH_CRITIQUE — preferred when any checklist item fails. "
    "Name the failure mode explicitly (e.g. 'citation does not support the claim', "
    "'answer does not address the question', 'answer contradicts retrieved evidence', "
    "'ungrounded citation ID'). Give a concrete, actionable critique for the Synthesizer.\n"
    "3. PROPOSE_CORRECTION — rare. Use ONLY when confidence >= 0.9 AND the evidence "
    "unambiguously supports a corrected draft_answer + citations using only allowed IDs. "
    "If a citation ID is invalid or support is partial, choose REJECT_WITH_CRITIQUE instead.\n\n"
    "Respond with ONLY valid JSON:\n"
    '{"outcome":"ACCEPT|REJECT_WITH_CRITIQUE|PROPOSE_CORRECTION",'
    '"critique":"..." or null,'
    '"corrected_answer":"..." or null,'
    '"corrected_citations":["doc_id",...] or null,'
    '"confidence":0.0,'
    '"failed_checks":["A|B|C|D",...]}'
)


def _extract_json(text: str) -> Any:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    return json.loads(cleaned)


def _merge(state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = {**state, **update}
    if "stage_logs" in update:
        merged["stage_logs"] = update["stage_logs"]
    return merged


def _run_node(state: dict[str, Any], node_fn, *, feedback: str | None = None) -> dict[str, Any]:
    working = {
        **state,
        "failed": False,
        "failure_reason": None,
        "retry_feedback": feedback,
        "retriever_expand": False,
    }
    update = node_fn(working)
    return _merge(working, update)


def _evidence_block(docs: list[dict[str, Any]]) -> str:
    if not docs:
        return "(no documents retrieved)"
    parts = []
    for d in docs:
        parts.append(
            f"[{d['doc_id']}] {d.get('title', '')}\n{d.get('text', '')}"
        )
    return "\n\n".join(parts)


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


def _run_synthesizer_with_schema_retry(
    state: dict[str, Any], *, feedback: str | None = None
) -> dict[str, Any]:
    """One schema/parse retry via P1 verify_stage before the verifier gate.

    Only retries hard JSON/schema failures — not citation-judgment calls
    (those belong to the cross-agent verifier).
    """
    state = _run_node(state, synthesizer_node, feedback=feedback)
    logs = list(state.get("stage_logs") or [])
    logs = _tag_last_log(logs, attempt=1)
    state["stage_logs"] = logs

    if not state.get("failed"):
        return state

    update = {
        "failed": True,
        "failure_reason": state.get("failure_reason"),
        "draft_answer": state.get("draft_answer"),
        "draft_citations": state.get("draft_citations"),
    }
    reason = verify_stage("synthesizer", state, update)
    fail_l = (state.get("failure_reason") or "").lower()
    is_schema = bool(
        (reason and reason.startswith("SCHEMA_VIOLATION"))
        or "malformed" in fail_l
        or "expecting value" in fail_l
        or "json" in fail_l
    )
    if not is_schema or not reason:
        return state

    state = _run_node(state, synthesizer_node, feedback=reason)
    logs = list(state.get("stage_logs") or [])
    logs = _tag_last_log(logs, attempt=2, verification_reason=reason)
    state["stage_logs"] = logs
    return state


def _deterministic_gate_failure(state: dict[str, Any]) -> str | None:
    """External checks the LLM soft-accepts too often — same facts P1 catches."""
    docs = list(state.get("retrieved_docs") or [])
    draft = (state.get("draft_answer") or "").strip()
    citations = list(state.get("draft_citations") or [])
    allowed = {d["doc_id"] for d in docs}

    if not draft:
        return "EMPTY_DRAFT: draft_answer is empty; cannot propagate to Formatter."
    if not docs:
        return (
            "NO_EVIDENCE: 0 retrieved documents; draft cannot be grounded. "
            "Reject and revise only if evidence becomes available."
        )
    missing = sorted({str(c) for c in citations if str(c) not in allowed})
    if missing:
        return (
            "UNGROUNDED_CITATIONS: citations "
            f"{missing} are not in the retrieved document set "
            f"{sorted(allowed)}. Regenerate draft_citations using ONLY allowed IDs."
        )
    return None


def _normalize_outcome(raw: str) -> str:
    raw_outcome = (raw or "ACCEPT").upper().strip()
    if raw_outcome in {"ACCEPT", "REJECT_WITH_CRITIQUE", "PROPOSE_CORRECTION"}:
        return raw_outcome
    if "REJECT" in raw_outcome:
        return "REJECT_WITH_CRITIQUE"
    if "PROPOSE" in raw_outcome or "CORRECT" in raw_outcome:
        return "PROPOSE_CORRECTION"
    # Unknown token — do not soft-default to ACCEPT
    return "REJECT_WITH_CRITIQUE"


def _call_verifier(state: dict[str, Any]) -> dict[str, Any]:
    """Run deterministic gate + verifier LLM; return structured result + log fields."""
    question = state["question"]
    docs = list(state.get("retrieved_docs") or [])
    draft = state.get("draft_answer") or ""
    citations = list(state.get("draft_citations") or [])
    allowed = sorted({d["doc_id"] for d in docs})

    det = _deterministic_gate_failure(state)
    if det:
        log_entry = {
            "stage": "verifier",
            "input": {
                "question": question,
                "n_docs": len(docs),
                "draft_answer": draft,
                "draft_citations": citations,
                "allowed_citation_ids": allowed,
            },
            "output": {
                "outcome": "REJECT_WITH_CRITIQUE",
                "critique": det,
                "corrected_answer": None,
                "corrected_citations": None,
                "confidence": 1.0,
                "raw": None,
                "deterministic": True,
            },
            "latency_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": None,
            "event": "cross_agent_verify",
            "model": None,
            "verifier_outcome": "REJECT_WITH_CRITIQUE",
            "verifier_critique": det,
            "verifier_tokens": {"input": 0, "output": 0, "total": 0},
            "verifier_cost_usd": 0.0,
            "verifier_debug": {
                "system_prompt": VERIFIER_SYSTEM,
                "user_prompt": None,
                "raw_response": None,
                "n_docs": len(docs),
                "deterministic_reason": det,
            },
        }
        return {
            "outcome": "REJECT_WITH_CRITIQUE",
            "critique": det,
            "corrected_answer": None,
            "corrected_citations": [],
            "confidence": 1.0,
            "log": log_entry,
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": 0.0,
            "cost_usd": 0.0,
        }

    user = (
        f"Question: {question}\n\n"
        f"Retrieved evidence:\n{_evidence_block(docs)}\n\n"
        f"Synthesizer draft_answer: {draft}\n"
        f"Synthesizer draft_citations: {json.dumps(citations)}\n"
        f"Allowed citation IDs: {json.dumps(allowed)}\n\n"
        "Apply the checklist. If any check fails, outcome must be "
        "REJECT_WITH_CRITIQUE (or PROPOSE_CORRECTION only if confidence >= 0.9)."
    )

    result = call_claude(VERIFIER_SYSTEM, user, model=config.MODEL_NAME)
    cost = estimate_cost_usd(result.input_tokens, result.output_tokens, model=config.MODEL_NAME)

    outcome = "REJECT_WITH_CRITIQUE"
    critique = None
    corrected_answer = None
    corrected_citations = None
    confidence = 0.5
    parse_error = None
    failed_checks: list[str] = []

    try:
        parsed = _extract_json(result.text)
        outcome = _normalize_outcome(str(parsed.get("outcome") or ""))
        # Missing/empty outcome → reject, not accept
        if not str(parsed.get("outcome") or "").strip():
            outcome = "REJECT_WITH_CRITIQUE"
            critique = "Verifier returned empty outcome; treating as REJECT_WITH_CRITIQUE."

        critique = parsed.get("critique")
        if critique is not None:
            critique = str(critique).strip() or None
        corrected_answer = parsed.get("corrected_answer")
        if corrected_answer is not None:
            corrected_answer = str(corrected_answer).strip() or None
        cc = parsed.get("corrected_citations")
        if isinstance(cc, list):
            corrected_citations = [str(c) for c in cc]
        fc = parsed.get("failed_checks")
        if isinstance(fc, list):
            failed_checks = [str(x) for x in fc]
        try:
            confidence = float(parsed.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        # If model listed failed checks but still ACCEPTed, force reject
        if outcome == "ACCEPT" and failed_checks:
            outcome = "REJECT_WITH_CRITIQUE"
            critique = critique or (
                f"Verifier listed failed_checks={failed_checks} but chose ACCEPT; "
                "overriding to REJECT_WITH_CRITIQUE."
            )

        if outcome == "PROPOSE_CORRECTION":
            if not corrected_answer or confidence < 0.9:
                outcome = "REJECT_WITH_CRITIQUE"
                critique = critique or (
                    "PROPOSE_CORRECTION rejected: need corrected_answer and "
                    "confidence >= 0.9; treating as REJECT_WITH_CRITIQUE."
                )
            else:
                allowed_set = set(allowed)
                corrected_citations = [
                    c for c in (corrected_citations or []) if c in allowed_set
                ]
                # Invalid cites in proposal → reject for synth retry
                raw_cc = parsed.get("corrected_citations")
                if isinstance(raw_cc, list):
                    bad = [str(c) for c in raw_cc if str(c) not in allowed_set]
                    if bad:
                        outcome = "REJECT_WITH_CRITIQUE"
                        critique = (
                            critique
                            or f"PROPOSE_CORRECTION used invalid citation IDs {bad}."
                        )
    except Exception as exc:
        parse_error = str(exc)
        # Fail-closed: do not rubber-stamp on parse errors
        outcome = "REJECT_WITH_CRITIQUE"
        critique = (
            f"Verifier JSON parse failed ({parse_error}); "
            "fail-closed REJECT_WITH_CRITIQUE."
        )

    log_entry = {
        "stage": "verifier",
        "input": {
            "question": question,
            "n_docs": len(docs),
            "draft_answer": draft,
            "draft_citations": citations,
            "allowed_citation_ids": allowed,
        },
        "output": {
            "outcome": outcome,
            "critique": critique,
            "corrected_answer": corrected_answer,
            "corrected_citations": corrected_citations,
            "confidence": confidence,
            "failed_checks": failed_checks,
            "raw": result.text[:2000],
            "deterministic": False,
        },
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "error": parse_error,
        "event": "cross_agent_verify",
        "model": config.MODEL_NAME,
        "verifier_outcome": outcome,
        "verifier_critique": critique,
        "verifier_tokens": {
            "input": result.input_tokens,
            "output": result.output_tokens,
            "total": result.input_tokens + result.output_tokens,
        },
        "verifier_cost_usd": round(cost, 6),
        "verifier_debug": {
            "system_prompt": VERIFIER_SYSTEM,
            "user_prompt": user[:6000],
            "raw_response": result.text[:2000],
            "n_docs": len(docs),
            "deterministic_reason": None,
        },
    }

    return {
        "outcome": outcome,
        "critique": critique,
        "corrected_answer": corrected_answer,
        "corrected_citations": corrected_citations or [],
        "confidence": confidence,
        "log": log_entry,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "cost_usd": cost,
    }


def run_cross_agent_pipeline(item: dict[str, Any]) -> dict[str, Any]:
    """Planner → Retriever → Synthesizer(+schema retry) → Verifier gate → Formatter.

    On REJECT_WITH_CRITIQUE: one synthesizer re-run with critique (evidence-bound).
    Cap: P4_MAX_REJECT_ROUNDS (default 1). After cap, accept current draft or
    apply PROPOSE_CORRECTION if the last verifier response provided one.
    """
    state: dict[str, Any] = {
        "question_id": item["id"],
        "question": item["question"],
        "gold_answer": item["gold_answer"],
        "supporting_doc_ids": list(item.get("supporting_doc_ids") or []),
        "stage_logs": [],
        "failed": False,
        "condition": "P4",
        "retry_feedback": None,
        "retriever_expand": False,
        "model_override": None,
        "degradation_tier": 0,
        "low_confidence": False,
        "verifier_outcome": None,
        "verifier_critique": None,
        "second_synth_round": False,
        "p4_verifier_tokens": {"input": 0, "output": 0, "total": 0},
        "p4_verifier_cost_usd": 0.0,
    }

    state = _run_node(state, planner_node)
    if state.get("failed"):
        return state

    state = _run_node(state, retriever_node)
    if state.get("failed"):
        return state

    state = _run_synthesizer_with_schema_retry(state)
    if state.get("failed"):
        return state

    max_reject = config.P4_MAX_REJECT_ROUNDS
    reject_rounds = 0
    last_propose: dict[str, Any] | None = None
    final_outcome = "ACCEPT"

    while True:
        v = _call_verifier(state)
        logs = list(state.get("stage_logs") or [])
        logs.append(v["log"])
        state["stage_logs"] = logs

        vt = state["p4_verifier_tokens"]
        vt["input"] += v["input_tokens"]
        vt["output"] += v["output_tokens"]
        vt["total"] += v["input_tokens"] + v["output_tokens"]
        state["p4_verifier_tokens"] = vt
        state["p4_verifier_cost_usd"] = float(state["p4_verifier_cost_usd"]) + float(
            v["cost_usd"]
        )
        state["verifier_outcome"] = v["outcome"]
        state["verifier_critique"] = v["critique"]
        final_outcome = v["outcome"]

        if v["outcome"] == "ACCEPT":
            break

        if v["outcome"] == "PROPOSE_CORRECTION":
            last_propose = v
            state["draft_answer"] = v["corrected_answer"]
            state["draft_citations"] = list(v["corrected_citations"] or [])
            break

        # REJECT_WITH_CRITIQUE
        if reject_rounds >= max_reject:
            if last_propose and last_propose.get("corrected_answer"):
                state["draft_answer"] = last_propose["corrected_answer"]
                state["draft_citations"] = list(
                    last_propose.get("corrected_citations") or []
                )
                final_outcome = "PROPOSE_CORRECTION"
            else:
                final_outcome = "REJECT_WITH_CRITIQUE"
            break

        reject_rounds += 1
        state["second_synth_round"] = True
        critique = v["critique"] or "Draft rejected by verifier; revise using only evidence."
        feedback = (
            "Verifier REJECT_WITH_CRITIQUE — revise your draft. "
            "Stay strictly evidence-bound; use only retrieved doc IDs as citations.\n"
            f"Critique: {critique}"
        )
        state = _run_synthesizer_with_schema_retry(state, feedback=feedback)
        if state.get("failed"):
            # Keep prior draft for formatter rather than dying on re-synth parse fail
            state["failed"] = False
            state["failure_reason"] = None
            break

    state["verifier_outcome"] = final_outcome

    state = _run_node(state, formatter_node)
    return state
