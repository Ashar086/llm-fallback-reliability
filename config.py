"""Central configuration for the multi-agent QA pipeline."""

from pathlib import Path

# Primary model — all stages unless overridden (P3 cheap tier)
MODEL_NAME = "claude-sonnet-4-6"
# P3 degradation tier 2: cheaper/faster model for remaining stages
CHEAP_MODEL_NAME = "claude-haiku-4-5-20251001"

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
QUESTIONS_PATH = DATA_DIR / "questions.json"
LOGS_DIR = PROJECT_ROOT / "logs"

# Retrieval
RETRIEVER_TOP_K = 3
# P1/P2/P3: keyword Jaccard-like scores on this corpus are typically ~0.02–0.15 for
# relevant hits; require at least one hit at/above this floor (else treat as miss).
RETRIEVER_MIN_SCORE = 0.02

# Anthropic
MAX_TOKENS = 1024
TEMPERATURE = 0.0

# Claude Sonnet 4.6 API pricing (USD per million tokens).
CLAUDE_SONNET_INPUT_USD_PER_MTOK = 3.0
CLAUDE_SONNET_OUTPUT_USD_PER_MTOK = 15.0
# Claude Haiku 4.5 pricing (USD per million tokens) — used when stage logs model=cheap.
CLAUDE_HAIKU_INPUT_USD_PER_MTOK = 1.0
CLAUDE_HAIKU_OUTPUT_USD_PER_MTOK = 5.0

# Fallback strategy knobs (unused by B0)
B1_MAX_RETRIES = 3  # additional blind attempts after the first
P1_MAX_RETRIES = 2  # additional tool-grounded attempts per stage after the first

# P2 — Deterministic checkpointing
CHECKPOINT_MAX_ROLLBACKS = 2  # rollback-and-retry cycles per question

# P3 — Graceful degradation
P3_MAX_RETRIES = 2  # P1-style retries before degrading at a stage
# B0 avg tokens/question ≈ 1229; 3× = ~3687 → round to 3700 as per-question budget.
P3_TOKEN_BUDGET = 3700

# P4 — Cross-agent verification gate
P4_MAX_REJECT_ROUNDS = 1  # one reject→re-synth cycle, then stop (bounds cost)

VALID_CONDITIONS = ("B0", "B1", "P1", "P2", "P3", "P4")
