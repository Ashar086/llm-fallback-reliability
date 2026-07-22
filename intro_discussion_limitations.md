# Introduction, Discussion, and Limitations

---

## Introduction

Multi-agent LLM pipelines fail in the middle of a run as often as they fail
at the end. A Planner invents bad sub-questions. A Retriever returns nothing
useful. A Synthesizer emits broken JSON or cites a document that was never
retrieved. When that happens, most systems do one of two things: stop, or
blindly re-run the same stage with the same prompt and hope the next sample
is better.

Neither option is a reliability strategy. Stopping wastes the work already
done. Blind retry burns tokens and wall time on correlated errors. Production
teams are shipping multi-agent stacks anyway—support bots, research agents,
tool-using workflows—and the recovery logic is usually ad hoc: a retry
counter here, a second “checker” agent there, with little evidence for which
choice actually cuts end-to-end failure, or what it costs in latency and
dollars.

This paper asks a direct question: **which fallback strategies most reduce
total task failure in multi-agent LLM pipelines, and what latency and cost
tradeoff does each carry?**

We answer it on one fixed testbed: a Planner → Retriever → Synthesizer →
Formatter multi-hop QA pipeline on LangGraph with Claude Sonnet. We compare
six conditions on the same 40 HotpotQA questions—no fallback (B0), blind
retry (B1), tool-grounded retry (P1), checkpoint rollback (P2), graceful
degradation (P3), and a cross-agent verification gate (P4)—and measure them
together on pass rate, p50/p95 latency, and cost per question.

The headline is not subtle. Targeted fallbacks that use external checks or
trusted checkpoints (P1, P2, P3) significantly beat doing nothing. Blind
retry and the fancier verifier gate do not, despite costing more and
stretching the latency tail. P1, P2, and P3 also land statistically
indistinguishable from each other: several different designs buy similar
gains. The expensive second-agent gate is not automatically worth it.

The rest of the paper is organized as follows. Related Work situates the
patterns against retry, verification, production RCA, and agent-failure
surveys. Method and Experimental Setup describe the pipeline, conditions,
dataset, and trial design. Results report the pooled comparisons and
tradeoff figures. Discussion and Limitations say what that means for
builders and where the claims stop.

---

## Discussion

If you are building a multi-agent pipeline, the practical takeaway is
narrow and useful. Do not default to blind retry. It did not significantly
beat no fallback on pass rate, and it blew out p95 latency because failed
questions stack sequential re-runs with no new evidence. Do not assume a
cross-agent verifier is automatically “more reliable” because it looks
sophisticated. In our runs it was the most expensive condition and one of
the two worst latency tails, without a significant pass-rate win over doing
nothing.

What worked was simpler: tool- or schema-grounded stage checks with a capped
retry (P1), rollback to a last trusted checkpoint (P2), or degrade when
retries and budget are exhausted (P3). Those paths raised pass rate over B0
at about $0.0075 per question versus $0.0060 for B0—more spend, but nowhere
near B1 or P4—and kept p95 latency near ten seconds instead of thirty.

That P1, P2, and P3 are statistically indistinguishable matters for how you
read the paper. This is not an accuracy horse race among three winners. It
is evidence that several targeted designs converge on similar reliability
gains when feedback is external and recovery is scoped to the failing stage
or a trusted prefix. The engineering choice is which mechanism fits your
graph—stage verify-and-retry, checkpoint restore, or degrade-on-exhaustion—
not which one “won” HotpotQA by a point or two.

P4’s underperformance is easier to understand once you take LLM-as-judge
limits seriously. Related Work already notes that judge models carry biases
and soft accepts. We hit a concrete version of that in development: the
first verifier prompt rubber-stamped almost every draft (ACCEPT on every
question that reached the gate), so the “gate” was not gating. After we
tightened the checklist, added deterministic citation checks, and
fail-closed on parse errors, the verifier did reject and occasionally
re-ran the Synthesizer—but pooled pass rate still did not clear
significance against B0, while cost and p95 stayed high. A second LLM on
the critical path is not free, and it is only as useful as its willingness
to say no for the right reasons. That is a design lesson, not just a
non-significant p-value.

More broadly, multi-agent reliability looks less like “add another agent”
and more like orchestration hygiene: external checks at stage boundaries,
immutable checkpoints after trusted passes, and a planned degrade path when
recovery fails. Patterns from CRITIC-style tool critique and AgentDebug-style
targeted re-roll beat undifferentiated retry here. Patterns that multiply
full agent calls without cheap external signals did not pay for themselves
on this testbed. Builders should budget verification the way they budget
any other stage—against measured failure, latency, and cost—not against how
careful the architecture diagram looks.

---

## Limitations

These claims have sharp edges.

**Narrow task and small set.** We used 40 HotpotQA multi-hop questions and
one pipeline shape (plan → retrieve → synthesize → format). Coding agents,
support triage, or tool-heavy workflows may fail differently. We do not
claim the same ranking holds there.

**Scorer.** Pass/fail uses normalized token-coverage matching against short
gold answers. It can fail a reasonable paraphrase and does not score
citation quality on its own. Relative comparisons across conditions stay
fair because every condition uses the same scorer; absolute pass rates
should be read with that limit in mind.

**Single patterns only.** We did not test compositions (e.g. P1 inside P2,
then P3 as last resort). Stacked policies might do better—or cost more for
little gain. That is left open.

**Modest trial counts.** B0/B1/P1/P2/P3 have three trials (pooled n = 120);
P4 has two (n = 80). That is enough for the comparisons we report at
temperature 0, and weaker than large multi-seed ML evaluations. A few
pairwise edges (notably P1/P2 vs B1) still sit near the decision boundary.

**Single base model.** All primary stages use Claude Sonnet
(`claude-sonnet-4-6`), with Haiku only on P3’s rare cheap path. Other
models may reject, parse, or judge differently. Pattern rankings could
shift.

**No multiple-comparison correction.** Pairwise pass-rate tests are an
exploratory screen at α = 0.05 without family-wise adjustment. Significant
stars should be read that way, not as a fully corrected tournament among
six conditions.
