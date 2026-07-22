"""Structured per-question logging for experimental conditions (B0, B1, P1–P4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config


def estimate_cost_usd(
    input_tokens: int, output_tokens: int, model: str | None = None
) -> float:
    """Estimate USD cost from token counts using config pricing constants."""
    use_haiku = bool(model and "haiku" in model.lower())
    in_rate = (
        config.CLAUDE_HAIKU_INPUT_USD_PER_MTOK
        if use_haiku
        else config.CLAUDE_SONNET_INPUT_USD_PER_MTOK
    )
    out_rate = (
        config.CLAUDE_HAIKU_OUTPUT_USD_PER_MTOK
        if use_haiku
        else config.CLAUDE_SONNET_OUTPUT_USD_PER_MTOK
    )
    return (input_tokens / 1_000_000.0) * in_rate + (output_tokens / 1_000_000.0) * out_rate


def _error_type(error: str | None) -> str | None:
    if not error:
        return None
    # Keep a short, stable label for aggregation
    lower = error.lower()
    if "malformed" in lower:
        return "malformed_output"
    if "authentication" in lower or "api_key" in lower or "401" in lower:
        return "auth_error"
    if "timeout" in lower:
        return "timeout"
    if "rate" in lower and "limit" in lower:
        return "rate_limit"
    return "exception"


def build_run_record(
    *,
    question_id: str,
    condition: str,
    stage_logs: list[dict[str, Any]],
    passed: bool,
    pipeline_failed: bool,
    failure_reason: str | None,
    final_answer: str | None,
    gold_answer: str | None,
) -> dict[str, Any]:
    """Consolidate node stage_logs into one structured JSON record."""
    stages = []
    total_latency = 0.0
    total_in = 0
    total_out = 0

    for s in stage_logs:
        err = s.get("error")
        success = err is None and s.get("event") not in {
            "rollback",
            "rollback_exhausted",
        }
        # Event-only rows (checkpoint_save, degrade_*) count as success markers
        if s.get("event") in {"checkpoint_save", "degrade_tier_1_skip_planner", "degrade_tier_2_cheap_model", "degrade_tier_3_partial"}:
            success = True
        in_tok = int(s.get("input_tokens") or 0)
        out_tok = int(s.get("output_tokens") or 0)
        lat = float(s.get("latency_ms") or 0.0)
        total_latency += lat
        total_in += in_tok
        total_out += out_tok
        stage_cost = estimate_cost_usd(in_tok, out_tok, model=s.get("model"))
        if s.get("event") in {
            "checkpoint_save",
            "degrade_tier_1_skip_planner",
            "degrade_tier_2_cheap_model",
            "degrade_tier_3_partial",
            "cross_agent_verify",
        }:
            success = err is None
        stages.append(
            {
                "stage": s.get("stage"),
                "latency_ms": lat,
                "tokens_used": {
                    "input": in_tok,
                    "output": out_tok,
                    "total": in_tok + out_tok,
                },
                "success": success,
                "error_type": _error_type(err),
                "error": err,
                # Optional strategy fields — ignored by aggregate.py core stats
                "attempt": s.get("attempt"),
                "verification_reason": s.get("verification_reason"),
                "model": s.get("model"),
                "event": s.get("event"),
                "degradation_tier": s.get("degradation_tier"),
                "low_confidence": s.get("low_confidence"),
                "estimated_cost_usd": round(stage_cost, 6),
                # P4 verifier line-item fields
                "verifier_outcome": s.get("verifier_outcome"),
                "verifier_critique": s.get("verifier_critique"),
                "verifier_tokens": s.get("verifier_tokens"),
                "verifier_cost_usd": s.get("verifier_cost_usd"),
                "verifier_debug": s.get("verifier_debug"),
            }
        )

    # Prefer summing per-stage costs (handles mixed Sonnet/Haiku in P3)
    cost = sum(float(st.get("estimated_cost_usd") or 0.0) for st in stages)
    if cost == 0.0:
        cost = estimate_cost_usd(total_in, total_out)

    # Pull optional run-level flags from last stage logs / caller via stage_logs scan
    degradation_tier = None
    low_confidence = False
    for s in reversed(stage_logs):
        if s.get("degradation_tier") is not None:
            degradation_tier = s.get("degradation_tier")
            break
    for s in stage_logs:
        if s.get("low_confidence"):
            low_confidence = True
            break

    # P4 verifier overhead (sum all verifier stage rows)
    verifier_in = 0
    verifier_out = 0
    verifier_cost = 0.0
    verifier_outcome = None
    verifier_critique = None
    second_synth_round = False
    synth_count = 0
    for s in stage_logs:
        if s.get("stage") == "verifier" or s.get("event") == "cross_agent_verify":
            verifier_in += int((s.get("verifier_tokens") or {}).get("input") or s.get("input_tokens") or 0)
            verifier_out += int((s.get("verifier_tokens") or {}).get("output") or s.get("output_tokens") or 0)
            if s.get("verifier_cost_usd") is not None:
                verifier_cost += float(s["verifier_cost_usd"])
            else:
                verifier_cost += estimate_cost_usd(
                    int(s.get("input_tokens") or 0),
                    int(s.get("output_tokens") or 0),
                    model=s.get("model"),
                )
            if s.get("verifier_outcome"):
                verifier_outcome = s.get("verifier_outcome")
            if s.get("verifier_critique"):
                verifier_critique = s.get("verifier_critique")
        if s.get("stage") == "synthesizer":
            synth_count += 1
    if synth_count > 1:
        second_synth_round = True

    return {
        "question_id": question_id,
        "condition": condition,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stages": stages,
        "final": {
            "pass": bool(passed),
            "pipeline_failed": bool(pipeline_failed),
            "failure_reason": failure_reason,
            "final_answer": final_answer,
            "gold_answer": gold_answer,
            "total_latency_ms": total_latency,
            "total_tokens": {
                "input": total_in,
                "output": total_out,
                "total": total_in + total_out,
            },
            "estimated_cost_usd": round(cost, 6),
            "degradation_tier": degradation_tier,
            "low_confidence": low_confidence,
            # P4 optional fields
            "verifier_outcome": verifier_outcome,
            "verifier_critique": verifier_critique,
            "verifier_tokens": {
                "input": verifier_in,
                "output": verifier_out,
                "total": verifier_in + verifier_out,
            },
            "verifier_cost_usd": round(verifier_cost, 6),
            "second_synth_round": second_synth_round,
        },
    }


def write_run_log(
    record: dict[str, Any],
    logs_dir: Path | None = None,
    *,
    trial: int | None = None,
) -> Path:
    """Write `/logs/{condition}/[trial_N/]{question_id}.json` and return the path."""
    base = logs_dir or config.LOGS_DIR
    condition = record["condition"]
    qid = record["question_id"]
    # Sanitize path component (Hotpot IDs are usually safe already)
    safe_qid = "".join(c if c.isalnum() or c in "-_" else "_" for c in qid)
    out_dir = base / condition
    if trial is not None:
        out_dir = out_dir / f"trial_{trial}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{safe_qid}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
