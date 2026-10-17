"""ATHANOR command-line interface.

    athanor run --config CFG [--out-dir DIR] [--tag NAME]
    athanor verify RUN_PATH            # check the hash-chained verdict ledger
    athanor replay RUN_PATH [--out-dir DIR]   # re-run from config.json, compare digests
    athanor diff RUN_A RUN_B           # compare two runs (digest, first divergence, stats)
    athanor bench [--config CFG] [--seeds 0-7] [--out DIR]   # governed vs ungoverned
    athanor selfmod [--seeds 0-15] [--steps 1000] [--out DIR]  # real self-modifying program
    athanor evals {list,capture,run}      # Bug2Eval regression suite (pip install "athanor[evals]")
    athanor registry {list,show,lineage,register,promote,verify}  # versioned configs, eval-gated promotion
    athanor search {index,status,find,grep,read,verify,cite}  # AgentSearch evidence (pip install "athanor[search]")

``athanor --config CFG`` (the original form) is still accepted and equals ``run``.
"""
from __future__ import annotations
import argparse, json, os, sys, tempfile
from typing import List, Optional

from .. import __version__
from ..experiments.registry import load_config, validate_config
from ..evolution.dgm_loop import run as run_loop
from ..ledger import verify_ledger, read_ledger


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


def _load_json(path, default=None):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def diff_runs(a: str, b: str) -> dict:
    la = read_ledger(os.path.join(a, 'ledger.jsonl'))
    lb = read_ledger(os.path.join(b, 'ledger.jsonl'))
    first = None
    for i in range(max(len(la), len(lb))):
        ha = la[i].get('row_hash') if i < len(la) else None
        hb = lb[i].get('row_hash') if i < len(lb) else None
        if ha != hb:
            first = i
            break
    digest_a = la[-1]['row_hash'] if la else None
    digest_b = lb[-1]['row_hash'] if lb else None
    sa = _load_json(os.path.join(a, 'archive_stats.json'), {}) or {}
    sb = _load_json(os.path.join(b, 'archive_stats.json'), {}) or {}
    ra = _load_json(os.path.join(a, 'decision_record.json'), {}) or {}
    rb = _load_json(os.path.join(b, 'decision_record.json'), {}) or {}
    ca = _load_json(os.path.join(a, 'config.json'), {}) or {}
    cb = _load_json(os.path.join(b, 'config.json'), {}) or {}
    cfg_changed = sorted(k for k in set(ca) | set(cb) if k != 'run' and ca.get(k) != cb.get(k))
    numeric = {}
    for k in ('mean_H7', 'mean_F', 'filled', 'max_best_f'):
        if k in sa or k in sb:
            va, vb = float(sa.get(k, 0.0)), float(sb.get(k, 0.0))
            numeric[k] = {'a': va, 'b': vb, 'delta': vb - va}
    return {
        'identical': digest_a == digest_b and len(la) == len(lb),
        'digest_a': digest_a, 'digest_b': digest_b,
        'rows_a': len(la), 'rows_b': len(lb),
        'first_divergent_seq': first,
        'config_keys_changed': cfg_changed,
        'verdict_counts': {'a': sa.get('verdict_counts'), 'b': sb.get('verdict_counts')},
        'promotions': {'a': ra.get('promotions'), 'b': rb.get('promotions')},
        'stats': numeric,
    }


def _cmd_diff(args) -> int:
    out = diff_runs(args.run_a, args.run_b)
    print(json.dumps(out))
    return 0 if out['identical'] else 1


def _parse_seeds(text: str) -> List[int]:
    seeds: List[int] = []
    for part in str(text).split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            seeds.extend(range(int(a), int(b) + 1))
        elif part:
            seeds.append(int(part))
    if not seeds:
        raise ValueError('no seeds given')
    return seeds


def _cmd_bench(args) -> int:
    from ..bench import run_bench, render_markdown, render_chart, default_bench_config
    cfg = load_config(args.config) if args.config else default_bench_config()
    res = run_bench(cfg, _parse_seeds(args.seeds))
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=2)
    with open(os.path.join(args.out, 'results.md'), 'w', encoding='utf-8') as f:
        f.write(render_markdown(res))
    chart = args.chart or os.path.join(args.out, 'benchmark.png')
    render_chart(res, chart)
    print(json.dumps({'out': args.out, 'chart': chart, 'summary': res['summary'], 'per_seed': res['per_seed']}))
    return 0


def _cmd_selfmod(args) -> int:
    from ..selfmod import run_selfmod_bench, render_markdown as md, render_chart as chart_fn
    from ..selfmod.experiment import compact
    res = run_selfmod_bench(_parse_seeds(args.seeds), {"steps": int(args.steps)},
                            ledger_dir=os.path.join(args.out, 'ledgers') if args.ledgers else None)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, 'results.json'), 'w', encoding='utf-8') as f:
        json.dump(res if args.full_json else compact(res), f, indent=1)
    with open(os.path.join(args.out, 'results.md'), 'w', encoding='utf-8') as f:
        f.write(md(res))
    chart = args.chart or os.path.join(args.out, 'selfmod.png')
    chart_fn(res, chart)
    print(json.dumps({'out': args.out, 'chart': chart, 'summary': res['summary'], 'per_seed': res['per_seed']}))
    return 0


def _cmd_selfmod_arms(args) -> int:
    from ..selfmod.evaluate import evaluate_all, compact_arms
    from ..selfmod.arms import arms_markdown, arms_chart
    res = evaluate_all(_parse_seeds(args.seeds), steps=int(args.steps))
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, 'arms_results.json'), 'w', encoding='utf-8') as f:
        json.dump(compact_arms(res), f, indent=1)
    with open(os.path.join(args.out, 'arms_results.md'), 'w', encoding='utf-8') as f:
        f.write(arms_markdown(res))
    chart = args.chart or os.path.join(args.out, 'selfmod_arms.png')
    arms_chart(res, chart)
    print(json.dumps({'out': args.out, 'chart': chart, 'summary': res['summary']}))
    return 0


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
    p = sub.add_parser('bench', help='compare governed vs ungoverned runs across seeds')
    p.add_argument('--config', default=None, help='default: built-in copy of configs/bench.yaml')
    p.add_argument('--seeds', default='0-7', help="e.g. '0-7' or '1,3,5'")
    p.add_argument('--out', default='data/bench')
    p.add_argument('--chart', default=None, help='chart path (default: OUT/benchmark.png)')
    p.set_defaults(fn=_cmd_bench)

    p = sub.add_parser('selfmod', help='governed vs ungoverned real self-modifying program')
    p.add_argument('--seeds', default='0-15')
    p.add_argument('--steps', type=int, default=1000)
    p.add_argument('--out', default='data/selfmod')
    p.add_argument('--chart', default=None, help='chart path (default: OUT/selfmod.png)')
    p.add_argument('--full-json', action='store_true', help='include per-step series in results.json')
    p.add_argument('--ledgers', action='store_true', help='also write a hash-chained ledger + final_self.py per run')
    p.set_defaults(fn=_cmd_selfmod)

    p = sub.add_parser('selfmod-arms', help='held-out comparison of all arms incl. validity gate and tuned adaptive schedule')
    p.add_argument('--seeds', default='0-15')
    p.add_argument('--steps', type=int, default=1000)
    p.add_argument('--out', default='data/selfmod')
    p.add_argument('--chart', default=None)
    p.set_defaults(fn=_cmd_selfmod_arms)

    p = sub.add_parser('diff', help='compare two runs (exit 0 if identical)')
    p.add_argument('run_a')
    p.add_argument('run_b')
    p.set_defaults(fn=_cmd_diff)

    from .evals_cli import add_parsers as _add_eval_parsers
    _add_eval_parsers(sub)
    from .search_cli import add_parsers as _add_search_parsers
    _add_search_parsers(sub)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].startswith('--config'):
        argv = ['run'] + argv  # legacy: `athanor --config X`
    args = build_parser().parse_args(argv)
    return int(args.fn(args))
