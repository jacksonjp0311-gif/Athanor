import json, math, os, subprocess, sys

import numpy as np
import pytest

import athanor
from athanor import Governor, GovernorError, govern

PROBES = np.linspace(-2, 2, 8)


def probe(p):
    return [p["a"] * x + p["b"] for x in PROBES]


def evaluate(p):
    return (p["a"] - 1.0) ** 2 + (p["b"] - 0.5) ** 2


def propose(p, rng, scale):
    return {"a": p["a"] + rng.normal(0, 0.3 * scale), "b": p["b"] + rng.normal(0, 0.3 * scale)}


def test_judge_small_large_and_broken_edits():
    gov = Governor(probe, scale=1.0)
    base = {"a": 0.0, "b": 0.0}
    assert gov.judge(base, {"a": 0.05, "b": 0.0}).verdict == "APPROVE"
    assert gov.judge(base, {"a": 5.0, "b": 0.0}).verdict == "REJECT"
    d = gov.judge(base, {"a": float("nan"), "b": 0.0})
    assert d.verdict == "REJECT" and d.probe_failed
    assert 1 / (1 + 0.43) >= 0.70 - 1e-3  # coherence bound used in the docs


def test_validity_check_rejects_first():
    gov = Governor(probe, check=lambda p: p["a"] < 1.0)
    d = gov.judge({"a": 0.0, "b": 0.0}, {"a": 1.01, "b": 0.0})
    assert d.verdict == "REJECT" and d.valid is False


def test_govern_is_deterministic_and_never_commits_unapproved(tmp_path):
    led = str(tmp_path / "ledger.jsonl")
    r1 = govern({"a": 0.0, "b": 0.0}, propose, evaluate, probe, steps=80, seed=3, scale=0.5, ledger=led)
    r2 = govern({"a": 0.0, "b": 0.0}, propose, evaluate, probe, steps=80, seed=3, scale=0.5)
    assert r1.program == r2.program and r1.score < r1.initial_score
    assert all(h["outcome"] == "APPROVE" for h in r1.history if h["committed"])
    from athanor.ledger import verify_ledger
    assert verify_ledger(led).ok


def test_ungoverned_commits_every_improvement():
    r = govern({"a": 0.0, "b": 0.0}, propose, evaluate, probe, steps=80, seed=3, scale=0.01, governed=False)
    g = govern({"a": 0.0, "b": 0.0}, propose, evaluate, probe, steps=80, seed=3, scale=0.01)
    assert r.commits >= g.commits


@pytest.mark.parametrize("kwargs, msg", [({"scale": 0}, "scale must be a positive"),
                                         ({"threshold": 1.5}, "threshold must be in"),
                                         ({"refine_floor": 0.9}, "refine_floor")])
def test_clear_errors(kwargs, msg):
    with pytest.raises(GovernorError, match=msg):
        Governor(probe, **kwargs)


def test_bad_probe_and_initial_program_errors():
    with pytest.raises(GovernorError, match="sequence of numbers"):
        Governor(lambda p: "abc").judge(1, 2)
    with pytest.raises(GovernorError, match="initial program fails probe"):
        govern({"a": float("nan"), "b": 0}, propose, evaluate, probe, steps=1)


def test_example_runs():
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    out = subprocess.run([sys.executable, os.path.join(root, "examples", "govern_quickstart.py")],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert "governed" in out.stdout and "single edit:" in out.stdout


def test_seed_policy():
    from athanor.seedsets import SeedReuseError, choose_gate_seeds, classify, next_gate_block
    ev = [{"gate_seeds": [200, 215]}, {"gate_seeds": [10000, 10015]}]
    assert next_gate_block(ev)[0] == 10016
    assert choose_gate_seeds(ev, None, dry_run=True)[0][0] == 90000
    for spent in ([0, 1], [100], [200, 201], [3000], [10003]):
        with pytest.raises(SeedReuseError):
            choose_gate_seeds(ev, spent)
    seeds, pol = choose_gate_seeds(ev, [0, 1], allow_reuse=True)
    assert pol["reuse"] and "heldout-v2" in pol["overlaps"]
    assert classify([5, 105, 3005, 10020])["gate-pool"] == [10020]
