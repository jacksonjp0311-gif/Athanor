import json, os

import pytest

from athanor.config_registry import Registry, parse_ref, required_bump, spec_hash
from athanor._cfgset import apply_sets

SPEC = {"arm": {"validity": True, "athanor": True, "gamma": None}, "cfg": {}}


def test_parse_ref():
    assert parse_ref("selfmod/adaptive@1.1.0") == ("selfmod", "adaptive", "1.1.0")
    with pytest.raises(ValueError):
        parse_ref("adaptive@1.1")


def test_register_status_lineage_and_ledger(tmp_path):
    reg = Registry(str(tmp_path))
    reg.register("f/a@1.0.0", SPEC, parent=None, reason="base")
    child = apply_sets(SPEC, ["cfg.threshold_h7=0.75"])
    reg.register("f/a@1.1.0", child, parent="f/a@1.0.0", reason="tighter")
    assert reg.status("f/a@1.1.0") == "candidate"
    reg.record("promote", "f/a@1.0.0", reason="bootstrap")
    assert reg.incumbent("f") == "f/a@1.0.0"
    reg.record("promote", "f/a@1.1.0", reason="gate", replaces="f/a@1.0.0")
    assert reg.incumbent("f") == "f/a@1.1.0"
    assert reg.status("f/a@1.0.0") == "retired"
    assert [x["ref"] for x in reg.lineage("f/a@1.1.0")] == ["f/a@1.1.0", "f/a@1.0.0"]
    assert reg.verify()["ok"]


def test_semver_rules_enforced(tmp_path):
    reg = Registry(str(tmp_path))
    reg.register("f/a@1.0.0", SPEC, parent=None, reason="base")
    with pytest.raises(ValueError, match="needs a minor bump"):
        reg.register("f/a@1.0.1", apply_sets(SPEC, ["cfg.threshold_h7=0.8"]), parent="f/a@1.0.0", reason="x")
    with pytest.raises(ValueError, match="needs a major bump"):
        reg.register("f/a@1.1.0", apply_sets(SPEC, ["arm.gamma=6"]), parent="f/a@1.0.0", reason="x")
    with pytest.raises(FileExistsError):
        reg.register("f/a@1.0.0", SPEC, parent=None, reason="dup")
    assert required_bump(SPEC, SPEC) == "patch"


def test_edits_after_registration_are_detected(tmp_path):
    reg = Registry(str(tmp_path))
    reg.register("f/a@1.0.0", SPEC, parent=None, reason="base")
    p = reg.entry_path("f/a@1.0.0")
    e = json.load(open(p))
    e["spec"]["cfg"]["threshold_h7"] = 0.5
    json.dump(e, open(p, "w"))
    res = reg.verify()
    assert not res["ok"] and any("spec_hash" in x for x in res["errors"])


def test_repo_registry_is_consistent():
    root = os.path.join(os.path.dirname(__file__), "..", "..", "configs", "registry")
    reg = Registry(root)
    res = reg.verify()
    assert res["ok"], res["errors"]
    assert reg.status("selfmod/adaptive@1.0.0") == "rejected"
    assert reg.incumbent("selfmod") is not None
    assert spec_hash(reg.get("selfmod/adaptive@1.1.0")["spec"]) == reg.get("selfmod/adaptive@1.1.0")["spec_hash"]
