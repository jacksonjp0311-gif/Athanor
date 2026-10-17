import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / 'configs' / 'toy_experiment.yaml'


def _athanor(*args):
    p = subprocess.run([sys.executable, '-m', 'athanor', *args], cwd=str(ROOT),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else None
    return p, out


def test_cli_runs_toy_legacy_form(tmp_path):
    p, out = _athanor('--config', str(CFG), '--out-dir', str(tmp_path))
    assert p.returncode == 0, p.stderr
    run_path = Path(out['run_path'])
    for name in ('ledger.jsonl', 'archive_stats.json', 'metadata.yaml', 'config.json'):
        assert (run_path / name).exists(), name
    first = (run_path / 'ledger.jsonl').read_text(encoding='utf-8').splitlines()[0]
    assert json.loads(first)['seq'] == 0


def test_cli_run_verify_replay_and_tamper(tmp_path):
    p, out = _athanor('run', '--config', str(CFG), '--out-dir', str(tmp_path), '--tag', 't1')
    assert p.returncode == 0, p.stderr
    run_path = out['run_path']

    p, v = _athanor('verify', run_path)
    assert p.returncode == 0 and v['ok'] and v['head'] == out['run_digest']

    p, r = _athanor('replay', run_path)
    assert p.returncode == 0, p.stderr
    assert r['ok'] and r['replay_digest'] == out['run_digest']

    ledger = Path(run_path) / 'ledger.jsonl'
    lines = ledger.read_text(encoding='utf-8').splitlines()
    row = json.loads(lines[3]); row['verdict'] = 'APPROVE' if row['verdict'] != 'APPROVE' else 'REJECT'
    lines[3] = json.dumps(row)
    ledger.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    p, v = _athanor('verify', run_path)
    assert p.returncode == 1 and not v['ok'] and v['first_bad_seq'] == 3
    p, r = _athanor('replay', run_path)
    assert p.returncode == 1 and not r['ok']
