# Evals: every bug and tuning failure becomes a permanent regression case

> Added in 2.7.0. Requires the optional extra: `pip install "athanor[evals] @ git+https://github.com/jacksonjp0311-gif/Athanor.git"`
> (it installs [Bug2Eval](https://github.com/jacksonjp0311-gif/bug2eval) v0.1.3 from GitHub). Core Athanor works without it.

Athanor gates self-modification. This layer turns the same discipline on Athanor itself:

```text
 fixed bug (commit pair + verifier)          failed tuning config (registry ref + seeds + limits)
              │                                              │
              └──────────────► athanor evals capture ◄───────┘
                                        │   bug2eval proves: before FAILS, after PASSES
                                        ▼   (a case that does not discriminate is not saved)
                         evals/cases/<ID>/   metadata.json · artifacts/*.tar.gz (SHA-256) ·
                                             prompt.md · athanor.json (provenance, recorded metrics)
                                        │
                     athanor evals run  ▼  replay every case → hash-chained ledger.jsonl + summary.json
                                        │
 tune.py --register-best ─► configs/registry/<family>/<name>/<semver>.json   (immutable, content-hashed)
                                        │
                  athanor registry promote REF
                    1. eval suite with REF injected   — no captured bug is back, no captured limit broken
                    2. Athanor verdict REF vs incumbent on fresh gate seeds (ΔΦ → C → H7 → verdict)
                                        │
                      APPROVE → promote · REFINE → hold · REJECT / suite failure → reject
                      (every decision appended to configs/registry/ledger.jsonl)
```

## What an eval case is

Each case is a standard **Bug2Eval case directory** (format v1.0): a broken workspace, a fixed reference
workspace, a prompt, and a verifier command. Bug2Eval checks artifact checksums and that protected verifier
files are identical in both snapshots and unchanged by a run. Athanor adds a sidecar `athanor.json` with:

- `kind`: `bug` or `tuning`, and `inject`: what the code or config under test replaces (`source` or `config`);
- `provenance`: commits and changed files for bugs; registry refs and spec hashes and the tuning-log evidence for tuning cases;
- `recorded`: exit codes and, for tuning cases, the measured metrics and their fingerprint at capture;
- `case_sha`: hash of the bug2eval contract, so an edited case is reported as an `ERROR`.

| Kind | Workspace | Verifier (protected) | "Current" check injects |
|---|---|---|---|
| `bug` | `src/` at the buggy and at the fixed commit | `evals/verifiers/ATH-B00x_*.py`, imports Athanor **from the workspace** | the working tree's `src/athanor` |
| `tuning` | `config.json` = bad / good registry spec | `verify_config.py` + `case.json` (seeds, steps, limits), run the **installed** Athanor | the `--candidate` config |

## Running the suite

```bash
athanor evals list
athanor evals run                         # all cases; exit 1 on REGRESSION / BLOCKED / ERROR
athanor evals run --kind bug --out data/evals/pr
athanor evals run --candidate selfmod/adaptive@1.1.0    # also score a config against every tuning case
athanor evals run --src /path/to/other/src               # test another checkout's code against the bug cases
athanor verify data/evals/pr                              # the result ledger is a normal Athanor ledger
```

Each case gets three checks, all through Bug2Eval's own machinery:

1. **Reference.** Bug2Eval validation: the captured *before* still fails and the captured *after* still passes. For tuning cases the verifier runs the installed Athanor, so a code change that makes a known-good config break its limits shows up here.
2. **Current.** The code or config under test goes into the *before* workspace and the protected verifier runs again, with tamper detection.
3. **Fingerprint.** For tuning cases, the metrics are hashed and compared with the capture.

| Status | Meaning | Fails the suite |
|---|---|---|
| `PASS` | Every check holds | no |
| `DRIFT` | Passes, but the tuning metrics differ from the capture (for example a different numpy version) | only with `--strict` |
| `STALE` | The captured *before* no longer fails, so the case no longer discriminates | only with `--strict` |
| `BLOCKED` | The `--candidate` config violates a captured limit | yes |
| `REGRESSION` | A fix no longer holds: the reference *after* fails, or the code under test brings the bug back | yes |
| `ERROR` | The case was edited, verifier files were tampered with, or the infrastructure failed | yes |

Ledger rows contain only deterministic fields (no timings), so the **suite digest** (the ledger head) is the same for the same code, cases, candidate and software stack. Two runs on this box gave the same digest.

## Seeded cases (real history only)

| ID | Kind | What it pins | Before → after (measured at capture) |
|---|---|---|---|
| ATH-B001 | bug | `log_jsonl` wrote a literal `\n` (fixed in 2.1.0, `31c1c4a`) | exit 1 → 0 |
| ATH-B002 | bug | `inherits:` used `dict.update` and dropped nested keys | exit 1 → 0 |
| ATH-B003 | bug | REFINE retry *k* of candidate *i* reused candidate *i+k*'s telemetry seed | 5 of 35 evaluations reused a seed → 0 of 36 |
| ATH-B004 | bug | Two runs in the same second shared one folder and ledger | shared `run_…` (6 rows from 2 runs) → `run_…_01` |
| ATH-T001 | tuning | Overfit: `selfmod/adaptive@1.0.0` (selected) vs `@1.1.0` (τ 0.75), held-out seeds 0–15 | severe **34** → **2** (limit ≤ 10) |
| ATH-T002 | tuning | Feedback trap: `adaptive-basis-current@1.0.0` vs `adaptive@1.0.0`, tuning seeds 100–115 | severe **30** → **8** (limit ≤ 10) |
| ATH-T003 | tuning | Threshold cliff: `validity-athanor@1.1.0` (τ 0.80) vs `@1.0.0`, seeds 100–115 | median steps to MSE < 1.5: never → 489 (limit ≤ 1000) |
| ATH-T004 | tuning | No governor: `ungoverned@1.0.0` vs `validity-athanor@1.0.0`, seeds 0–15 | broken 23 / severe 140 → 0 / 3 |

The bug cases snapshot the **real** `src/` tree at `ad23756` (before 2.1.0) and `31c1c4a` (2.1.0). The tuning cases re-measure the numbers in [TUNING_LOG.md](TUNING_LOG.md) and [selfmod/arms_results.md](selfmod/arms_results.md), and capture reproduced every one of them exactly. All limits are the pre-registered feasibility rule from the tuning protocol (broken ≤ 2, severe ≤ 10), plus a speed target for T003. `python evals/seed_history.py` rebuilds the registry and the cases from scratch.

Tests check that the suite passes on the current code, and that it reports **4/4 REGRESSION** when the pre-2.1.0 `src/` is injected (`tests/unit/test_evals.py`). They also check that the overfit config is **BLOCKED** by ATH-T001 and that an edited case is an **ERROR**.

## Capturing new cases

```bash
# A bug: write a verifier that exits non-zero on the bug and 0 when it is fixed (see evals/verifiers/).
athanor evals capture bug --id ATH-B005 --title "..." --before-ref <buggy> --after-ref <fix> \
    --verifier evals/verifiers/ATH-B005_thing.py

# A tuning failure: register both configs, then name the seeds and the violated limits.
athanor registry register selfmod/adaptive@1.2.0 --parent selfmod/adaptive@1.1.0 \
    --set cfg.adaptive_halflife=35 --reason "round 9: shorter half-life"
athanor evals capture tuning --id ATH-T005 --title "..." --bad selfmod/adaptive@1.2.0 \
    --good selfmod/adaptive@1.1.0 --seeds 0-15 --limit severe_regressions<=10 --limit broken_commits<=2
```

Capture runs Bug2Eval validation before saving and **refuses a case that does not discriminate**: the bad side must
actually fail (for tuning, it must *violate a limit*, exit 1, and not merely crash) and the good side must pass.

## The versioned config registry

`configs/registry/<family>/<name>/<semver>.json` holds `spec = {arm, cfg}`, `spec_hash = SHA-256(canonical spec)`,
`parent`, `reason`, `evidence`. Entries are immutable. Status comes from the hash-chained
`configs/registry/ledger.jsonl` (`register`, `promote`, `refine`, `reject`, `retire`); nothing is edited in place.

- **Semver is enforced** against a same-name parent: a change to the arm needs a **major** bump, a change to `cfg` needs a **minor** bump, and an identical spec is a **patch**.
- `athanor registry verify` recomputes every hash and checks the ledger chain. CI runs it on every push.
- `experiments/self_modify/tune.py --register-best REF --parent P` hands a round's best feasible setting to the registry as a candidate. **Tuning never promotes on its own.**

| Ref | Status | From |
|---|---|---|
| `selfmod/ungoverned@1.0.0` | rejected (historical) | 2.4.0 baseline |
| `selfmod/validity-athanor@1.0.0` | promoted (bootstrap) → retired | 2.5.0 governed arm, τ 0.70 |
| `selfmod/validity-athanor@1.1.0` | rejected (historical) | round 1, τ 0.80 |
| `selfmod/adaptive@1.0.0` | rejected (historical) | rounds 6–7 selected setting |
| `selfmod/adaptive-basis-current@1.0.0` | rejected (historical) | round 8 sensitivity |
| `selfmod/adaptive@1.1.0` | **promoted** through the gate (see below) | conservative τ 0.75 |

## Eval-gated, Athanor-governed promotion

`athanor registry promote REF` (code: `athanor/evals/promotion.py`):

1. **Eval floor.** Run the whole suite with REF injected. Any `REGRESSION`, `BLOCKED` or `ERROR` means **reject**. A new config cannot re-break a captured case.
2. **Step-size rule (dogfooding).** Run REF and the incumbent on **gate seeds 200–215**. Tuning uses 100–115 and the held-out report uses 0–15, so these seeds are fresh. Per seed, the behaviour signature is `σ = log10 MSE` of the current self at steps {10, 30, 100, 300, 1000}, clipped to [−3, 6], with a broken self counted as 6. The drift is `ΔΦ_s = ‖σ_s(REF) − σ_s(incumbent)‖₂ / √5`. The per-seed vectors are laid out as a trajectory, and Athanor's unchanged `estimate` and `VerifierAgent` give C = 1/(1+ΔΦ), H7, and APPROVE / REFINE / REJECT (τ 0.70, refine floor 0.50, so a seed counts as coherent when ΔΦ_s ≤ 0.4286).
3. APPROVE promotes (the old incumbent is retired). REFINE records `refine` (use `--allow-refine` to accept it). REJECT rejects. `--dry-run` evaluates without recording.

**Result of the real promotion recorded in the registry** (`selfmod/adaptive@1.1.0` over `selfmod/validity-athanor@1.0.0`):
see the `promote` event in `configs/registry/ledger.jsonl`, or run `athanor registry show selfmod/adaptive@1.1.0`. The gate run is summarised in the [CHANGELOG](../CHANGELOG.md) 2.7.0 entry.

## Caveats

- **The suite is a floor, not an objective.** Tuning cases ATH-T001 and ATH-T004 run on the held-out seeds 0–15. Once a gate checks those seeds over and over, they stop being truly held out for later configs, so confirm any new config once on fresh seeds before quoting held-out numbers. The promotion verdict already uses separate seeds (200–215).
- **The step-size rule measures how much behaviour changes, not whether it improves.** A config that gets better in a large jump is held back (REFINE or REJECT), on purpose, the same way Athanor treats self-edits.
- **Bug verifiers check behaviour, not a proof.** Each one encodes one observable symptom of the original bug.
- **Bug2Eval verifier protection is tamper detection, not a sandbox.** Only run cases you trust.
- Tuning metrics are deterministic on one software stack. A different numpy or Python version can change floats, and the suite reports that as `DRIFT`, not as a failure.
- The `[evals]` extra is a direct GitHub dependency, so it works with `pip install` from GitHub, but PyPI would not accept it as-is.
