# The Athanor method: tuning and governing a self-modifying system

> A reusable, system-agnostic procedure distilled from what Athanor actually did between v2.1.0 and v2.7.0.
> Every number here comes from a document in this repo: [TUNING_LOG.md](TUNING_LOG.md),
> [selfmod/arms_results.md](selfmod/arms_results.md), [selfmod.md](selfmod.md), [benchmark/results.md](benchmark/results.md),
> [EVALS.md](EVALS.md) and the [CHANGELOG](../CHANGELOG.md). The worked example is one small symbolic-regression
> self-modifier, so treat the numbers as an illustration of the method, not as general laws.

## The loop at a glance

```text
            ┌──────────────────────────── pre-register ─────────────────────────────┐
            │ objective · feasibility limits · tuning seeds · held-out seeds · stop rule│
            └──────────────────────────────────┬─────────────────────────────────────┘
                                               ▼
   ┌─────────── tuning seeds only ───────────────────────────────────────────────────┐
   │ R1 broad sweep → R2–3 diagnose → R4–6 structured search → R7 refine → R8 sensitivity │
   │       every setting logged (log.json)          stop when a round improves < 2 %     │
   └──────────────────────────────────┬──────────────────────────────────────────────┘
                                      ▼
              fit the math from the log only  (Pareto, cliffs, feedback, correlations)
                                      ▼
        fix the pick + a conservative neighbour  ──►  held-out seeds, run ONCE
                                      ▼
         every failure ──► bug2eval case (evals/cases)   every config ──► registry (semver + hash)
                                      ▼
   promote = eval suite passes with the candidate injected  AND  Athanor verdict vs incumbent on fresh seeds
                                      ▼
                         next version; the suite only grows
```

## 1. Pre-register the objective and the feasibility limits

Write the rule down **before** the first run, then don't change it.

- **Feasible** (Athanor 2.5.0): at most **2** commits that broke the program and at most **10** severe regressions (more than 2× worse held-out MSE, or broken), summed over 16 tuning seeds.
- **Objective:** among feasible settings, minimise the median held-out MSE at step 100 (speed). Tie-break on MSE at step 1000.
- **Stop rule:** stop when a round improves the best feasible objective by less than **2 %**.

Limits are hard constraints, not weights in a score. That keeps "faster but less safe" from passing for progress.

## 2. Keep tuning seeds and held-out seeds apart, and run held-out once

- **Tuning seeds 100–115** for every tuning decision. **Held-out seeds 0–15** are used **once**, after tuning stops.
- A fresh third set (**200–215**) is used only by the promotion gate (section 6), so the gate does not reuse either of the other two.

## 3. Narrow in rounds, with a fixed stop rule

| Phase | Athanor round | What happened (tuning seeds) |
|---|---|---|
| Broad sweep | 1 (24 settings) | τ ∈ {0.5…0.8} × γ: speed only came by giving up safety (τ 0.5: severe 54–123); τ 0.8 froze the agent |
| Diagnosis | 2–3 | No feasible settings. The best near-miss had severe 16. A dense validity grid barely helped |
| Structured search | 4–6 | Diagnosed a **feedback loop**. Best-so-far basis + cap, then a **time-decayed slack** (t½) gave the first feasible fast settings (round 6: MSE@100 **0.750**, severe 8, broken 0) |
| Local refinement | 7 (54 settings) | **0 % improvement**, so the stop rule triggered |
| Sensitivity | 8 (10 settings) | Almost every single-parameter change broke feasibility: a narrow spike |

Plateau trace (best feasible MSE@100): rounds 1–5: 2.247 → round 6: 0.750 → round 7: 0.750 → round 8: 0.750.

## 4. Log every experiment, and fit the math only from the log

All **199** entries (195 tuned settings plus 4 baselines) are in [`tuning/log.json`](tuning/log.json). The analysis script reads only that log. What came out:

- **Pareto frontier.** 8 non-dominated points in (MSE@100, severe), fitted on a log-log scale: **severe + 1 ≈ 5.2 · MSE@100^−1.9**. Halving the step-100 error costs about **3.7×** more severe regressions. It is a fit to 8 points on one task.
- **Threshold cliff.** `C = 1/(1+ΔΦ)`, so `C ≥ τ ⇔ ΔΦ ≤ ΔΦ_max = 1/τ − 1`. At τ = 0.8, ΔΦ_max = 0.25, which is exactly the cost of the smallest structural edit (`w_s · 0.5`). Nothing structural passes, and MSE@100 stays at 2.971. τ is a step function, not a dial: severe 54 / 75 / 5 / 0 for τ 0.5 / 0.6 / 0.7 / 0.8.
- **Feedback trap.** A tolerance driven by the *current* error loosens the gate right after a regression. Measured: severe **30** vs **8** with the best-so-far basis, and the tolerance reached 278 right after a regression.
- **Off the frontier, speed and safety are unrelated.** Spearman ρ(MSE@100, severe) = **0.008** across adaptive settings. Most settings are simply dominated, and only the specific structure found in rounds 4–6 reaches the frontier.

## 5. Check for overfitting, and keep a conservative neighbour

The sensitivity round showed a narrow optimum, so **before** looking at held-out seeds a second setting was fixed: the τ 0.75 neighbour (severe 1 on the tuning seeds).

| Held-out seeds 0–15 | broken | severe | MSE@100 | MSE@1000 |
|---|---:|---:|---:|---:|
| ungoverned | 23 | 140 | 1.173 | 0.862 |
| selected (τ 0.70, adaptive) | 0 | **34** (was 8 on tuning seeds) | 1.011 | 0.697 |
| conservative (τ 0.75, adaptive) | 0 | **2** | 1.247 | 0.903 |

The selected setting **overfit its safety (8 → 34)**. The conservative one generalised. Its cost was reported too: median steps to MSE < 1.5 was 34.5 vs 8.5 for ungoverned.

## 6. Capture every failure, version every config, and gate every promotion

From 2.7.0 on (details in [EVALS.md](EVALS.md)):

- **Every failure becomes a [Bug2Eval](https://github.com/jacksonjp0311-gif/bug2eval) case** that must discriminate: before fails, after passes. The seeded suite has 4 real bugs fixed in 2.1.0 and 4 real tuning failures: the overfit (34 → 2), the feedback trap (30 → 8), the threshold cliff (never → 489 steps), and no governor (23/140 → 0/3).
- **Every config is an immutable, content-hashed registry entry** with semver (arm change = major, cfg change = minor), a parent and a reason. Status lives in a hash-chained ledger.
- **Promotion = eval floor + step-size rule.** The suite must pass with the candidate injected, so it cannot re-break a captured case. Athanor's own ΔΦ → C → H7 verdict compares the candidate's behaviour with the incumbent's on fresh seeds. The tuner can only *register* candidates.
- **Cite the results you rely on, and re-check them before you use them** (2.8, [SEARCH.md](SEARCH.md)). Each case records the exact lines and run records it rests on with their SHA-256, and a tuner candidate pins its rows of the tuning log. Promotion and the next tuning round re-verify them first, and a changed or missing result holds the decision.

## How to apply this to your system: checklist

1. ☐ Name the **change unit** (a parameter vector, a code edit, a prompt) and a **behaviour signature** you can compute for both the old and the new version (outputs on fixed probes, metrics at checkpoints).
2. ☐ Define ΔΦ on that signature, pick τ, and compute **ΔΦ_max = 1/τ − 1**. Check it against the cost of your *smallest legitimate change*, so you don't build a frozen gate.
3. ☐ Write down **feasibility limits** (hard), the **objective**, the **stop rule**, and three disjoint seed sets: **tuning / held-out / gate**.
4. ☐ Add a cheap **validity pre-gate** (crashes, non-finite values), but don't rely on it alone: validity-only still let 10 broken commits and 118 severe regressions through.
5. ☐ Tune in rounds (sweep → diagnose → structure → refine → sensitivity) and **log every setting** with its config and metrics.
6. ☐ Fit relationships **only from the log**: the frontier, cliffs, feedback loops, and correlations off the frontier.
7. ☐ If the optimum is narrow, fix a **conservative neighbour** before the held-out run. Then run held-out **once** and report both settings.
8. ☐ Turn every bug and every failed config into a **discriminating eval case**, and put every config in a **versioned registry**.
9. ☐ Promote only through the gate: **suite passes** with the candidate **and** a governor verdict vs the incumbent on fresh seeds. Record the decision in a hash-chained ledger.
10. ☐ Give every seed set **one purpose** and spend held-out and gate seeds once. Every promotion takes a **fresh gate block** (3.0: `athanor.seedsets`).
11. ☐ Make validity and probe inputs **cover deployment sizes**: the 2.6 probes were smaller than the real inputs, and every governed TSP break hid in that gap.
12. ☐ **Cite** every past result a decision depends on (file + line hashes), and **re-verify** the citations before tuning or promoting on them.
13. ☐ Report what got **worse** as plainly as what got better (speed, best-ever error, seeds where nothing changed).

## How this method was actually run: a human + AI collaboration

James Jackson (the repository owner) set the direction and the bar in plain language. Grok Bot, the assistant (running here as "ATHANOR"), planned each step, built it, ran it on its own computer (a separate Linux box, not James's machine), documented the results, and opened pull requests and releases on GitHub where James could see them. The loop was:

```text
intent (James, plain language) → plan (assistant) → build → measure → honest report → James steers → next version
```

Each version was one pass through the loop. These are the real messages and outcomes:

| Version | James's direction | What was built and measured | What the report said, including the negatives |
|---|---|---|---|
| 2.1.0 | "take my repo and evolve it even further" | Hash-chained ledger, replay, CLI, 4 bug fixes; tests 13 → 30 | Same seed gives different results than 2.0.0 because of the seed fix |
| 2.2.0 | "push it all to main … pro level read me … top tier stability. treat it as such" | Decision record, deterministic REFINE, optional H20/H44 gates, README; 39 tests | Run fingerprints no longer match 2.1.0; the README makes no benchmark claims |
| 2.3.0 | "Do it all and get it pushed to include the release and pip", then "Just make it easy" | Governed vs ungoverned benchmark (8 seeds), GitHub release, install from GitHub; 44 tests | 3 of 8 seeds were identical in both modes; 2 seeds stayed below τ; the task is synthetic; `athanor` on PyPI is taken by another project |
| 2.4.0 | "yea go ahead" (a real self-modifying test, run remotely) | A program that rewrites its own source: broken 0 vs 23, severe 3 vs 140; 53 tests | Much slower (~300 vs ~9 steps to MSE < 1.5); the gate would have approved 20 of the 23 breaking edits |
| 2.5.0 | "Keep tuning … until you perfect it … record any mathematics" | Validity pre-gate, 8 tuning rounds, 199 logged experiments, algorithm card, tuning log; 59 tests | Validity alone was weak; the selected setting overfit (8 → 34); still about 4× slower to first reach MSE < 1.5 |
| 2.6.0 | "Ok keep going" | A second, larger self-modifier (a TSP solver that rewrites its own source) to test whether the tuned setting transfers; retuned on seeds 100–115 (τ 0.78, no time decay); 68 tests | Partial transfer: the carried-over conservative setting had 4 broken / 5 severe on held-out seeds and 9 of 16 runs never reached good; retuned 2 / 2; fixed-tolerance Athanor froze on all 16 seeds; every governed break was on inputs larger than any probe |
| 2.7.0 | "integrate [bug2eval] … so we can version … get more explicit with the configuration tuning" | Bug2Eval suite (4 real bugs + 4 real tuning failures), versioned registry, eval-gated promotion (`adaptive@1.1.0` APPROVE, H7 0.8125), this method; 80 tests | The promoted config had 1 broken commit on the gate seeds (incumbent 0); seeds 0–15 reused in the cases are no longer strictly held-out; see the caveats in [EVALS.md](EVALS.md) |
| 2.8.0 | Approved integrating his AgentSearch repo as an evidence layer | Citations with file and line SHA-256 for every eval case (29), `athanor search`, stale-evidence checks before promotion and tuning; 86 tests | A citation proves bytes are unchanged, not correct; the extra pins an AgentSearch release candidate |
| 3.0.0 | "create a plan to get it operational, tested and benchmarked, pushed to GitHub and passing" | Public adapter API (`athanor.govern`), `doctor`, `demo`, the TSP eval cases T005–T007, never-reused gate seeds, size-scaled TSP validity inputs, and a unified benchmark on fresh seeds 3000–3015; 103 tests | Governed arms trade speed and best-case quality for safety (curve fit: final MSE 0.930 vs 0.433 ungoverned); the curve-fit incumbent sat exactly at its severe limit (10); a runaway-memory failure was found and capped |

Where James's questions changed the work:
- "So it doesn't work?" led to a plain explanation of the safety-for-speed trade-off rather than a softer one.
- "What's this tell us" led to stating that the 2.3.0 benchmark was synthetic, which motivated the real self-modifying test in 2.4.0.

James decided what mattered and when to go further. The assistant was responsible for the plan, the code, running the measurements, and reporting them as measured. Nothing here claims more than that.
