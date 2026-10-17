# Changelog

## 3.0.0 — 2026-10-17

Operational release: usable from any program, checked by one command, benchmarked on fresh held-out seeds.

### Added
- **Public adapter API** (`athanor.governor`, exported from `athanor`).
  - `athanor.govern(initial, propose, evaluate, probe, *, scale, check=None, steps, seed, ledger=None, governed=True)` runs a governed self-modification loop for any program.
  - `athanor.Governor(probe, scale=…).judge(current, candidate)` gates a single edit.
  - The verdict is ATHANOR's unchanged ΔΦ → C → H7 → `VerifierAgent` pipeline on per-probe drift `|Δprobe| / scale`.
  - `athanor.GovernorError` gives clear messages for bad settings or probe output.
  - Example: `examples/govern_quickstart.py`.
- **`athanor doctor`**: checks Python, dependencies and extras, runs a governor self-test and a run + ledger verify + determinism check, and verifies the registry and eval cases when run inside a checkout. `--json` for machine output.
- **`athanor demo`**: one command for run → verify → replay from `config.json` (identical digest) → eval suite (bug cases; `--full-evals` for all).
- **Clear CLI errors**: one line plus a hint and exit code 2 instead of a traceback (`ATHANOR_DEBUG=1` restores it).
- **`athanor bench --all`** (`athanor.bench_all`): the unified benchmark.
  - Three systems: the synthetic loop, the curve-fitting self-modifier and the TSP self-modifier.
  - Arms: ungoverned, validity and governed, using the registry configs.
  - Seeds: the new held-out set 3000–3015.
  - Output: `docs/benchmark_v3/results.{md,json}` and `docs/assets/benchmark_v3.png`.
- **TSP family in the eval suite and registry**: the `tsp/*` registry entries and three cases that re-measure the 2.6 results exactly.
  - ATH-T005: partial transfer, broken 4 → 2.
  - ATH-T006: frozen fixed-tolerance gate, 16 frozen runs → 0.
  - ATH-T007: no governor, 16 broken → 2.
  - The verifier template and capture dispatch on the family. The suite now has 11 cases.
- **TSP promotion signature**: held-out tour ratio at checkpoints divided by κ = 0.10, with a broken program counted as 2.0.
- **Seed-set policy** (`athanor.seedsets`, documented in `docs/EVALS.md#seed-set-policy`).
  - Each promotion takes the next never-used gate block of 16 seeds from 10000 up.
  - Explicit gate seeds that overlap tuning, held-out, benchmark or already-gated seeds are refused unless `--allow-seed-reuse`, which is recorded in the ledger.
  - Dry runs use scratch seeds 90000–90015.
- **Size-scaled TSP validity inputs**: `probe_scaling = "checks" | "checks+probes"` adds instances at 50/75/100 % of the deployment size to the validity checks (and optionally to the ΔΦ probes). The default is off, so 2.6 reproduces exactly.
- **Worker memory cap** for TSP runs (2 GB address space per worker), so a self-edited program that allocates without bound fails as a crash instead of taking down the machine.
- Docs: README (operational quickstart, adapter API, unified benchmark), algorithm card (adapter API, seed policy, size-scaled inputs, new failure modes), EVALS (TSP cases, seed policy, TSP promotion), TUNING_LOG (3.0 probe-scaling selection), METHOD (two checklist steps, 2.8 and 3.0 rows).
- CI runs `athanor doctor`, `athanor demo`, the adapter example and a `bench --all` smoke run. The wheel job checks doctor, demo, the API and `bench --all` from the built wheel.
- Tests: adapter API (verdicts, validity, determinism, ungoverned baseline, ledger, errors, example), seed policy, size-scaled inputs, TSP promotion signature, bench arms match the registry, doctor/demo/CLI errors. 103 tests in total.

### Results
- **Unified benchmark, held-out seeds 3000–3015** (unsafe commits / severe regressions / final quality):
  - curve fit: ungoverned 31 / 116 / MSE 0.433; validity 8 / 84 / 0.874; validity + Athanor 0 / 4 / 1.044; Athanor adaptive (incumbent) **0** / 10 / 0.930.
  - TSP: ungoverned 16 / 16 / broken; validity 4 / 15 / ratio 1.045; validity + scaled checks 0 / 11 / 1.044; fixed-tolerance Athanor 0 / 0 / frozen; Athanor adaptive 2.6: 2 / 2 / 1.068; **Athanor adaptive + scaled checks (incumbent) 0 / 0 / 1.049**.
  - synthetic loop: promotions of non-APPROVED parents 163 → **0**; tail H7 0.781 → 0.914 (governed higher on 10 of 16 seeds, lower on 4).
- **Size-scaled checks** on the fresh seeds: validity only went from 4 broken to 0 and the adaptive arm from 2/2 to 0/0, with no loss of speed. On spent seeds 0–15 the adaptive arm went from 2/2 to 1/1.
- **TSP promotion through the gate**: `tsp/adaptive@1.2.0` over `@1.1.0` on gate block 10000–10015 gave suite 11/11 PASS and APPROVE, H7 1.000. Broken commits 0 vs 2, severe 5 vs 7, identical median ratio.

### Caveats
- Governed arms are slower and reach worse best-case quality. On the curve fit, ungoverned had the best final MSE (0.433 vs 0.930) and reached MSE < 1.5 in 5.5 vs 27.5 steps. On TSP every governed arm was still at the seed program at step 50, and 7 of 16 runs never reached ratio ≤ 1.05.
- The curve-fit incumbent had 10 severe regressions on the fresh seeds, exactly at the limit of 10.
- Size scaling uses the deployment size (largest evaluation instance). In the adapter API, choosing probe inputs that cover deployment is still the user's job.
- The memory cap is per worker process and POSIX-only. Serial runs (`workers=1`) are not capped.
- `bench-v3` seeds are now spent by the published table. Future benchmarks need a new set.

### Unchanged
- Defaults reproduce 2.6 exactly (`probe_scaling` off; existing tests still pass). The CLI is backwards compatible: `athanor bench` without `--all` is unchanged, and `promote --gate-seeds` still works but refuses spent seeds.

## 2.8.0 — 2026-10-17

### Added
- **AgentSearch evidence layer** (`athanor.search`, optional extra `athanor[search]`, Python 3.11+). The extra pins [AgentSearch](https://github.com/jacksonjp0311-gif/AgentSearch) `agentsearch-local` 1.0.0rc5. All file access goes through its five read-only tools; the index is derived state in `.athanor/search/` (git-ignored). Design: `docs/SEARCH.md`.
  - **Citations at capture time.** `athanor evals capture … --cite PATH[:text]` (on by default when the extra is installed, `--no-evidence` to skip) and `athanor evals evidence` write `evals/cases/<ID>/evidence.json`: path, file SHA-256, cited line range, cited-lines SHA-256, excerpt.
  - **`athanor search index|status|find|grep|read|verify|cite`** over run ledgers and decision records (`--scope runs`), configs, the registry, eval cases, the tuning logs, docs and source.
  - **Stale-evidence checks.** Statuses: `fresh`, `changed-lines-intact`, `moved`, `stale`, `missing`; only `stale` and `missing` are hard.
    - Every `athanor evals run` re-verifies case citations (row `evidence: {checked, stale, hard}`, summary `evidence_checked`, `stale_evidence`). Case statuses are unchanged by it.
    - `athanor registry promote --require-fresh-evidence` records `refine` instead of promoting on hard staleness. Every promotion event records `evidence_checked` and `stale_evidence`.
    - `experiments/self_modify/tune.py` re-verifies the tuning cases' citations and the `--parent` entry's evidence before a round. `--require-fresh-evidence` stops on hard staleness.
    - `athanor evals evidence --check` exits 1 only on hard staleness.
- **Registry evidence pinning.** Evidence items that name a repo file get its SHA-256 at registration. Items with `rows: [start, end]` (as written by `tune.py --register-best`) get a SHA-256 of exactly those rows of the JSON log. Later rounds can append to `docs/tuning/log.json` without making them stale, and this check needs no AgentSearch.
- **Seeded citations** (`evals/seed_evidence.py`): 29 citations across the 8 cases. They cover the fixed source lines and 2.1.0 CHANGELOG lines (bugs), and the TUNING_LOG lines, `docs/tuning/log.json`, `docs/selfmod/arms_results.*` and registry entries (tuning failures).
- CI builds the index and runs `athanor evals evidence --check` on 3.11 and 3.12. It checks that `athanor search` degrades with an install hint on 3.10 and in a clean core install.
- Tests: the five tools and scopes, all five citation statuses, the evidence file round-trip, registry hash pinning, citations attached to a real case and flagged stale in the suite check and the promotion evidence check, and pinned log rows surviving appends but not edits. The search tests skip cleanly on Python < 3.11 or without the extra. 86 tests.
- Docs: `docs/SEARCH.md`; evidence sections in the README, `docs/EVALS.md`, `docs/ALGORITHM_CARD.md` and `docs/METHOD.md` (a new checklist step: cite past results and re-verify them before relying on them).

### Caveats
- A citation proves the cited bytes are unchanged, not that they are correct.
- `changed-lines-intact` and `moved` are soft by design: the surrounding text may have changed meaning.
- Registry entries registered before 2.8.0 carry no hashes, so they have nothing to verify.
- The extra is a direct Git dependency on an AgentSearch release candidate; it installs from GitHub, not PyPI.

### Unchanged
- Core behaviour, results, eval cases and registry decisions. Core ATHANOR and the `[evals]` suite work without the extra.

## 2.7.0 — 2026-10-17

### Added
- **Bug2Eval regression suite** (`athanor.evals`, optional extra `athanor[evals]`, which pins [Bug2Eval](https://github.com/jacksonjp0311-gif/bug2eval) v0.1.3). Every fixed bug and every failed config is a versioned, deterministic case in `evals/cases/`. A case is refused unless its captured *before* fails and its *after* passes, and its verifier is protected (identical in both snapshots, SHA-256 checked).
  - `athanor evals list`, `evals run [--kind] [--case] [--candidate REF] [--strict] [--out]`, `evals capture bug …`, `evals capture tuning …`.
  - Statuses: PASS, DRIFT, STALE, BLOCKED, REGRESSION, ERROR. Results go to a hash-chained `ledger.jsonl` and `summary.json` with a deterministic suite digest.
  - Bug cases inject the working-tree `src/` into the captured *before* workspace, so a reintroduced bug shows up as `REGRESSION`. Tuning cases inject a registry config, so a config that falls into a captured failure shows up as `BLOCKED`.
- **Seeded from real history** (`evals/seed_history.py`):
  - ATH-B001…B004: the four bugs fixed in 2.1.0 (log JSONL newline, nested config inheritance, seed overlap under REFINE, run-folder collision), captured from the real `src/` at `ad23756` → `31c1c4a`.
  - ATH-T001: overfit tuned setting vs conservative τ 0.75 (severe 34 → 2, seeds 0–15).
  - ATH-T002: `adaptive_basis = current` feedback trap (severe 30 → 8, seeds 100–115).
  - ATH-T003: τ 0.80 threshold cliff (never reaches MSE < 1.5 → median 489 steps, seeds 100–115).
  - ATH-T004: no governor (broken/severe 23/140 → 0/3, seeds 0–15).
- **Versioned config registry** (`athanor.config_registry`, `configs/registry/`, `athanor registry list|show|lineage|register|promote|verify`). Entries are immutable and content-hashed, semver is enforced against the parent (arm change = major, cfg change = minor), lineage is tracked, and status comes only from a hash-chained registry ledger. `experiments/self_modify/tune.py --register-best REF --parent P` hands a tuning result to the registry as a candidate.
- **Eval-gated, Athanor-governed promotion** (`athanor registry promote`). The full suite runs with the candidate injected; any REGRESSION, BLOCKED or ERROR rejects. Then Athanor's own ΔΦ → C → H7 → verdict pipeline compares candidate and incumbent per-seed log-MSE signatures on fresh gate seeds 200–215. APPROVE promotes, REFINE holds, REJECT rejects, and every decision is recorded.
- **`docs/EVALS.md`** (design, statuses, cases, registry, promotion, caveats) and **`docs/METHOD.md`** (a system-agnostic tuning and governance method with a checklist, using only measured numbers, plus an account of how it was run as a human + AI collaboration from 2.1 to 2.7). Both are linked from the README and the algorithm card. The algorithm card and tuning log gain promotion and registry sections.
- CI runs `athanor registry verify` and the full eval suite, and checks that core ATHANOR still works without the `[evals]` extra.
- Tests for the registry (immutability, semver, lineage, tamper detection) and the evals (old source → 4/4 REGRESSION, overfit config → BLOCKED, tampered case → ERROR, capture round-trip and refusal, identical-config APPROVE). 80 tests in total.

### Results
- `selfmod/adaptive@1.1.0` (conservative τ 0.75) promoted over `selfmod/validity-athanor@1.0.0`: suite 8/8 PASS, **APPROVE, H7 = 0.8125** (13 of 16 gate seeds coherent), mean ΔΦ 0.296, max 0.654.
- On gate seeds 200–215 the candidate had 1 broken commit and 5 severe regressions against 0 and 13 for the incumbent, MSE@100 1.199 vs 2.161, final MSE 0.844 vs 0.880, and a median 32.5 vs 398 steps to reach MSE < 1.5.

### Caveats
- The promoted config had one broken commit on the gate seeds where the incumbent had none. The gate is a drift limit, not a proof of safety.
- Seeds 0–15 are used by ATH-T001 and ATH-T004, so for configs checked by the suite they are no longer strictly held-out. Confirm new configs once on fresh seeds.
- Tuning-case fingerprints are exact floats; a different numpy build could show `DRIFT` (a warning, failing only with `--strict`).
- The `[evals]` extra is a direct Git dependency, so it works with `pip install` from GitHub but would not be accepted by PyPI.
- No TSP (2.6) tuning cases yet; the suite covers the self-modifying program family only.

### Unchanged
- Core behaviour and results: 2.5 and 2.6 results reproduce exactly. Bug2Eval is optional and core ATHANOR runs without it.

## 2.6.0 — 2026-10-16

### Added
- **Second self-modification testbed: a self-modifying TSP solver** (`athanor.selfmod.tsp_program`, `athanor.selfmod.tsp_experiment`, `experiments/tsp_selfmod/`).
  - The agent's self is a six-function solver module. It rewrites its own source with AST mutations; a local LLM proposer was not feasible on CPU here.
  - Real failure modes: crashes, deterministic loop timeouts (harness-owned tick counter), silent wrong answers that look better to the agent's lenient self-scoring, and held-out regressions.
  - A unit-test-style check suite runs through the unchanged `validity_check`.
  - Separate probe, training, held-out and tuning instance sets.
- **Arms**: ungoverned, validity, athanor, validity+athanor, the v2.5 tuned and conservative settings carried over unchanged, and a setting retuned on seeds 100–115 (τ 0.78, no time decay; `experiments/tsp_selfmod/tuned.json`).
  - Results: `docs/tsp_selfmod/results.*` and `docs/assets/tsp_selfmod.png`.
  - Tuning log: `docs/tsp_selfmod/tuning_log.json` (36 settings, 4 rounds).
  - Counterfactual gate verdicts on the ungoverned breaks: `docs/tsp_selfmod/shadow_gate.json`.
- **Docs**: `docs/tsp_selfmod.md`, a transfer section in `docs/ALGORITHM_CARD.md`, and a 2.6 section in `docs/TUNING_LOG.md` with the admission condition `tol ≥ r₍⌈τP⌉₎·τ/(κ(1−τ))` and the half-life lockout window.
- Tests for the TSP sandbox, failure modes, check suite, ΔΦ trajectory, determinism, unchanged carried-over arms, and exact reproduction of the committed results.

### Changed
- `scheduled_tolerance()` is factored out of `run_selfmod` so both testbeds share the exact schedule. The 2.5 results still reproduce bit-for-bit.

### Results (held-out seeds 0–15, 1000 steps)
- **v2.5 conservative, carried over:** 4 broken commits (= validity only), 5 severe (vs 21 for validity only), final ratio 1.100 (vs 1.046). 9 of 16 runs never reached ≤ 1.05. This is a partial transfer.
- **Retuned:** 2 broken, 2 severe, final ratio 1.046, 3 runs never good. Tuning → held-out went 2/4 → 2/2 broken/severe.
- **Fixed-tolerance Athanor:** frozen on all 16 seeds.
- **Ungoverned:** broke on all 16 seeds (15 silent wrong answers). The gate would have rejected those 15 and approved the 1 timeout.

## 2.5.0 — 2026-10-17

### Added
- **Validity pre-gate** `athanor.core.validity.validity_check`: a hard reject on any exception or non-finite output over a validation input set. It runs before the coherence gate.
- **Self-mod arms**: `ungoverned`, `validity`, `athanor`, `validity+athanor`, plus adaptive variants (`athanor.selfmod.arms`, `athanor selfmod-arms`). Held-out results are in `docs/selfmod/arms_results.*` and `docs/assets/selfmod_arms.png`.
- **Adaptive drift tolerance** (off by default): `gamma`, `adaptive_power`, `adaptive_basis` (`current`/`best`), `adaptive_cap`, `adaptive_floor`, `adaptive_halflife`, `validity_grid`. Tuned values are `TUNED_ADAPTIVE` and `TUNED_ADAPTIVE_CONSERVATIVE`.
- **Tuning on separate seeds** (100–115) with a pre-declared feasibility and objective rule: `experiments/self_modify/tune.py`, `analyze_tuning.py`. 195 settings over 8 rounds are logged in `docs/tuning/`, with a Pareto chart `docs/assets/tuning_pareto.png`.
- **`docs/ALGORITHM_CARD.md`** (definitions, verdict rules, gates, pseudocode, defaults/tuned values, complexity, guarantees, failure modes, evaluation) and **`docs/TUNING_LOG.md`** (rounds, plateau, sensitivity, fitted trade-off, held-out generalisation).
- Tests for the validity check, the tolerance schedule, arm equivalence with 2.4.0, the validity invariant, and exact reproduction of the committed 2.4.0 results.

### Results (held-out seeds 0–15)
- The validity-only arm still committed 10 breaking edits and 118 severe regressions.
- The tuned adaptive validity+athanor arm had the best MSE@1000 (0.697 vs 0.862 ungoverned), but its severe regressions went from 8 (tuning seeds) to 34 (held-out): overfit.
- The conservative τ 0.75 setting (fixed before held-out evaluation): 0 broken, 2 severe, MSE@100 1.247 vs 1.173 and MSE@1000 0.903 vs 0.862 ungoverned. It is still about 4× slower to reach MSE < 1.5.

### Unchanged
- Default behaviour: with default config, 2.5.0 reproduces the 2.4.0 self-mod results exactly.

## 2.4.0 — 2026-10-17

### Added
- **Real self-modifying program test** (`athanor.selfmod`, `athanor selfmod`, `experiments/self_modify/`). An offline, deterministic agent rewrites its own `f(x)` source via `ast` mutation, recompiles it, and keeps edits that lower minibatch error. ΔΦ comes from real change (output divergence on 32 probes plus AST structural distance) and goes through ATHANOR's unchanged ΔΦ → C → H7 → `VerifierAgent` pipeline. Governed mode commits only APPROVE edits (REFINE retries a gentler edit); ungoverned commits every improving edit.
- Committed results for 16 seeds × 1000 steps (`docs/selfmod/`, `docs/assets/selfmod.png`) and a write-up (`docs/selfmod.md`). Breaking commits 0 vs 23 and severe regressions 3 vs 140, but improvement is much slower and median final held-out MSE is worse (1.110 vs 0.862). The gate would itself have approved 20 of the 23 breaking edits (H7 is a drift limit, not a crash detector); results include each commit's verdict for this analysis.
- Optional per-run hash-chained ledgers with the SHA-256 of every committed source, plus `final_self.py` (`--ledgers`).
- Tests for the mutator, grammar whitelist, breakage detection, ΔΦ trajectory, determinism and the governed-commit invariant.

## 2.3.0 — 2026-10-17

### Added
- **`athanor bench`** (`athanor.bench`): governed vs ungoverned comparison on the same task across seeds. Writes `results.json`, `results.md` and a 4-panel chart (ΔΦ, C, H7 per generation, plus verdict counts). Committed results for seeds 0–7 are in `docs/benchmark/` and `docs/assets/benchmark.png`, and the README shows the measured numbers, including the seeds where the governor makes no difference and the ones where it stays below τ.
- `configs/bench.yaml`, with a built-in copy so `athanor bench` works from an installed wheel.
- `governor.enabled` config switch (default `true`). `false` gives the ungoverned baseline: verdicts are recorded but don't block promotion, and REFINE retries are off.
- Decision record lineage now includes per-generation population means (`pop_dphi_mean`, `pop_C_mean`, `pop_h7_mean`) and the parent's metrics. `decision_record.json` also records `governed`.
- `release.yml`: on a published GitHub release, builds the sdist and wheel, checks the tag against the version, and attaches both. CI gains a `package` job (build, `twine check`, clean-venv wheel smoke test).

### Changed
- Packaging metadata for distribution: readme, SPDX license, classifiers, keywords, project URLs, pinned minimum dependency versions; `dev` extra adds `build` and `twine`.
- README: install from GitHub (`pip install git+https://github.com/jacksonjp0311-gif/Athanor.git`) or from the release wheel. Not published on PyPI (the `athanor` name there belongs to an unrelated project).

## 2.2.0 — 2026-10-16

### Added
- **Decision record** (`decision_record.json`): gate settings, verdict counts, promotions, and per-generation lineage (`parent_before` → `parent_after`, `promoted`, reason).
- Ledger rows now explain each verdict: `checks[]` (each gate's value, limit, pass/fail), `refine_trail[]` (each attempt with σ, verdict, H7), `parent_id`.
- **Optional gates** in `VerifierAgent`, enabled through config and off by default: `gates.h20` (noise immunity I20 under bounded ΔΦ perturbation) and `gates.h44` (boundary excess `H7 − τ ≥ min_excess`). They can only downgrade APPROVE → REFINE.
- **`archive.json`** (portable MAP-Elites archive, with `MapElitesArchive.to_dict/from_dict`) and **`athanor diff RUN_A RUN_B`**.
- Hero banner (`docs/assets/athanor-banner.svg`) and a rewritten README.

### Changed
- **Deterministic REFINE path**: proposal, telemetry, and gate randomness use independent per-(gen, idx, attempt) streams, so a candidate's result no longer depends on other candidates' REFINE retries. As a result, run digests differ from 2.1.0 for the same seed.

## 2.1.0

### Added
- **Hash-chained verdict ledger** (`athanor.ledger`): each row records `seq`, `prev_hash`, `row_hash`; `verify_ledger()` reports the first broken row.
- **Run digest**: the ledger chain head, written to `metadata.yaml` and returned from `run()`.
- **CLI subcommands**: `athanor run`, `athanor verify RUN`, `athanor replay RUN`, `--version`. `athanor --config X` still works.
- `config.json` (resolved config) saved in every run folder to enable replay.
- Config knobs previously hard-coded in the loop: `refine_floor`, `telemetry_noise`, `proposer_sigma`, `proposer_step_cap`; plus `run.tag` and `--out-dir`/`--tag` overrides.
- Tests for the ledger, determinism, config inheritance, and CLI tamper detection; CI matrix on Python 3.10–3.12 with a run→verify→replay smoke step.

### Fixed
- `utils.logging.log_jsonl` wrote a literal `\n` instead of a newline, producing one-line "JSONL".
- `inherits:` did a shallow `dict.update`, silently dropping nested keys (e.g. `archive.novelty_eps`); now a deep merge with cycle detection.
- Telemetry seeds `seed + g*10000 + i + attempt` collided (refine attempt 1 of candidate *i* reused candidate *i+1*'s seed); now derived via `SeedSequence`.
- Two runs started in the same second shared one folder and appended to the same ledger; untagged runs now get a unique folder, tagged runs refuse to overwrite an existing ledger.
- Validation now rejects `refine_floor > threshold_h7`.

### Changed
- Run outputs (ledger rows, metadata) will differ from 2.0.0 for the same seed because of the seeding fix.
- Integration tests write to a temp directory instead of `data/archives/`.
