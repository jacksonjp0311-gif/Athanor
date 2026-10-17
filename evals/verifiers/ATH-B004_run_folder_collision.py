"""ATH-B004 verifier: two runs started in the same second must not share a run folder.

2.0.0 named folders run_<UTC second> with exist_ok=True, so the second run appended to the first run's ledger.
"""
import os, sys, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
import athanor
if not os.path.abspath(athanor.__file__).startswith(os.path.join(HERE, "src")):
    print("athanor was not imported from the workspace snapshot: " + athanor.__file__)
    sys.exit(3)

import athanor.evolution.dgm_loop as loop
import logging; logging.disable(logging.WARNING)

loop.now_tag = lambda: "2026-01-01_000000"  # freeze the clock: both runs start "in the same second"
cfg = {"seed": 1, "threshold_h7": 0.7, "alpha": 0.7, "steps_per_candidate": 8, "population": 3,
       "generations": 1, "refine_attempts": 0, "dphi_mode": "l2", "genome_dim": 16, "archive": {"bins": [4, 4]}}
with tempfile.TemporaryDirectory() as tmp:
    cfg["run"] = {"out_dir": tmp}
    try:
        from athanor.experiments.registry import validate_config
        cfg = validate_config(cfg)
    except Exception:
        pass
    a = loop.run(dict(cfg))["run_path"]
    b = loop.run(dict(cfg))["run_path"]
    rows_a = sum(1 for _ in open(os.path.join(a, "ledger.jsonl"), encoding="utf-8"))
if os.path.abspath(a) == os.path.abspath(b):
    print(f"FAIL: both runs wrote to {os.path.basename(a)} (ledger now has {rows_a} rows from 2 runs)")
    sys.exit(1)
print(f"PASS: distinct run folders {os.path.basename(a)} and {os.path.basename(b)}")
