# Changelog

## 2.1.0 — unreleased

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
