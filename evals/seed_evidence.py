"""Attach AgentSearch citations to the seeded eval cases (v2.8.0).

    python evals/seed_evidence.py          # repo root, athanor[search] installed (Python 3.11+)

Each case cites the lines it rests on, with the file's SHA-256 and the cited
lines' SHA-256: the fixed source lines and the CHANGELOG entry for the bugs, and
the tuning-log / results lines and raw run records for the tuning cases.
`athanor evals evidence --check` (and every suite run and promotion) re-verifies them.
"""
from athanor.evals.cases import load_cases
from athanor.evals.evidence import attach

CITES = {
    "ATH-B001": [("src/athanor/utils/logging.py", "json.dumps(row) + '\\n'"),
                 ("CHANGELOG.md", "`utils.logging.log_jsonl` wrote a literal")],
    "ATH-B002": [("src/athanor/experiments/registry.py", "def deep_merge"),
                 ("CHANGELOG.md", "`inherits:` did a shallow `dict.update`")],
    "ATH-B003": [("src/athanor/evolution/dgm_loop.py", "def derive_seed"),
                 ("CHANGELOG.md", "Telemetry seeds `seed + g*10000 + i + attempt` collided")],
    "ATH-B004": [("src/athanor/evolution/dgm_loop.py", "def _make_run_path"),
                 ("CHANGELOG.md", "Two runs started in the same second shared one folder")],
    "ATH-T001": [("docs/TUNING_LOG.md", "The selected setting overfit its safety"),
                 ("docs/selfmod/arms_results.md", "Severe regressions (>2× worse or broken)"),
                 ("docs/selfmod/arms_results.json", None)],
    "ATH-T002": [("docs/TUNING_LOG.md", "Measured: severe 30 vs 8"), ("docs/tuning/log.json", None)],
    "ATH-T003": [("docs/TUNING_LOG.md", "At τ = 0.8 the threshold sits right at"), ("docs/tuning/log.json", None)],
    "ATH-T004": [("docs/selfmod/arms_results.md", "Commits that broke the program"),
                 ("docs/selfmod/arms_results.json", None)],
    "ATH-T005": [("docs/tsp_selfmod/results.md", "| validity+athanor-conservative |"),
                 ("docs/tsp_selfmod/results.md", "| validity+athanor-tuned |"), ("docs/tsp_selfmod/results.json", None)],
    "ATH-T006": [("docs/tsp_selfmod/results.md", "| validity+athanor |"), ("docs/tsp_selfmod/results.json", None)],
    "ATH-T007": [("docs/tsp_selfmod/results.md", "| ungoverned |"), ("docs/tsp_selfmod/results.json", None)],
}

if __name__ == "__main__":
    first = True
    for ac in load_cases("evals/cases"):
        r = attach(ac, CITES.get(ac.case_id, []), refresh=first)
        first = False
        print(r)
