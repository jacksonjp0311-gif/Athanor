"""AgentSearch evidence layer. Skipped on Python < 3.11 or without athanor[search]."""
import json, os, shutil, sys

import pytest

if sys.version_info < (3, 11):
    pytest.skip("AgentSearch needs Python 3.11+", allow_module_level=True)
pytest.importorskip("agentsearch")

from athanor.search import EvidenceIndex, read_evidence, write_evidence  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "log.md").write_text("intro\nrow A\nsevere 30 vs 8\nrow C\n", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "ledger.jsonl").write_text('{"verdict":"APPROVE","h7":0.81}\n', encoding="utf-8")
    return tmp_path


def test_five_tools_and_scopes(repo):
    with EvidenceIndex(str(repo)) as idx:
        idx.refresh()
        assert idx.status()["ok"]
        hit = idx.find("ledger", scope="runs")
        assert hit["ok"] and hit["hits"][0]["path"].endswith("ledger.jsonl")
        g = idx.grep("APPROVE", scope="runs")
        assert g["ok"] and g["files"][0]["matches"][0]["line"] == 1
        r = idx.read("docs/log.md", 3, 1)
        assert r["text"] == "severe 30 vs 8"
        v = idx.call("verify_evidence", path=idx.abspath("docs/log.md"), sha256=r["content_sha256"])
        assert v["verified"] is True


def test_citation_statuses(repo):
    log = repo / "docs" / "log.md"
    with EvidenceIndex(str(repo)) as idx:
        idx.refresh()
        c = idx.cite("docs/log.md", pattern="severe 30 vs 8")
        whole = idx.cite("data/ledger.jsonl")
        assert c["start_line"] == 3 and idx.verify(c)["status"] == "fresh"
        log.write_text("intro\nrow A\nsevere 30 vs 8\nrow C changed\n", encoding="utf-8")
        assert idx.verify(c)["status"] == "changed-lines-intact"
        log.write_text("new\nlines\nintro\nrow A\nsevere 30 vs 8\n", encoding="utf-8")
        assert idx.verify(c)["status"] == "moved"
        log.write_text("intro\nsevere 31 vs 8\n", encoding="utf-8")
        assert idx.verify(c)["status"] == "stale"
        os.remove(log)
        assert idx.verify(c)["status"] == "missing"
        (repo / "data" / "ledger.jsonl").write_text("{}\n", encoding="utf-8")
        res = idx.check([whole])
        assert res["fresh"] == 0 and res["hard"][0]["status"] == "stale"


def test_evidence_file_roundtrip(tmp_path):
    write_evidence(str(tmp_path), [{"path": "a", "sha256": "0" * 64, "whole_file": True}],
                   agentsearch_version="x", athanor_version="y")
    assert read_evidence(str(tmp_path))[0]["path"] == "a"
    assert read_evidence(str(tmp_path / "nope")) == []


def test_registry_pins_evidence_hashes(tmp_path):
    from athanor.config_registry import Registry
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "r.md").write_text("result\n", encoding="utf-8")
    reg = Registry(str(tmp_path / "configs" / "registry"))
    e = reg.register("f/a@1.0.0", {"arm": {}, "cfg": {}}, parent=None, reason="x",
                     evidence=[{"source": "docs/r.md", "severe": 2}])
    assert e["evidence"][0]["path"] == "docs/r.md" and len(e["evidence"][0]["sha256"]) == 64


@pytest.mark.skipif(not __import__("athanor.evals", fromlist=["x"]).bug2eval_available(), reason="needs athanor[evals]")
def test_suite_and_promotion_flag_stale_evidence(tmp_path):
    from athanor.evals.cases import load_cases
    from athanor.evals.evidence import attach, check_case
    from athanor.evals.promotion import check_promotion_evidence
    from athanor.config_registry import Registry
    repo = tmp_path / "repo"
    (repo / "evals").mkdir(parents=True)
    shutil.copytree(os.path.join(ROOT, "evals", "cases", "ATH-T002"), repo / "evals" / "cases" / "ATH-T002")
    shutil.copytree(os.path.join(ROOT, "configs"), repo / "configs")
    (repo / "docs").mkdir()
    (repo / "docs" / "TUNING_LOG.md").write_text("x\nMeasured: severe 30 vs 8\ny\n", encoding="utf-8")
    ac = load_cases(str(repo / "evals" / "cases"))[0]
    attach(ac, [("docs/TUNING_LOG.md", "Measured: severe 30 vs 8")], repo=str(repo))
    assert check_case(ac, repo=str(repo))["stale"] == []
    (repo / "docs" / "TUNING_LOG.md").write_text("x\nMeasured: severe 99 vs 8\ny\n", encoding="utf-8")
    chk = check_case(ac, repo=str(repo))
    assert [s["status"] for s in chk["stale"]] == ["stale"]
    reg = Registry(str(repo / "configs" / "registry"))
    ev = check_promotion_evidence(reg, reg.get("selfmod/adaptive@1.1.0"), str(repo / "evals" / "cases"), {})
    assert ev["checked"] >= 3 and [h["path"] for h in ev["hard"]] == ["docs/TUNING_LOG.md"]
