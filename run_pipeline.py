"""
Run the multi-agent QA pipeline under a selected experimental condition.

Usage:
  python run_pipeline.py --condition B0
  python run_pipeline.py --condition B1
  python run_pipeline.py --condition P1
  python run_pipeline.py --condition B0 --mock

Logs: /logs/{condition}/{question_id}.json
Dataset: data/questions.json (HotpotQA distractor-dev 40Q subset).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

# Parse args early so --mock is set before pipeline.llm import
_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--mock", action="store_true")
_pre.add_argument("--condition", default="B0")
_pre_args, _ = _pre.parse_known_args()
if _pre_args.mock:
    os.environ["MOCK_LLM"] = "1"

import config
from pipeline.aggregate import aggregate, print_summary
from pipeline.graph import build_graph, run_question
from pipeline.logger import build_run_record, write_run_log
from pipeline.retriever import get_retriever
from pipeline.scoring import get_scorer


def load_questions(path: Path = config.QUESTIONS_PATH) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multi-agent QA experimental condition")
    parser.add_argument(
        "--condition",
        choices=config.VALID_CONDITIONS,
        default="B0",
        help="Experimental condition (default: B0)",
    )
    parser.add_argument("--mock", action="store_true", help="Use mock LLM (offline)")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip questions that already have a log under /logs/{condition}/",
    )
    parser.add_argument(
        "--trial",
        type=int,
        default=None,
        help="Write logs under /logs/{condition}/trial_{N}/ (preserves multi-trial runs)",
    )
    args = parser.parse_args()
    condition = args.condition
    trial = args.trial

    questions = load_questions()
    log_dir = config.LOGS_DIR / condition
    if trial is not None:
        log_dir = log_dir / f"trial_{trial}"
    if args.resume and log_dir.exists():
        done = {p.stem for p in log_dir.glob("*.json")}
        before = len(questions)
        questions = [q for q in questions if q["id"] not in done]
        print(f"Resume: skipping {before - len(questions)} already-logged questions")

    get_retriever(reload=True)
    graph = build_graph(condition=condition)
    scorer = get_scorer("exact_substring")

    n = len(questions)
    mock = os.environ.get("MOCK_LLM", "").strip().lower() in {"1", "true", "yes"}
    labels = {
        "B0": "no fallback",
        "B1": "blind retry",
        "P1": "tool-grounded retry-with-verification",
        "P2": "deterministic checkpointing",
        "P3": "graceful degradation",
        "P4": "cross-agent verification gate",
    }
    print(f"Condition: {condition} ({labels.get(condition, '')})")
    if trial is not None:
        print(f"Trial: {trial}")
    print(f"Model: {config.MODEL_NAME}{' [MOCK]' if mock else ''}")
    print(f"Questions this run: {n}")
    print(f"Logs dir: {log_dir}")
    if condition == "P1":
        print(
            f"P1 retriever min score threshold: {config.RETRIEVER_MIN_SCORE} "
            f"(documented in config.py)"
        )
    if condition == "P2":
        print(f"P2 max rollbacks: {config.CHECKPOINT_MAX_ROLLBACKS}")
    if condition == "P3":
        print(
            f"P3 max retries/stage={config.P3_MAX_RETRIES}, "
            f"token budget={config.P3_TOKEN_BUDGET}, "
            f"cheap model={config.CHEAP_MODEL_NAME}"
        )
    if condition == "P4":
        print(f"P4 max reject rounds: {config.P4_MAX_REJECT_ROUNDS}")
    print("-" * 60)

    if n == 0:
        print("Nothing to run.")
        print_summary(aggregate(condition, trial=trial))
        return

    for item in questions:
        result = run_question(graph, item, condition=condition, scorer=scorer)
        logs = list(result.get("stage_logs") or [])

        pipeline_failed = bool(result.get("failed"))
        final_answer = result.get("final_answer") or ""
        gold = item["gold_answer"]

        if pipeline_failed:
            passed = False
            status = "FAIL (pipeline)"
            detail = result.get("failure_reason") or "unknown"
        else:
            passed = scorer(final_answer, gold)
            status = "PASS" if passed else "FAIL (score)"
            detail = final_answer

        record = build_run_record(
            question_id=item["id"],
            condition=condition,
            stage_logs=logs,
            passed=passed,
            pipeline_failed=pipeline_failed,
            failure_reason=result.get("failure_reason"),
            final_answer=final_answer if (not pipeline_failed or result.get("low_confidence")) else None,
            gold_answer=gold,
        )
        if result.get("degradation_tier") is not None:
            record["final"]["degradation_tier"] = result.get("degradation_tier")
        if result.get("low_confidence"):
            record["final"]["low_confidence"] = True
        # Prefer orchestrator-level P4 totals when present
        if result.get("verifier_outcome"):
            record["final"]["verifier_outcome"] = result.get("verifier_outcome")
        if result.get("verifier_critique") is not None:
            record["final"]["verifier_critique"] = result.get("verifier_critique")
        if result.get("p4_verifier_tokens"):
            record["final"]["verifier_tokens"] = result.get("p4_verifier_tokens")
        if result.get("p4_verifier_cost_usd") is not None:
            record["final"]["verifier_cost_usd"] = round(
                float(result.get("p4_verifier_cost_usd") or 0.0), 6
            )
        if result.get("second_synth_round") is not None:
            record["final"]["second_synth_round"] = bool(result.get("second_synth_round"))
        log_path = write_run_log(record, trial=trial)
        fin = record["final"]

        extra = ""
        if condition == "P4" and fin.get("verifier_outcome"):
            extra = (
                f" | verify={fin.get('verifier_outcome')}"
                f" v_cost=${float(fin.get('verifier_cost_usd') or 0):.4f}"
                f"{' +re-synth' if fin.get('second_synth_round') else ''}"
            )
        print(
            f"[{item['id']}] {status} | "
            f"latency={fin['total_latency_ms']:.0f}ms | "
            f"tokens={fin['total_tokens']['total']} | "
            f"cost=${fin['estimated_cost_usd']:.4f}{extra}"
        )
        print(f"  Q: {item['question'][:80]}{'...' if len(item['question']) > 80 else ''}")
        print(f"  Gold: {gold}")
        print(f"  Pred: {detail}")
        print(f"  Log: {log_path}")
        print()

    stats = aggregate(condition, trial=trial)
    print_summary(stats)


if __name__ == "__main__":
    main()
