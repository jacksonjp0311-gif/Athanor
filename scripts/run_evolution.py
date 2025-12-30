import argparse, json
from athanor.experiments.registry import load_config
from athanor.evolution.dgm_loop import run

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)
    out = run(cfg)
    print(json.dumps(out, indent=2))