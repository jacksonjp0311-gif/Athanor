import math

import numpy as np
import pytest

from athanor.selfmod.agent import (SEED_SOURCE, BrokenProgram, compile_source, evaluate, mutate,
                                   structural_distance)
from athanor.selfmod.experiment import (DEFAULTS, compact, edit_trajectory, make_task, render_markdown,
                                        run_selfmod, run_selfmod_bench)
from athanor.core.coherence import delta_phi


def test_seed_program_compiles_and_runs():
    f = compile_source(SEED_SOURCE)
    out, bad = evaluate(f, [-1.0, 0.0, 2.0])
    assert bad == 0 and list(out) == [-1.0, 0.0, 2.0]


def test_breaking_edits_are_detected_not_raised():
    f = compile_source("def f(x):\n    return math.log(x)\n")
    out, bad = evaluate(f, [-1.0, 1.0])
    assert bad == 1 and math.isnan(out[0]) and out[1] == 0.0
    g = compile_source("def f(x):\n    return 1.0 / (x - 1.0)\n")
    assert evaluate(g, [1.0])[1] == 1


def test_grammar_whitelist_blocks_arbitrary_code():
    with pytest.raises(BrokenProgram):
        compile_source("def f(x):\n    return __import__('os').getcwd()\n")
    with pytest.raises(BrokenProgram):
        compile_source("def f(x):\n    return math.pi\n")


def test_mutation_rewrites_source_deterministically():
    a = mutate(SEED_SOURCE, np.random.default_rng(5))
    b = mutate(SEED_SOURCE, np.random.default_rng(5))
    assert a == b
    src = SEED_SOURCE
    rng = np.random.default_rng(1)
    for _ in range(30):
        src, _ = mutate(src, rng)
        compile_source(src)  # every emitted program stays inside the grammar


def test_structural_distance_bounds():
    assert structural_distance(SEED_SOURCE, SEED_SOURCE) == 0.0
    d = structural_distance(SEED_SOURCE, "def f(x):\n    return math.sin(x) * 2.0\n")
    assert 0.0 < d <= 1.0


def test_edit_trajectory_gives_per_probe_dphi():
    task = make_task(0, DEFAULTS)
    old_s, new_s = SEED_SOURCE, "def f(x):\n    return math.log(x)\n"
    traj = edit_trajectory(compile_source(old_s), compile_source(new_s), old_s, new_s, task, DEFAULTS)
    d = delta_phi(traj.astype(np.float32))
    assert d.shape == (len(task["xpr"]),)
    # probes at x <= 0 break the new program and get the large penalty
    assert (d[task["xpr"] <= 0] > 100).all()


def test_governed_run_never_commits_unapproved_and_is_deterministic(tmp_path):
    a = run_selfmod(2, True, {"steps": 60}, out_dir=str(tmp_path / "a"))
    b = run_selfmod(2, True, {"steps": 60}, out_dir=str(tmp_path / "b"))
    assert a["run_digest"] == b["run_digest"]
    assert a["unapproved_commits"] == 0
    assert (tmp_path / "a" / "final_self.py").read_text() == a["final_source"]


def test_ungoverned_commits_every_improving_edit():
    u = run_selfmod(2, False, {"steps": 60})
    g = run_selfmod(2, True, {"steps": 60})
    assert u["commits"] >= g["commits"]


def test_bench_summary_and_markdown():
    res = run_selfmod_bench([0, 1], {"steps": 30})
    assert set(res["summary"]) == {"governed", "ungoverned"}
    assert "| Metric | Governed | Ungoverned |" in render_markdown(res)
    assert all("series" not in r for r in compact(res)["runs"])
