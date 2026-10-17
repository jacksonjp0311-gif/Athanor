from __future__ import annotations
import os, json, pickle, hashlib, logging
from typing import Dict, Any
from datetime import datetime, timezone
import numpy as np

from ..core.types import Candidate
from ..agents import TelemetryAgent, ProposerAgent, VerifierAgent, SelectorAgent, ArchivistAgent
from ..ledger import LedgerWriter, canonical_json
from ..utils.visualization import plot_h7, plot_fitness, render_dashboard

log = logging.getLogger(__name__)

def now_tag():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')

def sha256_json(obj: Any) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(',',':')).encode('utf-8')
    return hashlib.sha256(s).hexdigest()

def derive_seed(*parts: int) -> int:
    """Derive a collision-free 32-bit seed from integer parts (deterministic)."""
    ss = np.random.SeedSequence([int(p) for p in parts])
    return int(ss.generate_state(1, dtype=np.uint32)[0])

def _make_run_path(out_dir: str, tag: str | None) -> str:
    os.makedirs(out_dir, exist_ok=True)
    if tag:
        path = os.path.join(out_dir, tag)
        if os.path.exists(os.path.join(path, 'ledger.jsonl')):
            raise FileExistsError(f'run folder already contains a ledger: {path}')
        os.makedirs(path, exist_ok=True)
        return path
    base = os.path.join(out_dir, f'run_{now_tag()}')
    path, n = base, 1
    while True:
        try:
            os.makedirs(path)
            return path
        except FileExistsError:
            path = f'{base}_{n:02d}'
            n += 1

def run(config: Dict[str, Any]) -> Dict[str, Any]:
    seed = int(config.get('seed', 1337))
    rng  = np.random.default_rng(seed)

    threshold = float(config.get('threshold_h7', 0.70))
    alpha     = float(config.get('alpha', 0.70))
    steps     = int(config.get('steps_per_candidate', 24))
    pop       = int(config.get('population', 16))
    gens      = int(config.get('generations', 24))
    refine_attempts = int(config.get('refine_attempts', 2))
    # governor.enabled=false is the ungoverned baseline: verdicts are still measured and
    # ledgered, but they do not trigger REFINE retries or block parent promotion.
    governed = bool((config.get('governor', {}) or {}).get('enabled', True))
    if not governed:
        refine_attempts = 0
    dphi_mode = str(config.get('dphi_mode', 'l2'))

    bins = tuple(config.get('archive', {}).get('bins', [16,16]))
    out_dir = str(config.get('run', {}).get('out_dir', 'data/archives'))
    run_tag = config.get('run', {}).get('tag')
    refine_floor = float(config.get('refine_floor', 0.50))

    telemetry = TelemetryAgent(steps=steps, noise=float(config.get('telemetry_noise', 0.02)), seed=seed)
    proposer  = ProposerAgent(sigma=float(config.get('proposer_sigma', 0.12)),
                              step_cap=float(config.get('proposer_step_cap', 0.50)))
    gates_cfg = config.get('gates', {}) or {}
    verifier  = VerifierAgent(threshold_h7=threshold, dphi_mode=dphi_mode, refine_floor=refine_floor,
                              h20=gates_cfg.get('h20'), h44=gates_cfg.get('h44'))
    selector  = SelectorAgent(alpha=alpha)
    archivist = ArchivistAgent(bins=bins)

    D = int(config.get('genome_dim', 64))
    parent = Candidate(id='parent_0000', genome=rng.normal(0.0, 0.5, size=(D,)).astype(np.float32))

    verdict_counts = { 'APPROVE': 0, 'REFINE': 0, 'REJECT': 0 }
    h7_trace = []
    f_trace  = []

    run_path = _make_run_path(out_dir, run_tag)

    # Persist the fully-resolved config so the run can be replayed exactly.
    with open(os.path.join(run_path, 'config.json'), 'w', encoding='utf-8') as f:
        f.write(canonical_json(config) + '\n')

    ledger_path = os.path.join(run_path, 'ledger.jsonl')
    writer = LedgerWriter(ledger_path)
    ledger = writer.append

    lineage = []  # per-generation parent decisions (the decision record)

    def evaluate(cid: str, g: int, i: int, attempt: int):
        # Each (gen, idx, attempt) owns independent proposal / telemetry / gate streams,
        # so a candidate's outcome never depends on how many REFINE retries others used.
        prng = np.random.default_rng(derive_seed(seed, 1, g, i, attempt))
        c = proposer.step(parent, rng=prng, child_id=cid)
        telemetry.seed = derive_seed(seed, g, i, attempt)
        c = telemetry.step(c)
        return verifier.step(c, gate_seed=derive_seed(seed, 2, g, i, attempt))

    def attempt_row(c, attempt: int, sigma: float):
        return {'attempt': attempt, 'id': c.id, 'sigma': float(sigma), 'verdict': c.verdict,
                'reason': c.reason, 'h7': float(c.dphi.h7) if c.dphi else 0.0}

    for g in range(gens):
        best = None
        parent_before = parent.id
        gen_rows = []

        for i in range(pop):
            cid = f'g{g:03d}_c{i:03d}'
            sigma0 = proposer.sigma
            child = evaluate(cid, g, i, 0)
            trail = [attempt_row(child, 0, sigma0)]

            # Deterministic REFINE path: shrink sigma geometrically (0.75^k) and retry.
            attempts = 0
            while attempts < refine_attempts and child.verdict == 'REFINE':
                attempts += 1
                proposer.sigma = sigma0 * (0.75 ** attempts)
                child = evaluate(f'{cid}_r{attempts}', g, i, attempts)
                trail.append(attempt_row(child, attempts, proposer.sigma))
            proposer.sigma = sigma0

            child = selector.step(child)
            admitted = archivist.step(child)

            verdict_counts[child.verdict] = verdict_counts.get(child.verdict, 0) + 1
            h7 = float(child.dphi.h7) if child.dphi else 0.0
            h7_trace.append(h7)
            f_trace.append(float(child.score_f))

            ledger({
                'gen': g,
                'idx': i,
                'id': child.id,
                'verdict': child.verdict,
                'reason': child.reason,
                'h7': h7,
                'h7_weighted': float(child.dphi.summary.get('h7_weighted', 0.0)) if child.dphi else 0.0,
                'h7_cusp': float(child.dphi.summary.get('h7_cusp', 0.0)) if child.dphi else 0.0,
                'kappa_bound': float(child.dphi.summary.get('kappa_bound', 0.0)) if child.dphi else 0.0,
                'q': float(child.score_q),
                'f': float(child.score_f),
                'admitted': bool(admitted),
                'dphi_mean': float(child.dphi.summary.get('dphi_mean', 0.0)) if child.dphi else 0.0,
                'C_mean': float(child.dphi.summary.get('C_mean', 0.0)) if child.dphi else 0.0,
                'delta_norm': float(child.tags.get('delta_norm', 0.0)),
                'parent_id': parent.id,
                'checks': child.tags.get('checks', []),
                'refine_trail': trail,
            })

            gen_rows.append((h7, float(child.dphi.summary.get('dphi_mean', 0.0)) if child.dphi else 0.0,
                             float(child.dphi.summary.get('C_mean', 0.0)) if child.dphi else 0.0))

            if (best is None) or (child.score_f > best.score_f):
                best = child

        if best is None:
            why = 'empty generation'
        elif not governed:
            parent = best
            why = f'ungoverned: best-fitness candidate promoted ({best.verdict})'
        elif best.verdict == 'APPROVE':
            parent = best
            why = 'best-fitness candidate was APPROVED'
        else:
            why = f'best-fitness candidate was {best.verdict}; parent kept'
        lineage.append({
            'gen': g, 'parent_before': parent_before, 'parent_after': parent.id,
            'promoted': parent.id != parent_before,
            'best_id': best.id if best else None,
            'best_verdict': best.verdict if best else None,
            'best_f': float(best.score_f) if best else None,
            'reason': why,
            'pop_h7_mean': float(np.mean([r[0] for r in gen_rows])) if gen_rows else 0.0,
            'pop_dphi_mean': float(np.mean([r[1] for r in gen_rows])) if gen_rows else 0.0,
            'pop_C_mean': float(np.mean([r[2] for r in gen_rows])) if gen_rows else 0.0,
            'parent_h7': float(parent.dphi.h7) if parent.dphi else None,
            'parent_dphi_mean': float(parent.dphi.summary.get('dphi_mean', 0.0)) if parent.dphi else None,
            'parent_C_mean': float(parent.dphi.summary.get('C_mean', 0.0)) if parent.dphi else None,
        })

    archive_pkl = os.path.join(run_path, 'archive.pkl')
    with open(archive_pkl, 'wb') as f:
        pickle.dump(archivist.archive, f)

    with open(os.path.join(run_path, 'archive.json'), 'w', encoding='utf-8') as f:
        json.dump(archivist.archive.to_dict(), f, indent=2, sort_keys=True)

    stats = archivist.archive.stats()
    stats.update({
        'threshold_h7': threshold,
        'alpha': alpha,
        'verdict_counts': verdict_counts,
        'mean_H7': float(np.mean(h7_trace)) if h7_trace else 0.0,
        'mean_F':  float(np.mean(f_trace)) if f_trace else 0.0,
    })

    with open(os.path.join(run_path, 'archive_stats.json'), 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)

    record = {
        'schema': 'athanor.decision_record/1',
        'run_digest': writer.head,
        'governed': governed,
        'gates': {'H7': {'threshold': threshold, 'refine_floor': refine_floor},
                  'H20': gates_cfg.get('h20', {'enabled': False}),
                  'H44': gates_cfg.get('h44', {'enabled': False})},
        'verdict_counts': verdict_counts,
        'promotions': sum(1 for x in lineage if x['promoted']),
        'final_parent': parent.id,
        'lineage': lineage,
    }
    with open(os.path.join(run_path, 'decision_record.json'), 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2)

    cfg_hash = sha256_json(config)
    git_hash = os.environ.get('ATHANOR_GIT_HASH', '')

    meta = {
        'timestamp_utc': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'seed': seed,
        'config_hash': cfg_hash,
        'git_commit': git_hash,
        'ledger_rows': writer.count,
        'run_digest': writer.head,
    }
    with open(os.path.join(run_path, 'metadata.yaml'), 'w', encoding='utf-8') as f:
        for k,v in meta.items():
            f.write(f'{k}: {v}\n')

    try:
        plot_h7(ledger_path, os.path.join(run_path, 'h7_trace.png'), h7_threshold=threshold)
        plot_fitness(ledger_path, os.path.join(run_path, 'fitness_trace.png'))
        render_dashboard(run_path, threshold_h7=threshold)
    except Exception as exc:
        log.warning("artifact generation failed: %s", exc)

    return {
        'run_path': run_path,
        'stats': stats,
        'config_hash': cfg_hash,
        'run_digest': writer.head,
        'ledger_rows': writer.count,
    }
