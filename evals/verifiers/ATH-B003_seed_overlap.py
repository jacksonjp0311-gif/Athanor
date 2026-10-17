"""ATH-B003 verifier: every telemetry evaluation in a run gets a distinct seed.

2.0.0 used seed + g*10000 + i for candidate i and seed + g*10000 + i + k for its
k-th REFINE retry, so retry k of candidate i reused candidate i+k's noise stream.
"""
import os, sys, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))
import athanor
if not os.path.abspath(athanor.__file__).startswith(os.path.join(HERE, "src")):
    print("athanor was not imported from the workspace snapshot: " + athanor.__file__)
    sys.exit(3)

import athanor.evolution.dgm_loop as loop

seen = []
orig = loop.TelemetryAgent.step
def spy(self, cand, *a, **kw):
    seen.append(int(self.seed))
    return orig(self, cand, *a, **kw)
loop.TelemetryAgent.step = spy

cfg = {"seed": 1337, "threshold_h7": 0.70, "refine_floor": 0.50, "alpha": 0.7, "steps_per_candidate": 18,
       "population": 10, "generations": 3, "refine_attempts": 2, "dphi_mode": "l2", "genome_dim": 64,
       "archive": {"bins": [16, 16]}}
with tempfile.TemporaryDirectory() as tmp:
    cfg["run"] = {"out_dir": tmp}
    try:
        from athanor.experiments.registry import validate_config
        cfg = validate_config(cfg)
    except Exception:
        pass
    import logging; logging.disable(logging.WARNING)
    loop.run(cfg)
dups = len(seen) - len(set(seen))
if len(seen) <= 30:  # 3 generations x 10 candidates; more means REFINE retries ran
    print(f"FAIL: verifier needs REFINE retries to occur; only {len(seen)} evaluations ran")
    sys.exit(1)
if dups:
    print(f"FAIL: {dups} of {len(seen)} telemetry evaluations reused another evaluation's seed")
    sys.exit(1)
print(f"PASS: {len(seen)} telemetry evaluations, all seeds distinct")
