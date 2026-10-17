import json, os, subprocess, sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _cli(*args, cwd=ROOT):
    return subprocess.run([sys.executable, "-m", "athanor", *args], capture_output=True, text=True, cwd=cwd, timeout=600)


def test_bench_all_arms_match_registry():
    from athanor.bench_all import SELFMOD_ARMS, TSP_ARMS
    from athanor.config_registry import Registry, spec_hash
    reg = Registry(os.path.join(ROOT, "configs", "registry"))
    for name, (ref, spec) in {**SELFMOD_ARMS, **TSP_ARMS}.items():
        if ref:
            assert spec_hash(spec) == reg.get(ref)["spec_hash"], name


def test_bench_all_small_run(tmp_path):
    r = _cli("bench", "--all", "--seeds", "3000", "--steps", "30", "--workers", "2", "--out", str(tmp_path))
    assert r.returncode == 0, r.stderr
    res = json.load(open(tmp_path / "results.json"))
    assert set(res["systems"]) == {"synthetic", "selfmod", "tsp"} and res["seed_sets"] == ["bench-v3"]
    md = (tmp_path / "results.md").read_text()
    assert "## Headline" in md and (tmp_path / "benchmark_all.png").exists()


def test_doctor_and_demo(tmp_path):
    d = _cli("doctor", "--json")
    assert d.returncode == 0, d.stdout + d.stderr
    checks = {c["check"]: c["status"] for c in json.loads(d.stdout)["checks"]}
    assert checks["governor self-test"] == "OK" and checks["run + verify + determinism"] == "OK"
    m = _cli("demo", "--out", str(tmp_path), "--skip-evals")
    assert m.returncode == 0 and "demo passed" in m.stdout, m.stdout + m.stderr


def test_clear_cli_error(tmp_path):
    r = _cli("run", "--config", str(tmp_path / "missing.yaml"))
    assert r.returncode == 2 and "error: FileNotFoundError" in r.stderr and "hint:" in r.stderr
    assert "Traceback" not in r.stderr


def test_tsp_scaled_inputs_cover_deployment_size():
    from athanor.selfmod.tsp_experiment import fixed_sets, scaled_inputs, deploy_n_max, TSP_DEFAULTS
    n = deploy_n_max(TSP_DEFAULTS, fixed_sets())
    assert n == max(len(D) for D in fixed_sets()["held"])
    sizes = sorted(len(D) for D in scaled_inputs(n))
    assert sizes[-1] == n and sizes[0] == -(-n // 2) and len(sizes) == 6
    assert max(len(D) for D in fixed_sets()["probes"]) < n  # the 2.6 probes never reached deployment size


def test_tsp_probe_scaling_validated_and_default_unchanged():
    from athanor.selfmod.tsp_experiment import run_tsp, TSP_DEFAULTS
    assert TSP_DEFAULTS["probe_scaling"] is None
    with pytest.raises(ValueError, match="probe_scaling"):
        run_tsp(0, {"validity": True, "athanor": False, "gamma": None}, cfg={"steps": 1, "probe_scaling": "x"})
    arm = {"validity": True, "athanor": True, "gamma": None}
    a = run_tsp(0, arm, cfg={"steps": 5})
    b = run_tsp(0, arm, cfg={"steps": 5, "probe_scaling": "checks"})
    assert a["series"]["held"][0] == b["series"]["held"][0]


def test_tsp_promotion_signature_identical_configs_approve():
    from athanor.evals.promotion import behaviour_verdict
    spec = {"arm": {"validity": True, "athanor": True, "gamma": None}, "cfg": {}}
    e = {"ref": "tsp/x@1.0.0", "family": "tsp", "spec": spec}
    v = behaviour_verdict(e, e, seeds=[10000, 10001], steps=20, workers=1)
    assert v["verdict"] == "APPROVE" and v["dphi_max"] == 0.0 and v["family"] == "tsp"
