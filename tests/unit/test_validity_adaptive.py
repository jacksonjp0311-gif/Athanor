import math

from athanor.core.validity import validity_check
from athanor.selfmod.arms import run_arms, summarize
from athanor.selfmod.experiment import (ARMS, DEFAULTS, TUNED_ADAPTIVE, drift_tolerance, make_task,
                                        run_selfmod)
from athanor.selfmod.agent import compile_source, evaluate


def test_validity_check_flags_raises_and_nonfinite():
    ok = validity_check(lambda x: x * 2, [0, 1, 2])
    assert ok["passed"] and ok["inputs"] == 3
    bad = validity_check(lambda x: math.log(x), [-1.0, 1.0])
    assert not bad["passed"] and bad["failures"] == 1 and bad["first_failure"]["input"] == -1.0
    inf = validity_check(lambda x: float("inf"), [0.0])
    assert not inf["passed"]


def test_drift_tolerance_default_and_schedule():
    assert drift_tolerance(4.0, 1.0, None) == 1.0  # default: off
    assert drift_tolerance(4.0, 1.0, 2.0) == 4.0   # 2 * (2/1)^1
    assert drift_tolerance(0.01, 1.0, 2.0) == 1.0  # floor
    assert drift_tolerance(0.01, 1.0, 2.0, floor=0.7) == 0.7
    assert drift_tolerance(100.0, 1.0, 2.0, cap=6.0) == 6.0
    assert drift_tolerance(math.inf, 1.0, 2.0) == 1.0  # broken self gets no slack
    # tighter as error falls (monotone in error)
    assert drift_tolerance(1.0, 1.0, 4.0, power=3) > drift_tolerance(0.5, 1.0, 4.0, power=3)


def test_default_arms_reproduce_2_4_behaviour():
    a = run_selfmod(3, True, {"steps": 80})
    b = run_selfmod(3, cfg={"steps": 80}, arm=ARMS["athanor"])
    assert a["final_source"] == b["final_source"] and a["commits"] == b["commits"]
    u = run_selfmod(3, False, {"steps": 80})
    v = run_selfmod(3, cfg={"steps": 80}, arm=ARMS["ungoverned"])
    assert u["final_source"] == v["final_source"]


def test_validity_arm_never_commits_program_failing_validation_inputs():
    cfg = {**DEFAULTS, "steps": 200}
    for seed in (9, 14):
        r = run_selfmod(seed, cfg=cfg, arm=ARMS["validity"])
        task = make_task(seed, cfg)
        fn = compile_source(r["final_source"])
        import numpy as np
        xval = np.concatenate([task["xpr"], task["xtr"]])
        assert evaluate(fn, xval)[1] == 0


def test_tuned_adaptive_arm_runs_and_summarizes():
    cfg = {**TUNED_ADAPTIVE["cfg"], "steps": 60}
    res = run_arms([0, 1], {"v+a+ad": {"validity": True, "athanor": True, "gamma": TUNED_ADAPTIVE["gamma"]}},
                   cfg, workers=1)
    s = res["summary"]["v+a+ad"]
    for k in ("broken_commits", "severe_regressions", "median_mse_100", "median_steps_to_1p5", "commits"):
        assert k in s
    assert summarize(res["runs"], 60)["runs"] == 2


def test_matches_committed_2_4_results():
    import json
    from pathlib import Path
    old = json.loads((Path(__file__).resolve().parents[2] / "docs/selfmod/results.json").read_text())
    for r in old["runs"][:2]:  # governed seed 0, ungoverned seed 0 (1000 steps each)
        new = run_selfmod(r["seed"], r["mode"] == "governed")
        assert new["final_test_mse"] == r["final_test_mse"] and new["commits"] == r["commits"]
