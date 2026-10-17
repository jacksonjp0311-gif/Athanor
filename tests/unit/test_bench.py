import json

from athanor.bench import render_chart, render_markdown, run_bench
from athanor.evolution.dgm_loop import run
from athanor.experiments.registry import validate_config
from athanor.scripts.cli import _parse_seeds


def _cfg(**kw):
    c = {"generations": 4, "population": 5, "steps_per_candidate": 12, "genome_dim": 8,
         "alpha": 1.0, "proposer_sigma": 0.5, "proposer_step_cap": 2.0}
    c.update(kw)
    return validate_config(c)


def test_ungoverned_promotes_every_generation(tmp_path):
    out = run(validate_config({**_cfg(), "governor": {"enabled": False}, "run": {"out_dir": str(tmp_path)}}))
    rec = json.load(open(f"{out['run_path']}/decision_record.json"))
    assert rec["governed"] is False
    assert all(x["parent_after"] == x["best_id"] for x in rec["lineage"])
    # REFINE retries are disabled in the baseline
    rows = [json.loads(l) for l in open(f"{out['run_path']}/ledger.jsonl")]
    assert all(len(r["refine_trail"]) == 1 for r in rows)


def test_governed_never_promotes_unapproved(tmp_path):
    res = run_bench(_cfg(), seeds=[0, 1])
    assert res["summary"]["governed"]["promoted_unapproved"] == 0
    assert len(res["runs"]) == 4


def test_bench_is_deterministic_and_renders(tmp_path):
    a = run_bench(_cfg(), seeds=[3])
    b = run_bench(_cfg(), seeds=[3])
    assert [r["run_digest"] for r in a["runs"]] == [r["run_digest"] for r in b["runs"]]
    assert "| Metric | Governed | Ungoverned |" in render_markdown(a)
    render_chart(a, str(tmp_path / "c.png"))
    assert (tmp_path / "c.png").stat().st_size > 1000


def test_parse_seeds():
    assert _parse_seeds("0-3,7") == [0, 1, 2, 3, 7]


def test_builtin_bench_config_matches_repo_file():
    from pathlib import Path
    from athanor.bench import default_bench_config
    from athanor.experiments.registry import load_config
    repo = load_config(str(Path(__file__).resolve().parents[2] / "configs" / "bench.yaml"))
    assert repo == default_bench_config()
