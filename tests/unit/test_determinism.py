from athanor.evolution.dgm_loop import derive_seed, run
from athanor.experiments.registry import validate_config


def _cfg(tmp_path, **kw):
    base = {"seed": 7, "generations": 3, "population": 4, "steps_per_candidate": 10,
            "genome_dim": 8, "run": {"out_dir": str(tmp_path)}}
    base.update(kw)
    return validate_config(base)


def test_derive_seed_has_no_offset_collisions():
    # the old scheme (seed + g*10000 + i + attempt) collided for (i, attempt=1) vs (i+1, 0)
    assert derive_seed(1, 0, 0, 1) != derive_seed(1, 0, 1, 0)
    assert derive_seed(1, 2, 3, 0) == derive_seed(1, 2, 3, 0)


def test_same_config_same_digest(tmp_path):
    a = run(_cfg(tmp_path / "a"))
    b = run(_cfg(tmp_path / "b"))
    assert a["run_digest"] == b["run_digest"]
    assert a["ledger_rows"] == 3 * 4


def test_different_seed_different_digest(tmp_path):
    a = run(_cfg(tmp_path / "a"))
    b = run(_cfg(tmp_path / "b", seed=8))
    assert a["run_digest"] != b["run_digest"]


def test_untagged_runs_do_not_share_a_folder(tmp_path):
    a = run(_cfg(tmp_path))
    b = run(_cfg(tmp_path))
    assert a["run_path"] != b["run_path"]


def test_tagged_run_refuses_to_overwrite(tmp_path):
    cfg = _cfg(tmp_path, run={"out_dir": str(tmp_path), "tag": "fixed"})
    run(cfg)
    try:
        run(cfg)
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected FileExistsError")
