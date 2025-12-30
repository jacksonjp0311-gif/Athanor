import json, subprocess, sys, os
from pathlib import Path

def test_cli_runs_toy(tmp_path):
    root = Path(__file__).resolve().parents[2]
    cfg = root / 'configs' / 'toy_experiment.yaml'
    p = subprocess.run([sys.executable, '-m', 'athanor', '--config', str(cfg)],
                       cwd=str(root),
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE,
                       text=True)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout.strip())
    assert 'run_path' in out