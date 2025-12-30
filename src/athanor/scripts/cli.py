from __future__ import annotations
import argparse, json
from ..experiments.registry import load_config
from ..evolution.dgm_loop import run as run_loop

def main():
    ap = argparse.ArgumentParser(prog='athanor')
    ap.add_argument('--config', required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)
    out = run_loop(cfg)
    print(json.dumps(out))
    return 0