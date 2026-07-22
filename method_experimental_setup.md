# Method and Experimental Setup

Draft for the paper. Grounded in `framework_design.md` and `significance_results.md`
(plus the recorded HotpotQA subset metadata for dataset construction details).

---

## Method

### Testbed

We evaluate fallback patterns on a fixed multi-agent multi-hop QA pipeline. The
pipeline has four stages, in order: **Planner**, **Retriever**, **Synthesizer**,
and **Formatter**. The Planner breaks a question into sub-questions. The
Retriever pulls documents from a fixed local corpus (no live web search). The
Synthesizer drafts an answer with citations. The Formatter emits the final
structured answer.

We built the graph in LangGraph and ran all LLM stages with Claude Sonnet
(`claude-sonnet-4-6`) at temperature 0, except where a pattern deliberately
switches models (P3’s cheap tier). Each stage writes typed fields into a shared
state object, so a fallback can see what failed and where without guessing.

End-to-end success is a correct final answer against a labeled gold string
(scoring details below). The design goal was a small production-like workflow
where stage failures are easy to locate and recover from—same idea as the
Candidate A testbed in the framework design.

### Conditions

We ran six conditions on the same questions and corpus. B0 and B1 are baselines.
P1–P4 are the fallback patterns. Full trigger/recovery specs live in the
framework design document; here we only summarize what each condition does.

**B0 — No fallback.** The pipeline runs once. Any hard stage error, or a wrong
final answer, counts as failure. No retries. This is the reference point for
cost and latency.

**B1 — Blind retry.** On stage failure (or a failed final check), we re-run the
same stage or the full graph up to a fixed number of times, with the same
prompts and tools. No new evidence, no rollback to a trusted checkpoint, no
second agent. This is the strawman we expect targeted patterns to beat on
reliability per dollar and per latency dollar.

**P1 — Tool-grounded retry-with-verification.** After a stage produces a
candidate output, we run cheap external checks: empty or low-relevance
retrieval, citation IDs missing from the retrieved set, schema/JSON parse
failures. If a check fails, we re-run only that stage and append the check
result as feedback (CRITIC-style verify-then-correct). Retries are capped.
This is not “please fix your answer” with no new signal.

**P2 — Deterministic checkpointing.** After a stage passes verification, we
save a checkpoint. On hard failure or verification failure at stage *i*, we
discard untrusted state from *i* onward, restore the last trusted checkpoint,
and re-execute forward from there (optionally with a one-shot tool hint). We
do not keep polluted intermediate memory.

**P3 — Graceful degradation.** After repeated recoveries fail at a stage, or a
per-question token budget is exceeded, we switch to a simpler path: skip
multi-hop planning, cascade remaining stages to a cheaper model (Haiku),
and/or return a partial answer marked low-confidence. The task is still scored
as pass/fail on the gold answer. When the Haiku path runs, those stages are
priced at Haiku rates in the logs; the P3 cost and latency numbers we report
already include that mix (they are not Sonnet-only totals with Haiku ignored).
In the pooled runs, Haiku was used on a small minority of questions—most P3
runs never left the Sonnet path—so the average cost stays close to P1/P2.

**P4 — Cross-agent verification gate.** Before the Synthesizer draft goes to
the Formatter, a second Verifier agent (distinct system prompt, same Sonnet
model) sees the question, retrieved evidence, and draft. It must ACCEPT,
REJECT_WITH_CRITIQUE, or PROPOSE_CORRECTION. On reject, the Synthesizer re-runs
once with the critique, still bound to the retrieved evidence. Reject-and-retry
is capped at one round *per question* (so a single question cannot loop); across
the fixed P4 run, that second synthesizer pass did fire on some questions
(six in the debug trial), just not repeatedly on the same item.

We evaluate each pattern as its own condition, not as stacked compositions.
Composition (e.g. P2+P1, then P3) is left for later work once single-pattern
effects are clear.

### Why external / tool-grounded feedback (P1–P3)

P1–P3 deliberately avoid intrinsic self-correction as the main recovery signal.
Huang et al. (2024) show that when models are asked to fix their own reasoning
without external feedback, they often do not improve and can get worse. Kamoi
et al. (2024) make the same point in survey form: reliable correction needs
external signals, task-specific checks, or other grounding—not prompted
self-evaluation alone.

So when P1 retries a stage, the feedback is a checkable fact (empty retrieval,
bad citation ID, broken JSON schema), not “try again.” P2 only writes
checkpoints after an external pass. P3 degrades on budget or repeated external
failures, not on the model’s own confidence score. P4 is different: it uses a
second agent as a gate. That is still external to the Synthesizer’s first draft,
but it is an LLM judge rather than a tool check, and we treat it as a separate
(expensive) pattern family.

---

## Experimental Setup

### Dataset

We use 40 multi-hop questions from HotpotQA (distractor setting, validation
split), loaded via Hugging Face `datasets`. Selection filters, recorded in the
subset metadata:

- Short gold answers (at most 60 characters / 6 tokens)
- Yes/no answers excluded
- At least two supporting titles
- Bridge-type questions preferred; then sort and take the first 40

The retrieval corpus has 100 documents: 80 supporting documents tied to the
selected questions, plus 20 distractor documents (sorted titles, stride
subsample). The Retriever only searches this fixed corpus, so runs are
reproducible and do not depend on a live search API.

### Scoring

A question passes if the model’s final answer matches the gold string under a
normalized token-coverage rule: exact match, substring containment either way,
or every gold token appearing in the prediction. That is lenient toward verbose
answers and strict about covering the gold content.

This scorer is a limitation. It can mark a factually reasonable answer as fail
when the wording diverges from Hotpot’s short gold span, and it does not check
citation quality on its own. We flag that for the discussion; the same scorer
is used for every condition so relative comparisons stay fair.

### Trial design and statistics

All LLM calls use temperature 0. We still ran multiple full trials because
scoring flukes and rare parse paths can move a few questions.

- B0, B1, P1, P2, P3: three independent trials of the same 40 questions
  (pooled n = 120 question-outcomes per condition)
- P4: two trials (pooled n = 80)

The third trial for B0/B1/P1/P2/P3 was targeted after the two-trial screen
showed edge-band significance for some B0 comparisons; P4 was not re-run.

For pass rate, we pool question outcomes across trials and compare conditions
with a two-sided two-proportion z-test and Fisher’s exact test (α = 0.05). We
do not report a run-level standard deviation from two or three trials. We did
not apply multiple-comparison correction; pairwise tests are an exploratory
screen and should be read that way.

For latency and cost we report per-trial values and simple averages. With only
two or three trial totals, we do not attach confidence intervals or claim
significant cost differences from the trial sample alone.

### Metrics

Primary metrics, aligned with the research question:

1. **Pass rate** — fraction of questions scored correct (pooled across trials)
2. **Latency** — end-to-end wall time per question; we report p50 and p95
   (pooled question-level distributions, and per-trial p50/p95 for inspection)
3. **Cost** — estimated USD from logged token counts and published Claude
   pricing; we report total cost per trial and average cost per question

Secondary logging for P4 separates Verifier token/cost from the Synthesizer so
verification overhead can be stated on its own line. That does not change the
primary cost metric above.
