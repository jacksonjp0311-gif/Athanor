import argparse, json
from pathlib import Path

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True, help='path to data/archives/run_*')
    args = ap.parse_args()
    run = Path(args.run)
    stats = run / 'archive_stats.json'
    if not stats.exists():
        raise SystemExit('archive_stats.json not found')
    obj = json.loads(stats.read_text(encoding='utf-8'))
    print(json.dumps(obj, indent=2))
