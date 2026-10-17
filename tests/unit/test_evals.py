"""Bug2Eval integration. Skipped when the optional extra (athanor[evals]) is not installed."""
import io, json, os, shutil, subprocess, tarfile

import pytest

pytest.importorskip("bug2eval")

from athanor.config_registry import Registry
from athanor.evals.cases import load_cases
from athanor.evals.suite import run_suite

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CASES = os.path.join(ROOT, "evals", "cases")
REG = os.path.join(ROOT, "configs", "registry")


def _git_src(ref, dest):
    data = subprocess.run(["git", "-C", ROOT, "archive", "--format=tar", ref, "src"], stdout=subprocess.PIPE,
                          check=False)
    if data.returncode != 0:
        pytest.skip("git history not available (shallow clone?)")
    with tarfile.open(fileobj=io.BytesIO(data.stdout)) as tf:
        tf.extractall(dest, **({'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}))
    return os.path.join(dest, "src")


def test_seeded_cases_present():
    ids = {c.case_id: c for c in load_cases(CASES)}
    for cid in ["ATH-B001", "ATH-B002", "ATH-B003", "ATH-B004", "ATH-T001", "ATH-T002", "ATH-T003", "ATH-T004"]:
        assert cid in ids
    assert ids["ATH-T001"].sidecar["recorded"]["before_metrics"]["severe_regressions"] == 34
    assert ids["ATH-T001"].sidecar["recorded"]["after_metrics"]["severe_regressions"] == 2
    assert ids["ATH-B003"].sidecar["provenance"]["after_commit"].startswith("31c1c4a")


def test_bug_suite_passes_on_current_code_and_is_deterministic(tmp_path):
    a = run_suite(cases_root=CASES, out_dir=str(tmp_path / "a"), kinds=["bug"])
    b = run_suite(cases_root=CASES, out_dir=str(tmp_path / "b"), kinds=["bug"])
    assert a["ok"], a["results"]
    assert a["counts"] == {"PASS": 4}
    assert a["suite_digest"] == b["suite_digest"]
    from athanor.ledger import verify_ledger
    assert verify_ledger(a["ledger"]).ok


def test_reintroduced_bugs_are_caught(tmp_path):
    old_src = _git_src("ad23756", str(tmp_path / "old"))
    res = run_suite(cases_root=CASES, out_dir=str(tmp_path / "r"), kinds=["bug"], src_root=old_src)
    assert not res["ok"]
    assert res["counts"] == {"REGRESSION": 4}


def test_tampered_case_is_an_error(tmp_path):
    dst = tmp_path / "cases"
    shutil.copytree(os.path.join(CASES, "ATH-B001"), dst / "ATH-B001")
    meta = dst / "ATH-B001" / "metadata.json"
    m = json.loads(meta.read_text())
    m["verification"]["timeout_sec"] = 5
    meta.write_text(json.dumps(m))
    res = run_suite(cases_root=str(dst), out_dir=str(tmp_path / "o"))
    assert res["counts"] == {"ERROR": 1}


def test_candidate_that_rebreaks_a_tuning_case_is_blocked(tmp_path):
    reg = Registry(REG)
    e = reg.get("selfmod/adaptive@1.0.0")
    cand = {"ref": e["ref"], "family": e["family"], "spec": e["spec"], "spec_hash": e["spec_hash"]}
    res = run_suite(cases_root=CASES, out_dir=str(tmp_path / "c"), ids=["ATH-T001"], candidate=cand)
    assert res["counts"] == {"BLOCKED": 1}
    assert "severe_regressions=34" in res["results"][0]["notes"][0]


def test_capture_bug_roundtrip_and_refuses_non_discriminating(tmp_path):
    from athanor.evals.capture import capture_bug
    v = os.path.join(ROOT, "evals", "verifiers", "ATH-B001_log_jsonl_newline.py")
    out = capture_bug(case_id="X-1", title="newline", before_ref="ad23756", after_ref="31c1c4a", verifier=v,
                      repo=ROOT, out_root=str(tmp_path))
    assert out["validation"] == {"valid": True, "before": 1, "after": 0}
    assert os.path.isfile(os.path.join(out["case"], "athanor.json"))
    with pytest.raises(ValueError, match="does not discriminate"):
        capture_bug(case_id="X-2", title="same", before_ref="31c1c4a", after_ref="31c1c4a", verifier=v,
                    repo=ROOT, out_root=str(tmp_path))
    assert not os.path.exists(os.path.join(str(tmp_path), "X-2"))


def test_behaviour_verdict_identical_configs_approve():
    from athanor.evals.promotion import behaviour_verdict
    e = Registry(REG).get("selfmod/validity-athanor@1.0.0")
    v = behaviour_verdict(e, e, seeds=[200, 201], steps=60, workers=1)
    assert v["verdict"] == "APPROVE" and v["dphi_max"] == 0.0
