# Literature Scan: Reliability & Fallback Design Patterns for Multi-Agent LLM Systems

**Research question:** Which fallback strategies most reduce total task failure in multi-agent LLM pipelines, and what latency/cost tradeoff does each carry?

**Scope:** 13 peer-reviewed or widely cited works (2023–2026) covering retry/self-correction, cross-agent verification, production reliability engineering, and failure characterization in LLM agent systems.

---

## 1. Retry, Fallback, and Self-Correction in LLM Pipelines

### 1. Self-Consistency Improves Chain of Thought Reasoning in Language Models
- **Authors:** Xuezhi Wang, Jason Wei, Dale Schuurmans, Quoc V. Le, Ed H. Chi, Sharan Narang, Aakanksha Chowdhery, Denny Zhou
- **Year / Venue:** 2023, ICLR
- **Link:** [arXiv:2203.11171](https://arxiv.org/abs/2203.11171)
- **Core claim:** Sampling multiple independent reasoning paths and taking a majority vote over final answers substantially improves reasoning accuracy over greedy chain-of-thought decoding, without additional training.
- **Relation to RQ:** Establishes the simplest *retry-with-aggregation* fallback pattern—redundant generation plus voting reduces failure at the cost of linearly scaling inference calls and latency.

### 2. Reflexion: Language Agents with Verbal Reinforcement Learning
- **Authors:** Noah Shinn, Federico Cassano, Edward Berman, Ashwin Gopinath, Karthik Narasimhan, Shunyu Yao
- **Year / Venue:** 2023, NeurIPS
- **Link:** [arXiv:2303.11366](https://arxiv.org/abs/2303.11366)
- **Core claim:** Agents can improve across trials by converting environment feedback into natural-language self-reflections stored in episodic memory, achieving large gains on coding and decision-making benchmarks without weight updates.
- **Relation to RQ:** A canonical *reflect-and-retry* loop for single-agent pipelines; demonstrates failure recovery when external scalar/binary feedback is available, but does not quantify multi-strategy cost/latency tradeoffs.

### 3. CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing
- **Authors:** Zhibin Gou, Zhihong Shao, Yeyun Gong, Yelong Shen, Yujiu Yang, Nan Duan, Weizhu Chen
- **Year / Venue:** 2024, ICLR
- **Link:** [arXiv:2305.11738](https://arxiv.org/abs/2305.11738)
- **Core claim:** LLMs can iteratively verify and revise outputs when critiques are grounded in external tools (search engines, code interpreters), improving QA, math, and toxicity tasks in a verify-then-correct loop.
- **Relation to RQ:** Models a *tool-grounded fallback* strategy—reliability gains depend on verifier quality and add per-iteration tool-call latency and API cost; directly relevant to designing fallback tiers with external validators.

### 4. Large Language Models Cannot Self-Correct Reasoning Yet
- **Authors:** Jie Huang, Xinyun Chen, Swaroop Mishra, Huaixiu Steven Zheng, Adams Wei Yu, Xinying Song, Denny Zhou
- **Year / Venue:** 2024, ICLR
- **Link:** [arXiv:2310.01798](https://arxiv.org/abs/2310.01798)
- **Core claim:** Under *intrinsic* self-correction (no external feedback), LLMs often fail to improve—and frequently degrade—on reasoning benchmarks; prior positive results often relied on oracle labels or unfair baselines.
- **Relation to RQ:** Sets a critical boundary condition: naive self-critique retry loops are unreliable fallbacks; motivates comparing fallback strategies that differ in feedback source (intrinsic vs. tool vs. cross-agent).

### 5. When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs
- **Authors:** Ryo Kamoi, Yusen Zhang, Nan Zhang, Jiawei Han, Rui Zhang
- **Year / Venue:** 2024, TACL
- **Link:** [ACL Anthology](https://aclanthology.org/2024.tacl-1.78/)
- **Core claim:** Synthesizes self-correction literature and argues the bottleneck is feedback quality; reliable correction requires external signals, task-specific verifiability, or fine-tuning—not prompted self-evaluation alone.
- **Relation to RQ:** Provides the conceptual map for fallback design choices (intrinsic vs. external feedback) and warns that many proposed retry strategies are evaluated under conditions that overstate production viability.

### 6. FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance
- **Authors:** Lingjiao Chen, Matei Zaharia, James Zou
- **Year / Venue:** 2024, Transactions on Machine Learning Research (TMLR)
- **Link:** [arXiv:2305.05176](https://arxiv.org/abs/2305.05176)
- **Core claim:** Introduces prompt adaptation, model approximation, and LLM cascades—sequentially escalating to more capable models only when a scoring function deems the current response unreliable—achieving large cost savings with competitive accuracy.
- **Relation to RQ:** The closest prior work on explicit *cost–reliability tradeoffs* via model escalation; however, it targets single-query routing rather than multi-agent pipeline failures and does not jointly optimize latency tails under agent orchestration.

---

## 2. Self-Verification and Cross-Agent Verification

### 7. Improving Factuality and Reasoning in Language Models through Multiagent Debate
- **Authors:** Yilun Du, Shuang Li, Antonio Torralba, Joshua B. Tenenbaum, Igor Mordatch
- **Year / Venue:** 2024, ICML (PMLR 235)
- **Link:** [arXiv:2305.14325](https://arxiv.org/abs/2305.14325)
- **Core claim:** Multiple LLM instances propose answers, critique one another over several rounds, and converge on a consensus, improving math, strategic reasoning, and factual consistency over single-agent baselines.
- **Relation to RQ:** A foundational *cross-agent verification* pattern; increases reliability through redundant agents but multiplies token cost and round-trip latency—exactly the tradeoff space your RQ targets.

### 8. Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena
- **Authors:** Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin, Zhuohan Li, Dacheng Li, Eric P. Xing, Hao Zhang, Joseph E. Gonzalez, Ion Stoica
- **Year / Venue:** 2023, NeurIPS (Datasets and Benchmarks Track)
- **Link:** [arXiv:2306.05685](https://arxiv.org/abs/2306.05685)
- **Core claim:** Strong LLMs can serve as automated judges correlating >80% with human preferences, but exhibit systematic biases (position, verbosity, self-enhancement) that must be mitigated in evaluation pipelines.
- **Relation to RQ:** Underpins the *LLM-as-verifier* fallback tier common in multi-agent systems; reliability of any judge-gated retry loop depends on verifier calibration, directly affecting false-retry and missed-failure rates.

---

## 3. Reliability Engineering for LLM Systems in Production

### 9. LLMRCA: Multilevel Root Cause Analysis for LLM Applications Using Multimodal Observability Data
- **Authors:** Gou Tan, Zilong He, Min Li, Haiyu Huang, Yilun Wang, Pengfei Chen, Giuliano Casale, Chuanfu Zhang
- **Year / Venue:** 2026, ACM Transactions on Software Engineering and Methodology (TOSEM); presented at FSE 2024
- **Link:** [DOI:10.1145/3806200](https://doi.org/10.1145/3806200)
- **Core claim:** Proposes an unsupervised RCA framework combining metrics, logs, and traces to diagnose both performance regressions and *silent quality faults* in production LLM/RAG applications.
- **Relation to RQ:** Frames production reliability as observability-driven diagnosis rather than inference-time fallback; highlights that HTTP-200 failures require trajectory-level monitoring—the measurement substrate needed to evaluate whether fallbacks actually reduce end-to-end task failure.

### 10. Exploring LLM-based Agents for Root Cause Analysis
- **Authors:** Devjeet Roy, Xuchao Zhang, Rashi Bhave, Chetan Bansal, Pedro Las-Casas, Rodrigo Fonseca, Saravan Rajmohan
- **Year / Venue:** 2024, FSE (Industry Track)
- **Link:** [Microsoft Research](https://www.microsoft.com/en-us/research/publication/exploring-llm-based-agents-for-root-cause-analysis/)
- **Core claim:** ReAct-style LLM agents equipped with retrieval and diagnostic tools can perform competitive RCA on cloud incidents, especially when given access to the same external services human on-call engineers use.
- **Relation to RQ:** Demonstrates agentic *recovery workflows* in production incident management; relevant as an operational context where multi-step fallback and tool-use reliability directly affect mean time to resolution and cost.

---

## 4. Failure Characterization in LLM Agent Systems (Survey-Level)

### 11. A Survey on Large Language Model based Autonomous Agents
- **Authors:** Lei Wang, Chen Ma, Xueyang Feng, Zeyu Zhang, Hao Yang, Jingsen Zhang, Zhiyuan Chen, Jiakai Tang, Xu Chen, Yankai Lin, Wayne Xin Zhao, Zhewei Wei, Ji-Rong Wen
- **Year / Venue:** 2024, *Frontiers of Computer Science*
- **Link:** [arXiv:2308.11432](https://arxiv.org/abs/2308.11432)
- **Core claim:** Provides a unified framework for agent construction (profile, memory, planning, action) and surveys applications and evaluation across domains, identifying open challenges in capability acquisition and assessment.
- **Relation to RQ:** Situates multi-agent pipelines within the broader agent architecture space; useful for mapping where fallback hooks (planning retries, action re-execution, memory refresh) can be inserted, though it does not compare mitigation strategies empirically.

### 12. Large Language Model Reasoning Failures
- **Authors:** Peiyang Song, Pengrui Han, Noah Goodman
- **Year / Venue:** 2026, TMLR
- **Link:** [arXiv:2602.06176](https://arxiv.org/abs/2602.06176)
- **Core claim:** First comprehensive survey of LLM reasoning failures, classifying them by reasoning type (embodied vs. formal/informal) and failure class (architectural, domain-specific, robustness), with mitigation strategies per category.
- **Relation to RQ:** Offers survey-level failure taxonomy beyond any single agent framework; helps define *what* fallbacks must prevent (e.g., robustness vs. planning failures) when designing comparative experiments.

### 13. Where LLM Agents Fail and How They Can Learn From Failures
- **Authors:** Kunlun Zhu, Zijia Liu, Bingxuan Li, Muxin Tian, Yingxuan Yang, Jiaxun Zhang, Pengrui Han, Qipeng Xie, Fuyang Cui, Weijia Zhang, Xiaoteng Ma, Xiaodong Yu, Gowtham Ramesh, Jialian Wu, Zicheng Liu, Pan Lu, James Zou, Jiaxuan You
- **Year / Venue:** 2025, arXiv preprint (AgentDebug; presented at MSLD 2026)
- **Link:** [arXiv:2509.25370](https://arxiv.org/abs/2509.25370)
- **Core claim:** Introduces AgentErrorTaxonomy and AgentErrorBench for modular failure attribution (memory, reflection, planning, action, system), plus AgentDebug—a debugging framework that isolates root-cause errors and enables iterative recovery, yielding up to 26% relative task-success gains.
- **Relation to RQ:** Closest prior work on *failure recovery* in agent pipelines; demonstrates that targeted fallback (root-cause correction + re-rollout) beats undifferentiated retry, but evaluates one recovery mechanism rather than comparing fallback strategy families on cost and latency.

---

## Gap Analysis

Prior work establishes a rich menu of reliability techniques—self-consistency voting, reflection loops, tool-grounded critique (CRITIC), model cascades (FrugalGPT), multi-agent debate, and LLM-as-judge gating—but evaluates each largely in isolation and often reports accuracy or task success without jointly reporting **end-to-end failure rate, p95 latency, and dollar cost per successful task**. Negative results (Huang et al., 2024; Kamoi et al., 2024) show that naive self-correction is an unreliable fallback, while positive results (CRITIC, Reflexion, debate) demonstrate recovery is possible when feedback is well-sourced—but none systematically asks *which fallback tier to invoke when*, or how strategies compare under a fixed reliability budget.

Production reliability research (LLMRCA, FSE RCA agents) focuses on post-hoc diagnosis of deployed systems rather than proactive, in-pipeline mitigation design. General LLM agent and reasoning-failure surveys (#11, #12, #13) explain *why* agents fail and where recovery hooks might attach, but stop short of prescribing or benchmarking orchestration-level fallback policies against one another. FrugalGPT addresses cost–quality tradeoffs for model routing but not multi-agent orchestration failures (cascading errors, verification gaps, misrouted retries).

**Your paper's contribution sits in the intersection:** a systematic, empirical comparison of fallback strategies—retry, escalate, re-route, cross-verify, degrade gracefully—applied at orchestration boundaries in multi-agent LLM pipelines, measured simultaneously on **task failure reduction, latency, and cost**. Prior art proposes and validates individual patterns; your work would be the first (to our knowledge) to treat them as a *design space* and quantify their Pareto frontiers under controlled multi-agent workloads, turning ad hoc reliability patches into an engineering discipline with actionable tradeoff curves.

---

## Coverage Map

| Theme | Papers |
|---|---|
| Retry / self-correction / fallback | #1–6 |
| Cross-agent verification | #7–8 |
| Production reliability engineering | #9–10 |
| Failure characterization (survey-level) | #11–13 |
