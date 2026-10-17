<p align="center">
  <img src="docs/assets/athanor-banner.svg" alt="ATHANOR — a deterministic coherence governor for recursive AI systems" width="100%"/>
</p>

<p align="center">
  <a href="https://github.com/jacksonjp0311-gif/Athanor/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/jacksonjp0311-gif/Athanor/actions/workflows/ci.yml/badge.svg?branch=main"/></a>
  <img alt="Python 3.10 | 3.11 | 3.12" src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white"/>
  <a href="https://github.com/jacksonjp0311-gif/Athanor/releases/latest"><img alt="Version 2.7.0" src="https://img.shields.io/badge/version-2.7.0-ffb347"/></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-3ddc97"/></a>
</p>

<p align="center">
  <b>Measure drift. Gate change. Ledger every verdict.</b>
</p>

---

**ATHANOR** is a deterministic coherence governor for recursive, self-modifying systems. Before a candidate change is committed, ATHANOR measures its internal drift **ΔΦ** along a telemetry trajectory, converts it to coherence **C**, computes the stability horizon **H7**, and issues a hard verdict: **APPROVE**, **REFINE**, or **REJECT**. Every verdict, along with the gate checks behind it, is written to a hash-chained ledger. The same seed and config reproduce the same ledger and the same run digest, and `athanor replay` checks that.

## Why it matters

A system that rewrites itself needs a referee that is *outside* the thing being optimized. ATHANOR keeps that referee small and explicit:

- **Coherence comes first.** A change has to meet the H7 stability gate before fitness can promote it to parent.
- **Every verdict is explained.** Each ledger row lists the gates that were evaluated, their values and limits, the REFINE attempts, and the parent the candidate came from.
- **Every run can be audited.** Edited, deleted, inserted, or reordered ledger rows are detected, and a run can be replayed and compared bit-for-bit through its digest.

## Contents
[Governance loop](#governance-loop) · [Quickstart](#quickstart) · [Benchmark](#benchmark-governed-vs-ungoverned) · [Real self-modifying program](#real-world-test-a-self-modifying-program) · [Transfer test](#26-transfer-test-a-self-modifying-tsp-solver) · [Evals & versioned configs](#evals-and-versioned-configs-27) · [Algorithm card](docs/ALGORITHM_CARD.md) · [Method](docs/METHOD.md) · [CLI](#cli-reference) · [Configuration](#configuration-reference) · [Guarantees](#guarantees) · [Run artifacts](#run-artifacts) · [Architecture](#architecture) · [Testing](#testing) · [Theory](#theory--manuscripts) · [Roadmap](#roadmap) · [Changelog](CHANGELOG.md)

## Governance loop

```mermaid
flowchart LR
    P([Parent]) --> PR[Propose child<br/>Gaussian step, capped]
    PR --> T[Telemetry<br/>trajectory x_t]
    T --> D["ΔΦ = ‖x_t+1 − x_t‖"]
    D --> C["C = 1 / (1 + |ΔΦ|)"]
    C --> H["H7 = mean(C ≥ τ)"]
    H --> G{H7 gate}
    G -- "H7 < refine_floor" --> RJ[REJECT]
    G -- "refine band" --> RF[REFINE]
    G -- "H7 ≥ τ" --> OG{Optional gates<br/>H20 · H44}
    OG -- fail --> RF
    OG -- pass --> AP[APPROVE]
    RF -- "σ ← σ·0.75ᵏ, retry ≤ refine_attempts" --> PR
    AP --> S[Select · fitness F]
    RF --> S
    RJ --> S
    S --> A[(MAP-Elites archive)]
    S --> L[(Hash-chained ledger)]
    S -- "best is APPROVE" --> P
```

Optional gates can only **downgrade** APPROVE to REFINE. They never rescue a REJECT and never upgrade a verdict. A generation's best-fitness candidate becomes the new parent **only if** its verdict is APPROVE, and each such decision goes into `decision_record.json`.

## Quickstart

Install straight from GitHub (Python 3.10+):

```bash
pip install git+https://github.com/jacksonjp0311-gif/Athanor.git            # latest main
pip install git+https://github.com/jacksonjp0311-gif/Athanor.git@v2.7.0     # pinned release
```

Each [GitHub release](https://github.com/jacksonjp0311-gif/Athanor/releases) also has the built wheel and sdist attached (for example `pip install athanor-2.7.0-py3-none-any.whl`). ATHANOR is **not published on PyPI**. The name `athanor` on PyPI belongs to an unrelated project, so `pip install athanor` will **not** install this package.

Optional extra for the regression suite and eval-gated config promotion ([docs/EVALS.md](docs/EVALS.md)):

```bash
pip install "athanor[evals] @ git+https://github.com/jacksonjp0311-gif/Athanor.git@v2.7.0"   # adds Bug2Eval
```

For development:

```bash
git clone https://github.com/jacksonjp0311-gif/Athanor.git && cd Athanor
python -m pip install -e ".[dev]"
```

```bash
# 1. run a governed evolution loop
athanor run --config configs/toy_experiment.yaml --tag demo

# 2. verify the hash chain of the verdict ledger
athanor verify data/archives/demo

# 3. replay from the saved config and confirm the digest matches
athanor replay data/archives/demo
```

Each command prints one JSON object to stdout and exits non-zero on failure, so it fits in CI and scripts.

## Benchmark: governed vs ungoverned

`athanor bench` runs the **same self-modification task** twice per seed:

- **governed**: the normal loop, where verdicts gate REFINE retries and parent promotion.
- **ungoverned**: `governor.enabled: false`. ΔΦ, C, H7 and verdicts are still measured and ledgered, but the best-fitness child **always** becomes the parent and nothing is retried.

The task ([`configs/bench.yaml`](configs/bench.yaml)) is built so that only the governor resists drift. Selection is coherence-blind (`alpha: 1.0`, so fitness rewards small proposal steps only), and proposals are large (`proposer_sigma: 0.5`, `proposer_step_cap: 2.0`) over 40 generations × 12 candidates. Telemetry is ATHANOR's built-in synthetic linear dynamics, so these numbers describe this toy system, not any real AI model.

Reproduce exactly (the measured run took about 7 s):

```bash
athanor bench --config configs/bench.yaml --seeds 0-7 --out docs/benchmark --chart docs/assets/benchmark.png
```

<p align="center"><img src="docs/assets/benchmark.png" alt="Governed vs ungoverned: drift, coherence, H7 per generation and verdict counts over seeds 0-7" width="100%"/></p>

Measured with v2.3.0, seeds 0–7. Population means per generation; "last 10" means generations 30–39.

| Metric | Governed | Ungoverned |
|---|---:|---:|
| Mean H7, last 10 gens | **0.866** | 0.637 |
| Mean C, last 10 gens | **0.789** | 0.629 |
| Median ΔΦ, last 10 gens | **0.232** | 0.524 |
| Mean ΔΦ, last 10 gens | **0.440** | 137.168 |
| Worst generation ΔΦ (any seed) | **11.661** | 2575.680 |
| APPROVE / REFINE / REJECT | 3209 / 2 / 629 | 2456 / 173 / 1211 |
| Parent promotions | 265 | 320 |
| Promotions of non-APPROVED parents | 0 | 115 |

**How to read it, including where the governor does *not* win:**

- On **3 of 8 seeds** (2, 3, 7) the two modes are identical, because the ungoverned run never promoted a non-APPROVED parent. The governor only matters once the task drifts.
- On the other 5 seeds the governed run ends with higher H7 and lower drift. The ungoverned mean ΔΦ is dominated by a few blow-ups (seed 6 reaches a last-10 mean ΔΦ ≈ 1015), so the median is the fairer typical-case comparison: 0.232 vs 0.524.
- The governor **does not guarantee** staying above τ. On seeds 0 and 5 the governed population's last-10 H7 is 0.625 and 0.506, below τ = 0.70. It blocks unstable *parents*, but children proposed from a stable parent can still be unstable.
- It has a cost: **55 fewer parent promotions** (265 vs 320), meaning less exploration, which is the price of refusing non-APPROVED changes.

Full per-seed results are in [`docs/benchmark/results.md`](docs/benchmark/results.md) and [`results.json`](docs/benchmark/results.json), including every run digest.

## Real-world test: a self-modifying program

The benchmark above uses synthetic dynamics. [`athanor selfmod`](docs/selfmod.md) tests ATHANOR on an **actual self-modifying program**: an agent that parses its own Python source with `ast`, mutates it, recompiles it and keeps the edit if it lowers error on a noisy 8-point minibatch. Edits can genuinely break it (`log` of a negative, division by zero, overflow). ΔΦ is measured from real changes: output divergence on 32 probe inputs plus AST structural distance. ATHANOR's unchanged ΔΦ → C → H7 → verdict pipeline gates each self-edit.

<p align="center"><img src="docs/assets/selfmod.png" alt="Self-modifying program: governed vs ungoverned over 16 seeds" width="100%"/></p>

16 seeds × 1000 self-edits. Lower is better for every row.

| | Governed | Ungoverned |
|---|---:|---:|
| Commits that **broke** the program on held-out inputs | **0** | 23 |
| Severe regressions (>2× worse held-out error, or broken) | **3** | 140 |
| Worst held-out MSE ever committed | **528** | 2.2 × 10¹⁴³ |
| Median held-out MSE after 100 steps | 2.250 | **1.173** |
| Median held-out MSE after 1000 steps | 1.110 | **0.862** |
| Median best-ever held-out MSE | 0.899 | **0.206** |

**Honest read:** the governed agent avoided almost all catastrophic and breaking self-edits, but it improved **much more slowly** and ended **worse** on the typical seed (ungoverned is better on 9/16 seeds at step 1000). The gate directly blocks most severe regressions: it would have refused 84 of the 140 ungoverned ones. It does **not** reliably detect crashes, though. It would have approved 20 of the 23 breaking edits, because they fail on only a few inputs. The governed run avoids those mostly indirectly, through its slower, lower-drift path. It is a stability-for-speed trade on this toy system. The [full write-up](docs/selfmod.md) covers the ΔΦ definition, the per-seed results and the caveats.

```bash
athanor selfmod --seeds 0-15 --steps 1000 --out docs/selfmod --chart docs/assets/selfmod.png
```

### 2.5: pairing Athanor with a validity check, plus an adaptive schedule

2.5.0 adds a hard **validity pre-gate** (reject edits that crash or go non-finite on the probes and training inputs) and an optional **adaptive drift tolerance**. The tolerance is loose while the agent is far from the target and tightens as its best training error falls and as time passes. It was tuned on separate seeds 100–115 until it plateaued, then evaluated **once** on held-out seeds 0–15:

<p align="center"><img src="docs/assets/selfmod_arms.png" alt="All arms on held-out seeds" width="100%"/></p>

| Held-out seeds 0–15 | broken | severe | worst MSE | MSE@100 | MSE@1000 | best-ever | steps < 1.5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ungoverned | 23 | 140 | 2.2e143 | 1.173 | 0.862 | **0.206** | **8.5** |
| validity only | 10 | 118 | 3.3e247 | 1.276 | 0.728 | 0.249 | 8.5 |
| validity + athanor | **0** | 3 | 528 | 2.250 | 1.110 | 0.899 | 404.5 |
| validity + athanor-adaptive (tuned) | **0** | 34 | 2.1e21 | **1.011** | **0.697** | 0.527 | 14.5 |
| validity + athanor-adaptive, τ 0.75 | **0** | **2** | **3.8** | 1.247 | 0.903 | 0.819 | 34.5 |

**Honest read:**
- A crash check alone isn't enough: it still committed 10 breaking edits and 118 severe regressions.
- The tuned adaptive arm is the fastest at step 1000, but its safety **overfit** the tuning seeds: 8 severe regressions became 34.
- The conservative τ 0.75 neighbour was fixed *before* the held-out run. It keeps 0 broken and 2 severe, and is within 6 % of ungoverned error at step 100 and 5 % at step 1000. It still takes **4× longer** to get below MSE 1.5 and its best-ever error is 4× worse.
- Tuning plateaued on the tuning seeds at MSE@100 = 0.750 with 8 severe (vs ungoverned 0.881 with 127). On the frontier the measured trade-off is about *severe + 1 ≈ 5.2·MSE@100^−1.9*.

Details: [TUNING_LOG.md](docs/TUNING_LOG.md) (all 195 settings, plateau, sensitivity, Pareto chart) · [ALGORITHM_CARD.md](docs/ALGORITHM_CARD.md) (exact definitions, pseudocode, guarantees, failure modes) · [selfmod.md](docs/selfmod.md).

```bash
athanor selfmod-arms --seeds 0-15 --out docs/selfmod --chart docs/assets/selfmod_arms.png
```

### 2.6: transfer test, a self-modifying TSP solver

Does the v2.5 conservative setting work on a *different, larger* self-modifier **without retuning**? The second testbed is a six-function TSP solver module (`priority`, `pick_start`, `construct`, `budget`, `improve`, `solve`) that rewrites its own source with AST mutations. A local LLM proposer was not feasible on CPU here, so the mutations are programmatic. Its failures are real:
- crashes;
- deterministic loop timeouts, from a harness-owned tick counter;
- **silent wrong answers**: tours that drop cities and *look shorter* to the agent's own scoring;
- regressions on larger held-out instances.

The governor, the validity check and the adaptive schedule are reused unchanged. ΔΦ is the relative tour-length change on 16 probe instances (scale κ = 0.10, fixed a priori) plus AST distance.

<p align="center"><img src="docs/assets/tsp_selfmod.png" alt="TSP self-modifier: held-out quality and breakage by arm" width="100%"/></p>

| Held-out seeds 0–15, 1000 steps (ratio to reference, lower is better) | broken commits | severe | ratio@50 | ratio@1000 | runs never ≤ 1.05 |
|---|---:|---:|---:|---:|---:|
| ungoverned | 16 | 17 | broken | broken | 10 |
| validity only | 4 | 21 | 1.177 | **1.046** | **0** |
| validity + athanor (fixed tolerance) | **0** | **0** | 1.177 | 1.177 | 16 (frozen) |
| v2.5 conservative, **carried over unchanged** | 4 | 5 | 1.177 | 1.100 | 9 |
| retuned on seeds 100–115 (τ 0.78, no time decay) | 2 | 2 | **1.096** | **1.046** | 3 |

**Honest answer: partial transfer.**
- **Safety in kind:** the carried-over setting cut severe regressions from 21 to 5 against validity only, and no run ended broken.
- **Not safety in degree:** it committed 4 breaks, as many as validity alone. All 4 were APPROVEd timeouts or crashes that occur only on instances larger than any probe.
- **Not speed:** its 50-step half-life closes the window for the one big "turn on 2-opt" edit after about 60 steps, so 9 of 16 runs never got good.
- **A small retune fixed most of it, and the safety held:** 36 settings, on separate seeds *and* separate instances, with the same 2.5 rules. Broken/severe went from 2/4 on the tuning seeds to 2/2 on held-out.
- **A derived condition predicted every freeze:** `APPROVE ⇔ tol ≥ r₍⌈τP⌉₎·τ/(κ(1−τ))`.
- **Fixed-tolerance Athanor froze on every seed.**

Details: [tsp_selfmod.md](docs/tsp_selfmod.md) · [TUNING_LOG.md](docs/TUNING_LOG.md#260-transfer-to-the-tsp-self-modifier) · [ALGORITHM_CARD.md](docs/ALGORITHM_CARD.md#transfer-to-a-second-system-v260-self-modifying-tsp-solver).

```bash
python experiments/tsp_selfmod/run.py --with-tuned
```

## Evals and versioned configs (2.7)

Every bug fixed in ATHANOR and every tuning failure is now a permanent, deterministic **[Bug2Eval](https://github.com/jacksonjp0311-gif/bug2eval) case** in [`evals/cases/`](evals/cases/). Each case proves its own contract: the captured *before* fails and the captured *after* passes. Every tuned config is an immutable, content-hashed, semver'd entry in [`configs/registry/`](configs/registry/). A config becomes the incumbent only through **eval-gated, Athanor-governed promotion**:

```text
capture (bug commit pair | failed config + seeds + limits) → evals/cases/<ID>  (before FAILS, after PASSES)
athanor registry promote REF:
   1. eval suite with REF injected   → a new config can't re-break a captured case
   2. Athanor verdict REF vs incumbent on fresh gate seeds 200–215 (ΔΦ of log-MSE signatures → C → H7)
   → APPROVE promote · REFINE hold · REJECT / suite failure reject   (hash-chained registry ledger)
```

The suite is seeded from real history: the 4 bugs fixed in 2.1.0 (snapshots of the real `src/` at `ad23756` and `31c1c4a`) and 4 tuning failures re-measured exactly. Those four are the overfit setting (severe **34 → 2** on held-out seeds), the `basis = current` feedback trap (**30 → 8**), the τ 0.80 threshold cliff (never reaches MSE < 1.5 → 489 steps), and no governor (broken/severe **23/140 → 0/3**). Injecting the pre-2.1 source makes all 4 bug cases fail with `REGRESSION`, and injecting the overfit config makes ATH-T001 `BLOCKED` (both tested).

The conservative τ 0.75 setting (`selfmod/adaptive@1.1.0`) was promoted through the gate: the suite passed 8/8, and Athanor gave **APPROVE with H7 = 0.8125** (13 of 16 fresh seeds coherent, mean ΔΦ 0.296) over `selfmod/validity-athanor@1.0.0`. On those fresh seeds it had 1 broken commit and 5 severe regressions, against 0 and 13 for the incumbent. It reached MSE < 1.5 in a median 32.5 steps against 398.

```bash
athanor evals run                                   # PASS / DRIFT / STALE / BLOCKED / REGRESSION / ERROR, hash-chained ledger
athanor registry list                               # configs, statuses, incumbents
athanor registry promote selfmod/adaptive@1.2.0     # suite + Athanor verdict; decision recorded
```

Full design, statuses and caveats: [docs/EVALS.md](docs/EVALS.md). The reusable procedure behind all of this, including how it was run as a human + AI collaboration: [docs/METHOD.md](docs/METHOD.md).

## CLI reference

| Command | What it does | Exit code |
|---|---|---|
| `athanor run --config CFG [--out-dir DIR] [--tag NAME]` | Runs the loop and writes a run folder (`run_<UTC timestamp>` or `NAME`). A tagged folder that already has a ledger is never overwritten. | `0` |
| `athanor verify RUN` | Checks `seq`, `prev_hash`, and `row_hash` for every ledger row and reports `first_bad_seq`. | `0` ok · `1` broken |
| `athanor replay RUN [--out-dir DIR]` | Re-runs from `RUN/config.json` and compares the digest with the original ledger head. | `0` match · `1` mismatch · `2` no config |
| `athanor diff RUN_A RUN_B` | Compares two runs: digests, first divergent ledger row, changed config keys, verdict counts, promotions, and stats deltas. | `0` identical · `1` different |
| `athanor bench [--config CFG] [--seeds 0-7] [--out DIR] [--chart PNG]` | Governed vs ungoverned comparison across seeds. Writes `results.json`, `results.md` and a chart. Without `--config` it uses a built-in copy of `configs/bench.yaml`. | `0` |
| `athanor selfmod [--seeds 0-15] [--steps 1000] [--out DIR] [--chart PNG] [--ledgers]` | Governed vs ungoverned **real self-modifying program** (see [`docs/selfmod.md`](docs/selfmod.md)). `--ledgers` keeps a hash-chained ledger and `final_self.py` per run. | `0` |
| `athanor selfmod-arms [--seeds 0-15] [--steps 1000] [--out DIR] [--chart PNG]` | Held-out comparison of 7 arms: ungoverned, validity, athanor, validity+athanor, and the tuned adaptive variants. | `0` |
| `athanor evals list` · `evals run [--kind bug\|tuning] [--case ID] [--candidate REF] [--strict] [--out DIR]` | Lists and replays the Bug2Eval regression cases and writes a hash-chained `ledger.jsonl` + `summary.json` (needs `athanor[evals]`). | `0` ok · `1` REGRESSION/BLOCKED/ERROR · `2` unavailable |
| `athanor evals capture bug --id ID --title T --before-ref A --after-ref B --verifier V.py` | Captures a fixed bug. The case is refused unless *before* fails and *after* passes. | `0` · `2` refused |
| `athanor evals capture tuning --id ID --title T --bad REF --good REF --seeds S --limit M<=X` | Captures a tuning failure: the bad config must violate a limit and the good one must satisfy every limit. | `0` · `2` refused |
| `athanor registry list · show REF · lineage REF · verify` | The versioned config registry. `verify` recomputes every content hash and the ledger chain. | `0` · `1` corrupt |
| `athanor registry register REF [--parent P] [--set cfg.k=v] --reason R` | Adds an immutable config. Semver is enforced: an arm change is major, a cfg change is minor. | `0` · `2` |
| `athanor registry promote REF [--gate-seeds 200-215] [--allow-refine] [--bootstrap] [--dry-run]` | Eval suite with REF injected, then an Athanor verdict vs the incumbent. The decision is recorded. | `0` promoted · `1` not |
| `athanor --version` | Prints the version. | `0` |

`athanor --config CFG` (the 2.0 form) still works and is the same as `athanor run`. You can also use `python -m athanor ...`.

## Configuration reference

Configs are YAML files. `inherits: base.yaml` **deep-merges** nested sections, and inheritance cycles are rejected. Every field is validated at load time.

| Key | Default | Meaning |
|---|---|---|
| `seed` | `1337` | Root seed. Every random stream is derived from it. |
| `threshold_h7` (τ) | `0.70` | APPROVE needs `H7 ≥ τ`. Also the per-step coherence threshold. |
| `refine_floor` | `0.50` | REFINE band is `[refine_floor, τ)`. Must be `≤ τ`. |
| `refine_attempts` | `2` | Max REFINE retries. Each retry scales σ by `0.75ᵏ`. |
| `alpha` | `0.70` | Fitness `F = α·q + (1−α)·H7`, where `q = 1/(1+‖δ‖)`. |
| `dphi_mode` | `l2` | `l2` (step distance) or `cosine` (step angle). |
| `steps_per_candidate` | `24` | Telemetry trajectory length. |
| `population` / `generations` | `16` / `24` | Loop size. |
| `genome_dim` | `64` | Genome dimension. |
| `telemetry_noise` | `0.02` | Process noise in the telemetry dynamics. |
| `proposer_sigma` / `proposer_step_cap` | `0.12` / `0.50` | Gaussian proposal scale and max step norm. |
| `governor.enabled` | `true` | `false` gives the ungoverned baseline: verdicts are recorded but never block promotion, and REFINE retries are off. |
| `gates.h20.enabled` | `false` | **H20 noise immunity.** Perturbs ΔΦ by `U(−σ, σ)` and requires `I20 ≥ min_immunity`. |
| `gates.h20.sigma` / `min_immunity` | `0.05` / `0.90` | H20 parameters. |
| `gates.h44.enabled` | `false` | **H44 boundary excess.** Requires `H7 − τ ≥ min_excess`, a margin over the gate. |
| `gates.h44.min_excess` | `0.0` | H44 margin. |
| `archive.bins` | `[16, 16]` | MAP-Elites grid over (H7, ‖δ‖). |
| `run.out_dir` / `run.tag` | `data/archives` / *unset* | Output location and an optional fixed folder name. |

With both gates disabled (the default), verdicts depend only on the H7 gate.

## Guarantees

These are the properties ATHANOR is built and tested to provide. Each one has a precise scope:

- **Determinism.** For a fixed resolved config, the ledger, decision record, archive, and run digest are identical across runs on the same software stack. Proposal, telemetry, and H20 perturbation streams are each derived from `SeedSequence(seed, …, gen, idx, attempt)`, so a candidate's result does not depend on how many REFINE retries other candidates used. Float results can differ across NumPy builds or platforms; `replay` and `diff` will report that.
- **Tamper evidence.** Each row stores `prev_hash` and `row_hash = SHA-256(canonical JSON without row_hash)`. Editing, deleting, inserting, or reordering rows makes `verify` fail at the first bad row. The chain makes tampering *detectable*. It does not stop someone from rewriting the whole file and re-hashing it. To guard against that, store the run digest from `metadata.yaml` somewhere else.
- **Replay.** `athanor replay` re-runs from the saved `config.json` and passes only if the original ledger verifies **and** the new digest matches it.
- **Monotone gating.** Optional gates can only make a verdict stricter (APPROVE → REFINE).

## Run artifacts

| File | Contents |
|---|---|
| `ledger.jsonl` | One hash-chained row per candidate: verdict, reason, H7 metrics, `checks[]`, `refine_trail[]`, `parent_id`. |
| `decision_record.json` | Gate settings, verdict counts, and per-generation lineage (`parent_before` → `parent_after`, `promoted`, reason). |
| `config.json` | Fully resolved config, used for replay. |
| `metadata.yaml` | Timestamp, seed, config hash, `run_digest`, `ledger_rows`, optional `ATHANOR_GIT_HASH`. |
| `archive.json` / `archive.pkl` | MAP-Elites archive (portable JSON, plus the legacy pickle). |
| `archive_stats.json` | Archive fill, mean H7/F, and verdict counts. |
| `h7_trace.png`, `fitness_trace.png`, `dashboard.html` | Plots and a static dashboard. |

## Architecture

```text
src/athanor/
├── core/          ΔΦ, C, H7 math (coherence.py), validity pre-gate (validity.py), telemetry, types
├── agents/        Telemetry · Proposer · Verifier (H7/H20/H44 gates) · Selector · Archivist
├── adapters/      Pluggable proposal strategies (ProposerAdapter, GaussianNoiseAdapter)
├── evolution/     dgm_loop.run(): the governed loop; MAP-Elites archive
├── ledger/        Hash-chained LedgerWriter and verify_ledger
├── experiments/   Config loading, deep-merge inheritance, validation
├── bench.py       Governed-vs-ungoverned comparison (athanor bench)
├── selfmod/       Real self-modifying program, arms, adaptive schedule (athanor selfmod, selfmod-arms)
├── evals/         Bug2Eval integration: capture, suite runner, eval-gated promotion (athanor evals)
├── config_registry.py  Versioned, content-hashed config registry (athanor registry)
├── scripts/       CLI: run · verify · replay · diff · bench · selfmod · evals · registry
└── utils/         Seeding, JSONL logging, plots and dashboard
configs/           base.yaml, toy_experiment.yaml, bench.yaml
docs/benchmark/    Committed benchmark results (results.md, results.json)
docs/selfmod/      Committed self-modification results; write-up in docs/selfmod.md
experiments/       Runnable experiment entry points (self_modify/: run, tune, analyze_tuning)
docs/ALGORITHM_CARD.md, docs/TUNING_LOG.md, docs/tuning/   Algorithm card, tuning log and raw tuning data
docs/EVALS.md, docs/METHOD.md   Eval suite + registry design; the reusable tuning/governance method
evals/cases/       Bug2Eval regression cases (bugs + tuning failures); evals/verifiers/ their verifier sources
configs/registry/  Versioned config registry entries + hash-chained registry ledger
docs/              Architecture notes, LaTeX manuscripts, assets
tests/             Unit and integration tests (pytest)
```

You can use it as a library too:

```python
from athanor.experiments.registry import load_config
from athanor.evolution.dgm_loop import run
from athanor.ledger import verify_ledger

out = run(load_config("configs/toy_experiment.yaml"))
assert verify_ledger(f"{out['run_path']}/ledger.jsonl").ok
print(out["run_digest"])
```

## Testing

```bash
pip install -e ".[dev]"
pytest -q
```

The suite covers the coherence math, config validation and inheritance, the ledger (edit, delete, and reorder detection), determinism and REFINE-stream independence, the H20 and H44 gates, the decision record, the archive JSON round-trip, `diff`, and the CLI end to end (run → verify → replay → tamper). CI runs it on Python 3.10, 3.11, and 3.12, and also runs a run → verify → replay smoke check, `athanor registry verify` and the full eval suite (`athanor evals run`). It also checks that core ATHANOR still works without the `[evals]` extra.

## Theory & Manuscripts

The gates are based on the manuscripts in [`docs/source/`](docs/source/):
H7 coherence geometry law (`h7_coherence_geometry_law_v2_1.tex`), the Codex–DGM H7 paper (`athanor-latex-paper.tex`), H20 Ω-basin noise immunity (`h20_omega_basin_noise_immunity_v1_5.tex`), H44 boundary algebra (`h44_boundary_algebra_layer_v1_0.tex`), and 777 triadic boundary excess (v1.0, v2.0). See also [`docs/source/architecture.md`](docs/source/architecture.md) and the agent charters in [`AGENTS.md`](AGENTS.md).

## Roadmap

- [x] Hash-chained verdict ledger, `verify`, `replay` (2.1)
- [x] Decision record, deterministic REFINE path, optional H20/H44 gates, JSON archive, `diff` (2.2)
- [x] Governed-vs-ungoverned benchmark (`athanor bench`), wheel/sdist attached to GitHub releases (2.3)
- [x] Real self-modifying program test (`athanor selfmod`) (2.4)
- [x] Validity pre-gate, 4-arm comparison, adaptive schedule tuned on separate seeds (2.5)
- [x] Transfer test on a second, larger self-modifier (TSP solver); admission/lockout condition derived (2.6)
- [x] Bug2Eval regression suite, versioned config registry, eval-gated Athanor-governed promotion, METHOD.md (2.7)
- [ ] Probe sets that cover deployment input sizes (every governed TSP break was outside the probe range)
- [ ] Robust (worst-case over seed subsets) tuning objective, since the tuned optimum overfit its safety
- [ ] Pluggable telemetry backends for real model or agent traces (beyond the built-in linear dynamics)
- [ ] Signed run digests (for example Sigstore or GPG) to make whole-file rewrites detectable
- [ ] Remove `archive.pkl` once `archive.json` has been out for one release
- [ ] Property-based tests for gate monotonicity and ledger invariants

## Releases

Publishing a GitHub release runs [`.github/workflows/release.yml`](.github/workflows/release.yml). It builds the sdist and wheel, checks that the tag matches the `pyproject.toml` version, and attaches both files to the release. CI also builds the package, runs `twine check`, and smoke-tests the wheel in a clean venv on every push.

## Scope & intended use

ATHANOR is a research framework. The built-in telemetry is a synthetic linear dynamical system used to exercise the governor. It does not model any particular AI system. The self-modification test is a small symbolic-regression program, not an LLM or a general agent. The project makes no claims about benchmarks or real-world safety performance.

## License

[MIT](LICENSE) © 2025 James Paul Jackson
