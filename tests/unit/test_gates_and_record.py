import json

import numpy as np
import pytest

from athanor.agents.verifier_agent import VerifierAgent
from athanor.core.types import Candidate, TelemetryBatch
from athanor.evolution.archive import MapElitesArchive
from athanor.evolution.dgm_loop import run
from athanor.experiments.registry import validate_config
from athanor.ledger import read_ledger
from athanor.scripts.cli import diff_runs


def _cand(step=0.1, n=20, dim=3):
    traj = np.cumsum(np.full((n, dim), step / np.sqrt(dim), dtype=np.float32), axis=0)
    return Candidate(id="c", genome=np.zeros(dim, np.float32), telemetry=TelemetryBatch(traj=traj, meta={}))


def test_default_verifier_records_only_h7():
    c = VerifierAgent().step(_cand())
    assert c.verdict == "APPROVE"
    assert [x["gate"] for x in c.tags["checks"]] == ["H7"]


def test_h44_gate_downgrades_approve_to_refine():
    # H7 == 1.0 here, so excess over threshold 0.7 is 0.3
    v = VerifierAgent(threshold_h7=0.7, h44={"enabled": True, "min_excess": 0.5})
    c = v.step(_cand())
    assert c.verdict == "REFINE" and "H44" in c.reason
    v2 = VerifierAgent(threshold_h7=0.7, h44={"enabled": True, "min_excess": 0.2})
    assert v2.step(_cand()).verdict == "APPROVE"


def test_h20_gate_is_seeded_and_can_downgrade():
    strict = VerifierAgent(h20={"enabled": True, "sigma": 0.5, "min_immunity": 0.999})
    a = strict.step(_cand(), gate_seed=5)
    b = strict.step(_cand(), gate_seed=5)
    assert a.verdict == "REFINE" and "H20" in a.reason
    assert a.tags["checks"][1]["value"] == b.tags["checks"][1]["value"]
    lax = VerifierAgent(h20={"enabled": True, "sigma": 0.0, "min_immunity": 0.9})
    assert lax.step(_cand(), gate_seed=5).verdict == "APPROVE"


def test_gates_never_rescue_a_reject():
    v = VerifierAgent(h20={"enabled": True, "min_immunity": 0.0}, h44={"enabled": True})
    c = v.step(_cand(step=5.0))
    assert c.verdict == "REJECT"


def test_gate_config_validation():
    out = validate_config({})
    assert out["gates"]["h20"]["enabled"] is False and out["gates"]["h44"]["enabled"] is False
    with pytest.raises(ValueError):
        validate_config({"gates": {"h20": {"min_immunity": 2}}})


def _cfg(tmp_path, **kw):
    base = {"seed": 3, "generations": 4, "population": 5, "steps_per_candidate": 12, "genome_dim": 8,
            "run": {"out_dir": str(tmp_path)}}
    base.update(kw)
    return validate_config(base)


def test_decision_record_and_ledger_explain_verdicts(tmp_path):
    out = run(_cfg(tmp_path))
    rec = json.load(open(f"{out['run_path']}/decision_record.json"))
    assert rec["run_digest"] == out["run_digest"]
    assert len(rec["lineage"]) == 4
    assert rec["promotions"] == sum(x["promoted"] for x in rec["lineage"])
    for x in rec["lineage"]:
        assert x["promoted"] == (x["parent_before"] != x["parent_after"])
    rows = read_ledger(f"{out['run_path']}/ledger.jsonl")
    for r in rows:
        assert r["checks"][0]["gate"] == "H7"
        assert r["refine_trail"][-1]["verdict"] == r["verdict"]
        assert r["parent_id"]


def test_refine_path_is_independent_per_candidate(tmp_path):
    # Changing refine_attempts must not change candidates that never entered REFINE.
    a = read_ledger(f"{run(_cfg(tmp_path / 'a', refine_attempts=0, generations=1))['run_path']}/ledger.jsonl")
    b = read_ledger(f"{run(_cfg(tmp_path / 'b', refine_attempts=3, generations=1))['run_path']}/ledger.jsonl")
    for ra, rb in zip(a, b):
        if ra["refine_trail"][0]["verdict"] != "REFINE":
            assert ra["h7"] == rb["h7"] and ra["id"] == rb["id"]


def test_enabling_gates_changes_digest_but_stays_deterministic(tmp_path):
    g = {"h44": {"enabled": True, "min_excess": 0.2}, "h20": {"enabled": True}}
    a = run(_cfg(tmp_path / "a", gates=g))
    b = run(_cfg(tmp_path / "b", gates=g))
    c = run(_cfg(tmp_path / "c"))
    assert a["run_digest"] == b["run_digest"] != c["run_digest"]


def test_archive_json_roundtrip_and_diff(tmp_path):
    a = run(_cfg(tmp_path / "a"))
    b = run(_cfg(tmp_path / "b"))
    c = run(_cfg(tmp_path / "c", seed=4))
    d = json.load(open(f"{a['run_path']}/archive.json"))
    arc = MapElitesArchive.from_dict(d)
    assert arc.to_dict() == d and arc.stats()["filled"] == len(d["cells"])
    same = diff_runs(a["run_path"], b["run_path"])
    assert same["identical"] and same["first_divergent_seq"] is None
    other = diff_runs(a["run_path"], c["run_path"])
    assert not other["identical"] and other["first_divergent_seq"] == 0
    assert other["config_keys_changed"] == ["seed"]
