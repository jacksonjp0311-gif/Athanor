import json
import os

import numpy as np
import pytest

from athanor.selfmod.tsp_experiment import (GOOD_RATIO, KAPPA, fixed_sets, make_check, check_suite, mean_ratio,
                                            run_tsp, training_set, tsp_arms, tsp_trajectory, tuning_sets)
from athanor.selfmod.tsp_program import (SEED_PROGRAM, BrokenProgram, Program, mutate_program, run_instance,
                                         structural_distance)
from athanor.core.validity import validity_check

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def test_seed_program_is_valid_and_weak():
    s = fixed_sets()
    r, fail = mean_ratio(Program(SEED_PROGRAM), s["held"], s["held_ref"])
    assert fail is None and 1.1 < r < 1.25          # greedy only: budget(n) == 0 disables 2-opt
    on = Program(SEED_PROGRAM.replace("def budget(n):\n    return 0", "def budget(n):\n    return n"))
    r2, _ = mean_ratio(on, s["held"], s["held_ref"])
    assert r2 < GOOD_RATIO < r                         # one edit away from "good" - but the edit must be found


def test_runaway_loop_is_a_deterministic_timeout():
    src = SEED_PROGRAM.replace("delta < -1e-09", "delta < 1e9").replace("return 0\n\n\ndef improve",
                                                                          "return 10000\n\n\ndef improve")
    D = fixed_sets()["held"][0]
    assert run_instance(Program(src), D) == ("timeout", None)


def test_silent_wrong_answer_is_lenient_for_agent_but_invalid_for_harness():
    src = SEED_PROGRAM.replace("while len(tour) < n:", "while len(tour) < n - 2:")
    D = fixed_sets()["held"][0]
    st, L = run_instance(Program(src), D, strict=False)
    assert st == "ok" and L > 0
    assert run_instance(Program(src), D, strict=True) == ("invalid", None)
    # the unit-test-style check suite (reused validity_check) catches it
    assert not validity_check(make_check(Program(src)), check_suite(training_set(0, 24)["train"]))["passed"]
    assert validity_check(make_check(Program(SEED_PROGRAM)), check_suite(training_set(0, 24)["train"]))["passed"]


def test_sandbox_rejects_imports_and_dunders():
    with pytest.raises(BrokenProgram):
        Program("import os\n" + SEED_PROGRAM)
    with pytest.raises(BrokenProgram):
        Program(SEED_PROGRAM + "\ndef g():\n    return __tick\n")


def test_mutation_is_deterministic_and_produces_every_failure_class():
    a = mutate_program(SEED_PROGRAM, np.random.default_rng(3))
    b = mutate_program(SEED_PROGRAM, np.random.default_rng(3))
    assert a == b
    D = fixed_sets()["held"][0]
    seen = set()
    for k in range(300):
        src, _ = mutate_program(SEED_PROGRAM, np.random.default_rng(k))
        try:
            seen.add(run_instance(Program(src), D)[0])
        except (BrokenProgram, SyntaxError):
            seen.add("compile")
    assert {"ok", "crash", "invalid"} <= seen


def test_trajectory_zero_for_identical_and_big_for_failure():
    s = fixed_sets()
    L = [10.0] * len(s["probes"])
    t = tsp_trajectory(L, L, SEED_PROGRAM, SEED_PROGRAM, {"structure_weight": 0.5})
    assert np.allclose(t, 0)
    t2 = tsp_trajectory(L, [11.0] * len(L), SEED_PROGRAM, SEED_PROGRAM, {"structure_weight": 0.5})
    assert np.allclose(np.diff(t2[:, 0]), 1.0 / (10 * KAPPA) * 1.0)
    t3 = tsp_trajectory(L, [None] * len(L), SEED_PROGRAM, SEED_PROGRAM, {"structure_weight": 0.5})
    assert np.diff(t3[:, 0]).min() >= 1000
    assert structural_distance(SEED_PROGRAM, SEED_PROGRAM) == 0.0


def test_tuning_instances_disjoint_from_held_out():
    assert tuning_sets()["held"] != fixed_sets()["held"]
    assert tuning_sets()["probes"] == fixed_sets()["probes"]


def test_run_is_deterministic_and_arms_carry_over_unchanged():
    from athanor.selfmod.experiment import TUNED_ADAPTIVE_CONSERVATIVE
    arms = tsp_arms()
    assert arms["validity+athanor-conservative"]["cfg"] == TUNED_ADAPTIVE_CONSERVATIVE["cfg"]
    r1 = run_tsp(0, arms["validity+athanor-conservative"], "c", {"steps": 25})
    r2 = run_tsp(0, arms["validity+athanor-conservative"], "c", {"steps": 25})
    assert r1["series"] == r2["series"] and r1["final_source"] == r2["final_source"]


def test_published_tsp_results_reproduce_exactly():
    with open(os.path.join(ROOT, "docs", "tsp_selfmod", "results.json"), encoding="utf-8") as f:
        pub = json.load(f)
    want = {r["mode"]: r for r in pub["runs"] if r["seed"] == 1}
    arms = tsp_arms()
    for name in ("ungoverned", "validity+athanor-conservative"):
        r = run_tsp(1, arms[name], name, {"steps": pub["config"]["steps"]})
        assert r["final_held"] == want[name]["final_held"]
        assert r["commits"] == want[name]["commits"]
        assert r["broken_commits"] == want[name]["broken_commits"]
