# Results

## Headline

The main result is simple. The three targeted fallback patterns—tool-grounded
retry (P1), checkpointing (P2), and graceful degradation (P3)—raised pass rate
over the no-fallback baseline (B0) by a clear margin, at a modest cost increase.
Blind retry (B1) and cross-agent verification (P4) did not beat B0 on pass rate
at α = 0.05, even though both cost more and both stretch the latency tail.

Pass rates below are pooled question outcomes (n = 120 for B0/B1/P1/P2/P3;
n = 80 for P4). Cost and latency are the pooled figures from the same runs.
Pairwise tests are two-sided two-proportion z-tests and Fisher’s exact tests,
as in the experimental setup.

## Pass rate

Figure 1 shows pass rate by condition, with error bars spanning the trial
min–max and significance markers vs B0.

B0 sits at 60.0% (72/120). P1 and P2 both land at 75.8% (91/120)—a +15.8
percentage-point gain over B0. Both comparisons are significant (z = 2.627,
p(z) = 0.0086; Fisher p = 0.0125). P3 is a bit higher at 78.3% (94/120),
+18.3 pp over B0, and the strongest of the three against the baseline
(z = 3.075, p(z) = 0.0021; Fisher p = 0.0032).

B1 reaches 64.2% (77/120). That is only +4.2 pp over B0, and it is not
significant (p(z) = 0.5059; Fisher p = 0.5947). P4 reaches 70.0% (56/80),
+10.0 pp over B0, also not significant (p(z) = 0.1489; Fisher p = 0.1766).
P4’s sample is smaller (two trials), but the point estimate still does not
clear the bar.

So on pass rate alone: P1, P2, and P3 beat doing nothing. Blind retry and the
verifier gate do not, at least not at a level we can defend from these data.

## Cost vs accuracy

Figure 2 plots average cost per question against pass rate.

B0 is the cheap, lower-accuracy corner at $0.0060/q and 60.0%. P1, P2, and P3
sit together near $0.0075/q with pass rates of 75.8%, 75.8%, and 78.3%. That
is the good-value cluster: roughly a quarter more spend than B0 for a
fifteen-to-eighteen point pass-rate lift.

B1 costs $0.0108/q for 64.2% pass rate—almost twice B0’s cost for a gain that
is not significant. P4 is the expensive outlier at $0.0164/q and 70.0% pass
rate. Both sit in the dominated region of Figure 2: higher cost than P1–P3,
with worse or no better accuracy than that cluster. If the goal is reliability
per dollar, B1 and P4 lose to the cheaper targeted patterns.

(These cost figures are descriptive. With only two or three trial totals per
condition, we do not claim significant cost differences from a formal test on
the trial sample.)

## Latency

Figure 3 shows pooled p95 end-to-end latency on a log scale.

B0, P1, P2, and P3 stay near ten seconds at p95: 10397 ms, 10398 ms, 9591 ms,
and 10369 ms. B1 and P4 do not. B1’s p95 is 34506 ms (~34.5 s). P4’s is
30708 ms (~30.7 s). That is roughly three times the rest of the field.

The reasons match how each condition recovers. B1 re-runs the same stage or
graph on failure, up to its retry cap, with no new evidence and no early
targeted exit. Failed questions stack sequential retries, which fattens the
tail even when the median stays closer to the pack (B1 p50 is 7139 ms). P4
puts a full Verifier agent call on the critical path before the Formatter,
and on reject it may run a second Synthesizer pass (capped at one round per
question). That extra agent work shows up as both higher average cost and a
long p95, whether or not the gate eventually helps the answer.

## P1, P2, and P3 are interchangeable on pass rate

P1, P2, and P3 are statistically indistinguishable from each other on pooled
pass rate. P1 vs P2: both 75.8%, Fisher p = 1.0000. P1 vs P3: 75.8% vs 78.3%,
Fisher p = 0.7589. P2 vs P3: same gap, Fisher p = 0.7589.

We are not claiming one of these three is best. The finding is that three
different targeted designs—tool checks with stage retry, checkpoint rollback,
and degrade-on-exhaustion—land in the same place: clear gains over B0, similar
cost, similar latency tails. Choosing among them is more about engineering fit
than about a winner on this benchmark.

## P4: expensive verification without a significant win

P4 is the counter-intuitive result. It is the most elaborate pattern in the
set: a second LLM gates the Synthesizer draft before formatting, with accept /
reject-with-critique / propose-correction, plus a capped re-synth on reject.
It is also the most expensive condition ($0.0164 per question) and one of the
two worst latency tails (~30.7 s p95).

It did not significantly outperform B0 on pass rate (70.0% vs 60.0%;
p(z) = 0.1489, Fisher p = 0.1766). Against P1–P3 it is numerically lower and
not significantly different from them either (e.g. P3 vs P4: Fisher p = 0.1876),
while costing more than twice as much per question as that cluster.

So in this setup, paying for a full cross-agent verification gate did not buy
a defensible reliability gain over doing nothing—and it lost on cost and
latency to simpler tool-grounded and checkpoint-style fallbacks. That is a
real finding for the paper, not a failed run to soft-pedal.
