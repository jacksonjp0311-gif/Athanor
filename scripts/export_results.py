import argparse, json, csv
from pathlib import Path

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    args = ap.parse_args()
    run = Path(args.run)
    ledger = run / 'ledger.jsonl'
    out = run / 'ledger.csv'
    rows = []
    for line in ledger.read_text(encoding='utf-8').splitlines():
        if line.strip():
            rows.append(json.loads(line))
    if not rows:
        raise SystemExit('empty ledger')
    keys = sorted(rows[0].keys())
    with out.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in keys})
    print(str(out))
