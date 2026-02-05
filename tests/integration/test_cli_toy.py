import json, subprocess, sys
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
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert 'run_path' in out

    run_path = root / out['run_path']
    ledger = run_path / 'ledger.jsonl'
    stats = run_path / 'archive_stats.json'
    metadata = run_path / 'metadata.yaml'
    assert ledger.exists()
    assert stats.exists()
    assert metadata.exists()

    with ledger.open('r', encoding='utf-8') as f:
        first = f.readline().strip()
    assert first
    json.loads(first)
