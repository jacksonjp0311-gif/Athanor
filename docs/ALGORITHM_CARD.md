# ATHANOR Algorithm Card (v2.6.0)

## Purpose

ATHANOR is a **gate for self-modification**. Before a proposed change to a system (parameters, code, policy) is committed, it measures how much the change makes the system's internal state or behaviour *drift*. It turns that drift into a coherence score and issues a hard verdict, APPROVE / REFINE / REJECT, and every verdict is recorded in a tamper-evident ledger. It is a **drift limiter and audit layer**. It is **not** a correctness checker or an optimiser.

## Inputs and outputs

| | |
|---|---|
| **Input** | A *trajectory* `X ∈ ℝ^{T×D}` describing the change. In the built-in loop this is telemetry from a candidate. In the self-modification experiment it is the cumulative per-probe edit vector. Plus the config: τ, refine floor, optional gates, optional validity inputs and adaptive schedule. |
| **Output** | Verdict ∈ {APPROVE, REFINE, REJECT}, a reason, `checks[]` (each gate's value, limit and pass/fail), and summary metrics (ΔΦ mean/std, C mean/std, H7, …). In a run, also a hash-chained ledger row and a run digest. |

## Definitions

For a trajectory `x_0 … x_{T−1}`:

| Symbol | Definition | Code |
|---|---|---|
| ΔΦ_t (l2) | `‖x_{t+1} − x_t‖₂`, t = 0…T−2 | `core.coherence.delta_phi` |
| ΔΦ_t (cosine) | `arccos( ⟨x_t, x_{t+1}⟩ / (‖x_t‖‖x_{t+1}‖) )` | same |
| C_t | `1 / (1 + |ΔΦ_t|)` ∈ (0, 1] | `coherence_from_dphi` |
| H7 | `mean_t [ C_t ≥ τ ]` ∈ [0, 1], the fraction of steps that stay coherent | `h7_horizon` |
| Equivalent drift limit | `C_t ≥ τ ⇔ ΔΦ_t ≤ 1/τ − 1` (τ = 0.7 ⇒ ΔΦ ≤ 0.4286) | |

**Self-modification instantiation** (`selfmod/experiment.py`). For an edit `f_old → f_new` and probe inputs `x_1…x_P` (P = 32):
`d_t = [ |f_new(x_t) − f_old(x_t)| / (σ_y · tol) , w_s · S(old, new) ]`, with 1000 used where either version raises or is non-finite. `S` is the normalised multiset distance of AST token bags. The trajectory is `X = [0; cumsum(d)]`, so `ΔΦ_t = ‖d_t‖`, and H7 is the fraction of probes on which the edit stays coherent.

## Verdict rules (`agents/verifier_agent.py`)

```
H7 < refine_floor               → REJECT  ("H7 below refine floor")
refine_floor ≤ H7 < τ           → REFINE  ("H7 in refine band")
H7 ≥ τ:
    if H20 enabled and I20 < min_immunity     → REFINE
    if H44 enabled and (H7 − τ) < min_excess  → REFINE
    otherwise                                 → APPROVE
```

Optional gates can only downgrade APPROVE to REFINE. They never rescue a REJECT.

- **H20 noise immunity:** `ΔΦ' = ΔΦ + U(−σ, σ)` (seeded per candidate), `C' = 1/(1+|ΔΦ'|)`, `I20 = clip(1 − mean|C' − C| / mean|C|, 0, 1)`. Passes if `I20 ≥ min_immunity`.
- **H44 boundary excess:** `H7 − τ ≥ min_excess`, i.e. a required margin over the gate.

**Validity pre-gate** (`core/validity.py`, new in 2.5.0). Call the candidate on a validation input set. Any exception (ArithmeticError, ValueError, TypeError) or non-finite output means a **hard reject before the coherence gate runs**. In the self-mod experiment the validation set is the 32 probes plus the 40 training inputs, and optionally an evenly spaced grid over the training-input range.

**Adaptive drift tolerance** (selfmod, new in 2.5.0, off by default). Only the behaviour term is scaled:

```
e      = rmse_train / σ_y        (basis "current", or "best" = best-so-far, which can only tighten)
tol₀   = clip(γ · e^p, floor, cap)
tol(t) = floor + (tol₀ − floor) · 2^(−t/t½)      (if t½ set)
```

## Pseudocode: one governed self-modification step

```
propose edit e from current self s (seeded by (seed, step, attempt))
if not improves_minibatch(e): discard
if validity enabled and not valid(e on V): discard                  # hard pre-gate
X ← trajectory(s, e); v ← verdict(X)                                # ΔΦ → C → H7 → rules above
k ← 0
while v = REFINE and k < refine_attempts:                           # deterministic REFINE path
    k += 1; e ← gentler edit at scale 0.5^k; re-check improvement, validity; v ← verdict(...)
commit e iff improves and valid and v = APPROVE
append ledger row {verdict, reason, checks, refine_trail, metrics, source_sha256, prev_hash, row_hash}
```

The built-in evolution loop (`evolution/dgm_loop.py`) is the same idea over a population. Each child is proposed, gets telemetry, is verified, is REFINEd (σ·0.75ᵏ), and is scored with `F = α·q + (1−α)·H7`, `q = 1/(1+‖δ‖)`. A generation's best child becomes the parent **only if APPROVED**.

## Defaults and tuned values

| Parameter | Default | Tuned (self-mod, `TUNED_ADAPTIVE`) | Conservative tuned (`TUNED_ADAPTIVE_CONSERVATIVE`) |
|---|---|---|---|
| τ (`threshold_h7`) | 0.70 | 0.70 | 0.75 |
| refine_floor | 0.50 | 0.50 | 0.50 |
| refine_attempts | 2 | 2 | 2 |
| H20 / H44 | off | off | off |
| validity pre-gate | off (core loop); per arm in self-mod | on | on |
| adaptive γ | off | 6 | 6 |
| p / basis / cap / floor / t½ | 1 / current / ∞ / 1 / none | 3 / best / 6 / 0.7 / 50 | 3 / best / 6 / 0.7 / 50 |
| structure weight w_s | 0.5 | 0.5 | 0.5 |

Tuned on seeds 100–115 only. See [TUNING_LOG.md](TUNING_LOG.md).

## Complexity

| Operation | Cost |
|---|---|
| ΔΦ, C, H7 for a trajectory | O(T·D) time, O(T) extra memory |
| H20 gate | O(T) plus one seeded RNG draw |
| Validity pre-gate | O(|V|) candidate evaluations |
| Self-mod edit check | O(P + |V| + minibatch) program evaluations, each O(expression size ≤ 40 nodes) |
| Ledger append / verify | O(row size) SHA-256 per row; verify is O(N rows) |
| Built-in loop | O(G · N · (1 + refine) · T · D²) (telemetry is a D×D linear map per step) |

## Guarantees (tested)

- **Determinism:** same config and software stack ⇒ identical verdicts, ledger and run digest. Random streams are derived per (seed, gen/step, idx, attempt).
- **Tamper evidence:** editing, deleting, inserting or reordering ledger rows makes `athanor verify` fail at the first bad row.
- **Monotone gating:** optional gates and the validity pre-gate can only make a decision stricter.
- **Default-off changes:** with default config, 2.5.0 reproduces 2.4.0 results exactly, and 2.6.0 reproduces the committed 2.5.0 self-mod results exactly (tested).
- **Governed invariant:** in governed arms, no edit with a verdict other than APPROVE is ever committed.

## Non-guarantees

- **Not a correctness or safety proof.** H7 bounds the *fraction* of probes with large drift. An edit that is wrong but changes little passes. In 2.4.0, 639 governed commits still worsened held-out error.
- **Not a crash detector.** On the ungoverned trajectory, the gate would have approved 20 of 23 breaking edits. Use the validity pre-gate, but note that validity only covers the inputs it checks: on held-out seeds, validity-only still committed 10 breaking edits.
- **Not tamper-proof:** a whole-file rewrite with re-hashing isn't detected unless the run digest is stored elsewhere.
- **Cross-platform bit equality** of floats is not guaranteed.

## Failure modes (measured)

| Failure | Evidence |
|---|---|
| Too strict ⇒ frozen | τ 0.8 approves no structural edit (MSE stays 2.971 on all tuning seeds) |
| Too loose ⇒ unsafe | τ 0.5: 54 severe regressions on the tuning seeds |
| Feedback loop in adaptive tolerance (basis = current) | Tolerance reached 278 after a regression. Severe 30 vs 8 for the best-so-far basis |
| Narrow tuned optimum overfits | Selected setting: 8 severe on tuning seeds → 34 on held-out seeds |
| Breakage between validation inputs | Validity-only: 10 broken commits on held-out seeds |
| Slower improvement | Non-adaptive governed: median steps to MSE < 1.5 is 404.5 vs 8.5 ungoverned |
| Probes smaller than deployment inputs (TSP, 2.6) | Every committed break in the governed TSP arms was an APPROVEd timeout or crash that only occurs on held-out instances larger than any probe |
| Step-based decay is task-specific (TSP, 2.6) | Carried-over t½ = 50 locks out the one large beneficial edit after about 60 steps; 9 of 16 held-out runs never reach good |
| Fixed tolerance freezes on a big "unlock" edit (TSP, 2.6) | Non-adaptive Athanor: 0 commits on all 16 held-out seeds |

## Evaluation summary (held-out seeds 0–15, 1000 steps, self-modifying program)

| Arm | broken | severe | worst MSE | MSE@100 | MSE@1000 | best-ever | steps < 1.5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ungoverned | 23 | 140 | 2.2e143 | 1.173 | 0.862 | 0.206 | 8.5 |
| validity | 10 | 118 | 3.3e247 | 1.276 | 0.728 | 0.249 | 8.5 |
| athanor | 0 | 3 | 528 | 2.250 | 1.110 | 0.899 | 404.5 |
| validity + athanor | 0 | 3 | 528 | 2.250 | 1.110 | 0.899 | 404.5 |
| athanor-adaptive (tuned) | 21 | 53 | 2.1e21 | 1.037 | 0.807 | 0.550 | 14.5 |
| validity + athanor-adaptive (tuned) | 0 | 34 | 2.1e21 | 1.011 | 0.697 | 0.527 | 14.5 |
| validity + athanor-adaptive τ 0.75 (conservative) | 0 | 2 | 3.8 | 1.247 | 0.903 | 0.819 | 34.5 |

Source: [`selfmod/arms_results.md`](selfmod/arms_results.md). Synthetic-bench results are in the README. Scope: one small symbolic-regression self-modifier, not an LLM or a general agent.

## Transfer to a second system (v2.6.0: self-modifying TSP solver)

The question: does the v2.5 conservative setting work, **without retuning**, on a larger and different
self-modifier? The system is a six-function TSP solver module that rewrites its own source by AST mutation. It
has real crashes, deterministic loop timeouts, silent wrong answers (tours that drop cities and look shorter to
the agent) and held-out regressions. The full definition is in [tsp_selfmod.md](tsp_selfmod.md).

**Unchanged components:** `VerifierAgent` (the ΔΦ → C → H7 rules), `validity_check` and the adaptive schedule
(`scheduled_tolerance`, factored out of 2.5 with bit-identical behaviour).

**Changed only by definition (fixed a priori, not tuned):** ΔΦ per probe is `|ΔL|/(L·κ·tol)` with κ = 0.10,
plus `w_s`·structural distance. The tolerance error term is `e = (train_ratio − 1)/κ`.

| Held-out seeds 0–15, 1000 steps | broken (crash/timeout/silent) | severe | held@50 | held@1000 | never ≤ 1.05 |
|---|---|---:|---:|---:|---:|
| ungoverned | 16 (0/1/15) | 17 | broken | broken | 10 |
| validity | 4 (0/4/0) | 21 | 1.177 | 1.046 | 0 |
| athanor / validity + athanor (fixed tol) | 0 | 0 | 1.177 | 1.177 | 16 (frozen) |
| v2.5 conservative, carried over | 4 (1/3/0) | 5 | 1.177 | 1.100 | 9 |
| v2.5 tuned, carried over | 6 (0/6/0) | 7 | 1.167 | 1.053 | 6 |
| retuned on 100–115 (τ 0.78, no decay) | 2 (0/2/0) | 2 | 1.096 | 1.046 | 3 |

**Answer: partial transfer.**
- The carried-over conservative setting kept the governor's *kind* of benefit: severe regressions fell 21 → 5 vs
  validity only, and no run ended broken.
- It did not keep its 2.5 *degree* of safety. It had 4 committed breaks, as many as validity alone, and above the
  ≤ 2 feasibility rule it met in 2.5.
- It lost its speed: 9 of 16 runs never reached good.
- A 36-setting retune on separate seeds and separate instances fixed most of this, and generalised: 2/4 →
  2/2 broken/severe from tuning to held-out.

**What did transfer exactly** is the mechanism ([TUNING_LOG.md](TUNING_LOG.md#260-transfer-to-the-tsp-self-modifier)
has the derivation): an edit passes iff `tol ≥ r₍⌈τP⌉₎ · τ / (κ(1 − τ))`. This predicted the freeze boundaries
measured in tuning.

**What the governor cannot do, on either system:** see failures outside the inputs it runs. The counterfactual
gate rejected 15 of 16 ungoverned silent-wrong-answer breaks, because they change probe behaviour. It approved
the timeout that only appears on large instances.
