# Related Work

## Retry, fallback, and self-correction

A lot of reliability work for LLMs is some form of try again. Self-Consistency
(Wang et al., 2023) samples multiple reasoning paths and majority-votes the
answer. That cuts failure on reasoning tasks, but cost and latency scale with
the number of samples. Reflexion (Shinn et al., 2023) stores natural-language
reflections from environment feedback and retries with that memory. It helps
when you have external scalar or binary feedback. It does not compare several
fallback policies on cost and latency together.

CRITIC (Gou et al., 2024) is closer to what we use in the tool-grounded
condition. The model verifies and revises using external tools (search, code
execution), in a verify-then-correct loop. Gains depend on the quality of those
tool signals, and each iteration adds calls and latency.

Two negative results matter for our design. Huang et al. (2024) show that
*intrinsic* self-correction—asking the model to fix itself with no external
feedback—often fails to help and can make reasoning worse. Earlier positive
numbers often leaned on oracle labels or weak baselines. Kamoi et al. (2024)
survey the self-correction literature and reach the same bottleneck: feedback
quality. Reliable correction needs external signals, task-specific checks, or
fine-tuning—not prompted self-evaluation alone. That is why our targeted
patterns (P1–P3) feed stages checkable facts (retrieval miss, bad citation ID,
broken schema) rather than “please fix your answer.”

FrugalGPT (Chen et al., 2024) is the main prior work that treats cost and
quality as a joint problem. It cascades to stronger models only when a scoring
function says the current answer is unreliable. That is model routing for
single queries. It is not a comparison of orchestration-level fallbacks when a
multi-agent pipeline fails mid-graph, and it does not report p95 latency under
agent handoffs.

## Cross-agent and self-verification

Multiagent Debate (Du et al., 2024) has several LLM instances propose answers,
critique each other, and converge. Factuality and reasoning improve over a
single agent. Token cost and round-trips grow with the number of agents and
rounds. That is the same tradeoff space as our cross-agent verification
condition (P4), but debate is usually the whole method, not a gate at one
handoff inside a fixed pipeline.

LLM-as-a-Judge work (Zheng et al., 2023) shows strong models can score outputs
with high correlation to human preference, and also that judges carry biases
(position, verbosity, self-enhancement). Any verifier-gated retry inherits
those issues. If the judge is soft or biased, you get false accepts or wasted
rejects. We treat that as a reason to measure P4 on failure, latency, and cost
together—not only on whether the gate “looks careful.”

## Production reliability engineering

Production work is mostly about finding what went wrong after deploy, not about
choosing an in-pipeline fallback policy. LLMRCA (Tan et al., 2026) combines
metrics, logs, and traces to diagnose performance regressions and silent quality
faults in LLM/RAG apps. That is useful measurement substrate: many failures
return HTTP 200 and still wrong. Roy et al. (2024) study ReAct-style agents for
cloud incident root-cause analysis, using retrieval and the same diagnostic
tools on-call engineers use. Both lines show agentic recovery in operations.
Neither benchmarks a menu of orchestration fallbacks (retry vs checkpoint vs
degrade vs verify) on task failure, p95 latency, and dollar cost in one
controlled multi-agent testbed.

## Failure characterization surveys

Wang et al. (2024) survey LLM-based autonomous agents and organize construction
around profile, memory, planning, and action. That map is useful for where a
fallback can hook in (re-plan, re-act, refresh memory). It does not empirically
compare mitigation strategies.

Song et al. (2026) survey LLM reasoning failures by reasoning type and failure
class, with mitigation ideas per class. That helps say *what* a fallback should
catch. It stops short of ranking orchestration policies under a shared cost and
latency budget.

Zhu et al. (2025) (AgentDebug) attribute agent errors to modules (memory,
reflection, planning, action, system) and show that isolating a root cause and
re-rolling from there beats undifferentiated retry on their benchmark. That is
the closest prior on recovery *inside* agent pipelines. It validates one
targeted recovery idea. It does not put several fallback families on the same
axes of failure reduction, latency, and cost.

## Where this leaves a gap

Taken together, the literature already offers the pieces: vote and retry
(Self-Consistency), reflect-and-retry (Reflexion), tool-grounded critique
(CRITIC), model cascades (FrugalGPT), multi-agent debate, and LLM-as-judge
gating. Most papers validate one technique on accuracy or task success. Few
report end-to-end failure rate, p95 latency, and dollar cost on the same runs.
Huang and Kamoi show why blind intrinsic self-fix is a bad default.
CRITIC, Reflexion, and debate show recovery can work when feedback is
well-sourced. What is still missing is a side-by-side answer to *which fallback
to use when*, under a fixed multi-agent workload and a joint reliability budget.

Production RCA work diagnoses deployed systems after the fact. Agent and
reasoning-failure surveys explain failure modes and where hooks might attach.
FrugalGPT prices model routing, not cascading errors and verification gaps
inside a Planner→Retriever→Synthesizer→Formatter graph. AgentDebug shows
targeted recovery can beat blind retry for one mechanism.

Our work sits in that gap. We treat fallback strategies as a design space—
no fallback, blind retry, tool-grounded retry, checkpoint rollback, graceful
degradation, and cross-agent verification—applied at orchestration boundaries
in one multi-agent QA pipeline, and we measure them together on pass rate,
latency, and cost. Prior work proposes and validates individual patterns. We
compare the patterns as engineering options with explicit tradeoff curves.
