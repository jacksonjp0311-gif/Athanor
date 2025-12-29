import argparse
from pathlib import Path
from athanor.utils.visualization import plot_h7

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True, help='path to data/archives/run_*')
    args = ap.parse_args()
    run = Path(args.run)
    ledger = run / 'ledger.jsonl'
    out = run / 'h7_trace.png'
    plot_h7(str(ledger), str(out))
    print(str(out))
