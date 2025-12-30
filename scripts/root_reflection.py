import json
from pathlib import Path

REQUIRED = [
  'ledger.jsonl',
  'archive_stats.json',
  'metadata.yaml',
  'h7_trace.png',
  'fitness_trace.png',
  'dashboard.html',
]

def find_latest_run(archives_dir: Path):
    if not archives_dir.exists():
        return None
    runs = sorted([p for p in archives_dir.glob('run_*') if p.is_dir()], key=lambda p: p.name)
    if not runs:
        return None
    return runs[-1]

def main():
    root = Path('.').resolve()
    archives = root / 'data' / 'archives'
    run = find_latest_run(archives)
    if run is None:
        raise SystemExit('No run_* folder found under data/archives')

    missing = [f for f in REQUIRED if not (run / f).exists()]
    out = {
        'repo_root': str(root),
        'latest_run': str(run),
        'missing': missing,
        'ok': len(missing) == 0
    }
    print(json.dumps(out, indent=2))
    if missing:
        raise SystemExit('Root Reflection failed: missing artifacts')

if __name__ == '__main__':
    main()