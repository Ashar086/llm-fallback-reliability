# Framework Design: Reliability & Fallback Patterns for Multi-Agent LLM Systems

**Paper:** Reliability & Fallback Design Patterns for Multi-Agent LLM Systems  
**RQ:** Which fallback strategies most reduce total task failure in multi-agent LLM pipelines, and what latency/cost tradeoff does each carry?  
**Grounding:** Design choices constrained by `lit_scan.md` (esp. Huang/Kamoi, CRITIC, FrugalGPT, Du et al. debate, AgentDebug).

---

## Task 1 — Testbed Task Candidates (Step 1.1)

### Candidate A — Multi-Agent Research / Multi-Hop QA Pipeline

| Field | Detail |
|---|---|
| **Task description** | A fixed LangGraph/CrewAI pipeline: **Planner** decomposes a multi-hop question → **Retriever** calls a search/RAG tool → **Synthesizer** drafts an answer with citations → **Formatter** emits a structured JSON answer. End-to-end success = correct final answer against a labeled set (e.g. HotpotQA-style or a curated 100–200 question set). |
| **Failure-injection surface** | Failures map cleanly to stages: bad plan (wrong sub-questions), retrieval miss / wrong docs, hallucinated claims or fake citations, schema/format errors. Each stage has a typed state object, so we can inject faults (corrupt retrieval, truncate context, force wrong tool args) and measure whether the fallback recovers *before* the answer propagates. |
| **Build complexity** | **Low–Med.** One graph, one search tool (or fixed corpus), structured I/O schemas; no sandbox or ticket CRM needed. |

### Candidate B — Tool-Using Coding / Bugfix Agent

| Field | Detail |
|---|---|
| **Task description** | Pipeline: **Planner** reads a failing unit-test + stub → **Coder** edits code via tools → **Tester** runs the interpreter / pytest → **Reviewer** optionally comments. Success = tests pass. Dataset: a small suite of HumanEval-style or synthetic “broken function + tests” tasks. |
| **Failure-injection surface** | Strong *external* oracles: compile errors, assertion failures, timeouts, wrong tool calls. Stages are discrete (plan / edit / run). Ideal for tool-grounded verification (CRITIC-aligned) and for showing that blind retry ≠ targeted recovery (AgentDebug). |
| **Build complexity** | **Med–High.** Needs a safe code-execution sandbox, flaky-tool simulation, and careful isolation; week-buildable but more ops risk than Candidate A. |

### Candidate C — Support-Ticket Triage & Reply Agent

| Field | Detail |
|---|---|
| **Task description** | Pipeline: **Classifier** assigns intent/priority → **Knowledge Retriever** pulls policy/KB snippets → **Drafter** writes a reply → **Policy Checker** gates send. Success = correct intent label + reply that satisfies a checklist (or human/LLM-judge rubric on a labeled ticket set). |
| **Failure-injection surface** | Misclassification, wrong KB hit, policy-violating draft, premature “send.” Mirrors production support orchestration; silent quality faults (HTTP-200-but-wrong) are common—aligned with production-reliability concerns in the lit scan. |
| **Build complexity** | **Med.** Needs a synthetic ticket+KB corpus and a scoring rubric; less mechanical ground truth than coding tests, more annotation overhead than QA. |

---

### Recommendation: Candidate A (Multi-Agent Research / Multi-Hop QA)

**Choose Candidate A as the primary testbed.** It can be stood up in under a week on LangGraph + Claude with a fixed corpus or search tool and automatic answer scoring, while still looking like a production multi-agent workflow (plan → retrieve → synthesize → emit). Stage-typed state makes failure injection and checkpoint rollback easy to implement and report. Both tool-grounded critique (retrieval/citation checks) and cross-agent verification (a second agent vetting the draft) fit naturally, so every proposed pattern maps onto the same pipeline without a coding sandbox. Candidate B remains the best *follow-on* stress test if we later want a fully deterministic external oracle; Candidate C is deferred because success labeling is noisier and weakens the latency/cost vs. failure curves the RQ needs.

---

## Task 2 — Fallback Pattern Set (Step 1.2)

All patterns attach at **orchestration boundaries** in the Candidate A graph (after Planner, Retriever, Synthesizer). Success metrics for the RQ: **task failure rate**, **p50/p95 latency**, **\$ / tokens per successful task**.

### Baseline Conditions (to beat)

#### B0 — No Fallback
- **Trigger:** Never. Pipeline runs once; any stage error or failed final check → task failure.
- **Recovery:** None (fail-closed at first hard error, or fail-open with a wrong answer counted as failure).
- **Cost / latency overhead:** **None** (reference point).
- **Lit grounding:** Control condition implied by the gap analysis—prior techniques are rarely measured against a clean no-mitigation multi-agent baseline on failure × latency × cost jointly.

#### B1 — Blind Retry *(secondary baseline; not a “pattern” we advocate)*
- **Trigger:** Any stage soft-fail or hard-fail (timeout, schema error, empty retrieval, or final-answer check fail).
- **Recovery:** Re-run the *same* stage (or full graph) up to *k* times with the same prompt/tools; no new evidence, no rollback targeting, no second agent.
- **Cost / latency overhead:** **Med–High** (up to *k*× stage cost; often wasted on correlated errors).
- **Lit grounding:** AgentDebug (#13)—root-cause-targeted recovery beats undifferentiated retry; Blind Retry is the strawman we expect tool-grounded and targeted patterns to dominate on failure reduction *per dollar/latency*.

---

### Pattern Set (experimental conditions)

#### P1 — Tool-Grounded Retry-with-Verification
*(Not naive intrinsic self-critique.)*

| Aspect | Spec |
|---|---|
| **Trigger** | Stage emits a candidate output *and* a verifier signal fails: e.g. retrieval returns 0 hits / low similarity; citation IDs not in retrieved set; answer fails a structured schema check; optional lightweight entailment check against retrieved snippets. |
| **Recovery** | Re-run **only the failed stage** with tool feedback concatenated (CRITIC-style verify-then-correct): e.g. “citations {X} missing from corpus—regenerate with only these docs.” Cap at *r* retries; if still failing, escalate to P3 or mark failure. |
| **Cost / latency overhead** | **Med** (extra tool + LLM calls per failed stage; bounded by *r*). |
| **Lit grounding** | CRITIC (#3)—tool-interactive critique works; Huang (#4) & Kamoi (#5)—intrinsic self-correction alone is unreliable, so verification **must** use external signals (tools/schema/retrieval), not “please fix your answer.” |

#### P2 — Deterministic Checkpointing (Rollback to Last Trusted State)

| Aspect | Spec |
|---|---|
| **Trigger** | Hard failure or verification fail at stage *i* (tool exception, schema invalid, verifier reject, or timeout). |
| **Recovery** | Discard untrusted state from stage *i* onward; restore the last **checkpoint** (immutable snapshot after the last stage that passed verification). Re-execute from that checkpoint with optional one-shot tool-grounded hint; do **not** keep polluted intermediate memory. |
| **Cost / latency overhead** | **Low–Med** (avoids full-pipeline restart; cost ≈ re-run of suffix only; checkpoint I/O negligible). |
| **Lit grounding** | AgentDebug (#13)—isolating root cause and re-rolling from the critical step beats full undifferentiated retry; Wang agent survey (#11)—memory/planning/action modules are natural checkpoint boundaries. Complements Reflexion (#2) by using *trusted external pass* as the memory write gate rather than unconstrained verbal reflection. |

#### P3 — Graceful Degradation (Simpler Deterministic / Cheaper Path)

| Aspect | Spec |
|---|---|
| **Trigger** | After *r* failed recoveries under P1/P2 at the same stage, **or** cumulative budget exceeded (tokens/latency SLA). |
| **Recovery** | Switch to a **degraded path**: (a) skip multi-hop planning → single-shot retrieve+answer; (b) cascade to a cheaper/faster model for the remaining stages (FrugalGPT-style); and/or (c) return a partial answer + “low confidence / escalate to human” flag instead of a fully synthesized multi-hop narrative. Task still scored: full credit only if answer correct; partial credit optional as secondary metric. |
| **Cost / latency overhead** | **Low** on the degraded path (fewer agents/tools); **saves** cost vs. endless retries; may raise residual failure vs. P1/P4 on hard items. |
| **Lit grounding** | FrugalGPT (#6)—cost-aware escalation/cascades for reliability under budget; gap note—prior work is single-query routing, here applied to **multi-agent orchestration** after repeated stage failure. Also operational “fail soft” spirit of production reliability work (#9/#10), but *in-pipeline* rather than post-hoc RCA. |

#### P4 — Cross-Agent Verification (Verifier Agent Gate)

| Aspect | Spec |
|---|---|
| **Trigger** | Before a high-blast-radius handoff—especially **Synthesizer → final answer**—or when P1’s cheap tool checks are inconclusive. |
| **Recovery** | A second **Verifier** agent (distinct system prompt; ideally same or stronger model) receives (question, retrieved evidence, draft). It must **accept**, **reject+critique**, or **propose a corrected answer**. On reject, Synthesizer re-runs once with the critique (still evidence-bound—no pure intrinsic loop). Optional: short debate-style exchange capped at 1–2 rounds to bound cost. |
| **Cost / latency overhead** | **High** (extra full agent call(s) on the critical path; multiplies tokens roughly ×1.5–3 at the gated stage). |
| **Lit grounding** | Multiagent Debate (#7)—cross-instance critique improves factuality/reasoning; LLM-as-a-Judge (#8)—second-model gating is viable but bias-aware; used here as a **propagation gate**, not only as offline eval. |

---

### Pattern Summary Table

| ID | Name | Trigger (short) | Recovery (short) | Overhead | Primary lit anchor |
|---|---|---|---|---|---|
| **B0** | No fallback | — | Fail | None | Control / gap analysis |
| **B1** | Blind retry | Any fail | Same stage/graph × *k* | Med–High | AgentDebug (#13) — to beat |
| **P1** | Tool-grounded retry-with-verification | Tool/schema/evidence check fails | Re-run stage with tool critique | Med | CRITIC (#3); Huang/Kamoi (#4/#5) |
| **P2** | Deterministic checkpointing | Hard/verify fail at stage *i* | Rollback to last trusted checkpoint | Low–Med | AgentDebug (#13); agent modularity (#11) |
| **P3** | Graceful degradation | Budget / *r* retries exhausted | Simpler path / cheaper model / partial+escalate | Low (path) | FrugalGPT (#6) applied to MAS |
| **P4** | Cross-agent verification | Pre-propagation gate | Verifier accept/reject+critique (≤2 rounds) | High | Debate (#7); Judge (#8) |

---

### Experimental Use Note (for later steps)

- Run **B0, B1, P1, P2, P3, P4** as separate conditions on the same task set and failure-injection schedule so Pareto curves (failure ↓ vs. latency/cost ↑) are comparable.
- Prefer **compositions** (e.g. P2+P1, then P3 as last resort) only in a follow-on ablation after single-pattern effects are established—keeps the Q1 story clean: *which pattern family buys how much reliability per unit cost*.
