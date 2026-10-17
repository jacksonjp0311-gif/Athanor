# Changelog

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
