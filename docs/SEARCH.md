# Search and evidence: every past result is cited, and checked before it is used

> Added in 2.8.0. Optional extra, Python 3.11+:
> `pip install "athanor[search] @ git+https://github.com/jacksonjp0311-gif/Athanor.git@v2.8.0"`
> It installs [AgentSearch](https://github.com/jacksonjp0311-gif/AgentSearch) (`agentsearch-local` 1.0.0rc5) from GitHub.
> Core Athanor and the `[evals]` suite work without it. On Python 3.10 the extra installs nothing and its tests are skipped.

The eval suite (see [EVALS.md](EVALS.md)) keeps past bugs and failures from coming back. But promotion and tuning also lean on past *results*: a number in the tuning log, a row in `docs/tuning/log.json`, a held-out table. If that file was edited after the result was used, the decision built on it is no longer backed by what is on disk. This layer adds three things:

1. **Citations at capture time.** A captured case records the source lines and run records it rests on, with the SHA-256 of the whole file and of the cited lines, in `evals/cases/<ID>/evidence.json`.
2. **`athanor search`** over run ledgers, decision records, configs, the registry, eval cases, the tuning logs, docs and source. It is a local, read-only SQLite-FTS5 index.
3. **Stale-evidence checks.** Every suite run, every promotion and every tuning round re-verifies those citations before relying on them.

```text
 capture (bug | tuning)                    tune.py --register-best
        │ read_file → cite lines                    │ pin the round's rows of docs/tuning/log.json
        ▼                                           ▼
 evals/cases/<ID>/evidence.json         configs/registry/…/<semver>.json  "evidence": [{rows, rows_sha256}]
 {path, sha256, start/end_line,                     │
  lines_sha256, excerpt, pattern}                   │
        │                                           │
        └──────────► verify_evidence + re-read ◄────┘   (athanor evals run · registry promote · tune.py)
                     fresh · changed-lines-intact · moved · stale · missing
                     stale/missing = hard → promotion held with --require-fresh-evidence, tuning stopped with it
```

## Statuses

| Status | Meaning | Hard? |
|---|---|---|
| `fresh` | The file's bytes are identical (`verify_evidence` matches the SHA-256) | no |
| `changed-lines-intact` | The file changed, but the cited lines are byte-identical where they were | no |
| `moved` | The cited lines are byte-identical at a different line range (found again by their pattern) | no |
| `stale` | The cited lines changed or are gone (or a whole-file citation changed) | **yes** |
| `missing` | The file is gone or unreadable | **yes** |

Anything other than `fresh` is reported. Only `stale` and `missing` are hard: `athanor evals evidence --check` exits 1 on them, `athanor registry promote --require-fresh-evidence` records `refine` instead of promoting, and `tune.py --require-fresh-evidence` stops before the round.

Pinned registry evidence for a tuning round is a **row slice** of `docs/tuning/log.json` (`rows: [start, end]`, `rows_sha256` = SHA-256 of those rows in canonical JSON). Later rounds append to the log without making it stale; editing or removing one of those rows makes it `stale` or `missing`. This check needs no AgentSearch, so it also runs on Python 3.10.

## What the seeded cases cite

`evals/seed_evidence.py` attached citations to the 8 seeded cases:

| Case | Cites |
|---|---|
| ATH-B001…B004 | the case's verifier source; the fixed line in `src/` (e.g. `def deep_merge`, `def derive_seed`, `def _make_run_path`, the JSONL newline); the matching 2.1.0 CHANGELOG line |
| ATH-T001 | both registry entries; the TUNING_LOG overfit line; the held-out severe-regressions row of `docs/selfmod/arms_results.md`; `arms_results.json` (whole file) |
| ATH-T002 | both registry entries; TUNING_LOG "Measured: severe 30 vs 8"; `docs/tuning/log.json` (whole file) |
| ATH-T003 | both registry entries; the TUNING_LOG τ 0.8 cliff line; `docs/tuning/log.json` (whole file) |
| ATH-T004 | both registry entries; the broken-commits row of `arms_results.md`; `arms_results.json` (whole file) |

Line citations carry two lines of context on each side. Whole-file citations are used only for raw run records, which should never change.

Bug-case defaults deliberately cite the **verifier**, not the whole fixed source file: source files change for unrelated reasons, and a whole-file citation would make every bug case look stale. The fixed lines are cited explicitly with `path:pattern`.

## Commands

```bash
athanor search index                                   # (re)scan the repo into .athanor/search/index.sqlite3 (git-ignored)
athanor search status                                  # index_status: roots, coverage, freshness
athanor search grep "severe 30 vs 8" --scope docs      # content_search; scopes: runs configs registry tuning evals docs src
athanor search find decision_record --scope runs       # file_search over run folders (typo-tolerant)
athanor search read docs/TUNING_LOG.md --start 80 --lines 20
athanor search cite docs/TUNING_LOG.md --pattern "Measured: severe 30 vs 8" --context 2
athanor search verify docs/tuning/log.json <sha256>    # verify_evidence

athanor evals evidence                                 # attach default citations to every case
athanor evals evidence --case ATH-T002 --cite "docs/TUNING_LOG.md:Measured: severe 30 vs 8"
athanor evals evidence --check                         # exit 1 only on stale/missing
athanor evals capture tuning … --cite PATH[:pattern]   # cite at capture time (--no-evidence to skip)
athanor registry promote REF --require-fresh-evidence
python experiments/self_modify/tune.py --round 9 … --register-best selfmod/adaptive@1.2.0 --parent selfmod/adaptive@1.1.0 --require-fresh-evidence
```

Each `athanor evals run` ledger row now carries `evidence: {checked, stale, hard}`, and `summary.json` has `evidence_checked` and `stale_evidence`. Stale evidence is reported in the suite but does not change a case's status. The promotion ledger event records `evidence_checked` and `stale_evidence`.

## Design notes

- All file access in this layer goes through AgentSearch's five read-only tools (`file_search`, `content_search`, `read_file`, `verify_evidence`, `index_status`). `read_file`'s `content_sha256` is the SHA-256 of the raw file, so a citation can be checked with `sha256sum`.
- The index is derived state. Deleting `.athanor/` loses nothing, and `athanor search index` rebuilds it.
- Locating moved lines uses the citation's literal pattern, so only pattern citations can be `moved`; line-number citations go straight from `changed-lines-intact` to `stale`.

## Caveats

- A citation proves the cited bytes are unchanged, not that they are correct. A wrong number cited at capture time stays wrong and stays `fresh`.
- `changed-lines-intact` and `moved` are soft by design. The surrounding text may have changed meaning without touching the cited lines.
- The extra pins AgentSearch at a release candidate (`v1.0.0-rc5`) as a direct Git dependency. Like `[evals]`, it installs from GitHub but would not be accepted by PyPI.
- Python 3.11+ only (AgentSearch's own floor). On 3.10, `athanor search …` and `athanor evals evidence` exit 2 with an install hint. The registry row check still runs there.
