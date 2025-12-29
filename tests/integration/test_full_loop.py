from athanor.experiments.registry import load_config
from athanor.evolution.dgm_loop import run

def test_full_loop_runs(tmp_path):
    cfg = load_config('configs/toy_experiment.yaml')
    cfg['run'] = {'out_dir': str(tmp_path)}
    out = run(cfg)
    assert 'run_path' in out
