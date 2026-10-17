# Changelog

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
