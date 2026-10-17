"""ATHANOR command-line interface.

    athanor run --config CFG [--out-dir DIR] [--tag NAME]
    athanor verify RUN_PATH            # check the hash-chained verdict ledger
    athanor replay RUN_PATH [--out-dir DIR]   # re-run from config.json, compare digests

``athanor --config CFG`` (the original form) is still accepted and equals ``run``.
"""
from __future__ import annotations
import argparse, json, os, sys, tempfile
from typing import List, Optional

from .. import __version__
from ..experiments.registry import load_config, validate_config
from ..evolution.dgm_loop import run as run_loop
from ..ledger import verify_ledger


def _cmd_run(args) -> int:
    cfg = load_config(args.config)
    if args.out_dir:
        cfg['run']['out_dir'] = args.out_dir
    if args.tag:
        cfg['run']['tag'] = args.tag
    cfg = validate_config(cfg)
    out = run_loop(cfg)
    print(json.dumps(out))
    return 0


def _cmd_verify(args) -> int:
    res = verify_ledger(os.path.join(args.run_path, 'ledger.jsonl'))
    print(json.dumps(res.to_dict()))
    return 0 if res.ok else 1


def _cmd_replay(args) -> int:
    run_path = args.run_path
    cfg_path = os.path.join(run_path, 'config.json')
    if not os.path.exists(cfg_path):
        print(json.dumps({'ok': False, 'error': f'missing {cfg_path} (run predates replay support)'}))
        return 2
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    original = verify_ledger(os.path.join(run_path, 'ledger.jsonl'))

    with tempfile.TemporaryDirectory() as tmp:
        cfg.setdefault('run', {})
        cfg['run']['out_dir'] = args.out_dir or tmp
        cfg['run'].pop('tag', None)
        out = run_loop(validate_config(cfg))

    match = original.ok and out['run_digest'] == original.head
    print(json.dumps({
        'ok': bool(match),
        'original_ledger_ok': original.ok,
        'original_digest': original.head,
        'replay_digest': out['run_digest'],
        'rows': out['ledger_rows'],
    }))
    return 0 if match else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog='athanor', description='ATHANOR coherence governor')
    ap.add_argument('--version', action='version', version=f'athanor {__version__}')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('run', help='run a coherence-gated evolution loop')
    p.add_argument('--config', required=True)
    p.add_argument('--out-dir', default=None, help='override run.out_dir')
    p.add_argument('--tag', default=None, help='fixed run folder name (instead of a timestamp)')
    p.set_defaults(fn=_cmd_run)

    p = sub.add_parser('verify', help='verify a run ledger hash chain')
    p.add_argument('run_path')
    p.set_defaults(fn=_cmd_verify)

    p = sub.add_parser('replay', help='deterministically re-run a run and compare digests')
    p.add_argument('run_path')
    p.add_argument('--out-dir', default=None, help='keep replay artifacts here (default: temp dir)')
    p.set_defaults(fn=_cmd_replay)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].startswith('--config'):
        argv = ['run'] + argv  # legacy: `athanor --config X`
    args = build_parser().parse_args(argv)
    return int(args.fn(args))
