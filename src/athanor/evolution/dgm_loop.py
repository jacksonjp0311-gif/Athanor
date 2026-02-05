from __future__ import annotations
import os, json, pickle, hashlib, logging
from typing import Dict, Any
from datetime import datetime, timezone
import numpy as np

from ..core.types import Candidate
from ..agents import TelemetryAgent, ProposerAgent, VerifierAgent, SelectorAgent, ArchivistAgent
from ..utils.visualization import plot_h7, plot_fitness, render_dashboard

log = logging.getLogger(__name__)

def now_tag():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')

def sha256_json(obj: Any) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(',',':')).encode('utf-8')
    return hashlib.sha256(s).hexdigest()

def run(config: Dict[str, Any]) -> Dict[str, Any]:
    seed = int(config.get('seed', 1337))
    rng  = np.random.default_rng(seed)

    threshold = float(config.get('threshold_h7', 0.70))
    alpha     = float(config.get('alpha', 0.70))
    steps     = int(config.get('steps_per_candidate', 24))
    pop       = int(config.get('population', 16))
    gens      = int(config.get('generations', 24))
    refine_attempts = int(config.get('refine_attempts', 2))
    dphi_mode = str(config.get('dphi_mode', 'l2'))

    bins = tuple(config.get('archive', {}).get('bins', [16,16]))
    out_dir = str(config.get('run', {}).get('out_dir', 'data/archives'))

    telemetry = TelemetryAgent(steps=steps, noise=0.02, seed=seed)
    proposer  = ProposerAgent(sigma=0.12, step_cap=0.50)
    verifier  = VerifierAgent(threshold_h7=threshold, dphi_mode=dphi_mode, refine_floor=0.50)
    selector  = SelectorAgent(alpha=alpha)
    archivist = ArchivistAgent(bins=bins)

    D = int(config.get('genome_dim', 64))
    parent = Candidate(id='parent_0000', genome=rng.normal(0.0, 0.5, size=(D,)).astype(np.float32))

    verdict_counts = { 'APPROVE': 0, 'REFINE': 0, 'REJECT': 0 }
    h7_trace = []
    f_trace  = []

    run_tag  = f'run_{now_tag()}'
    run_path = os.path.join(out_dir, run_tag)
    os.makedirs(run_path, exist_ok=True)

    ledger_path = os.path.join(run_path, 'ledger.jsonl')

    def ledger(row: Dict[str, Any]):
        with open(ledger_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(row) + '\n')

    for g in range(gens):
        best = None

        for i in range(pop):
            cid = f'g{g:03d}_c{i:03d}'
            child = proposer.step(parent, rng=rng, child_id=cid)

            telemetry.seed = seed + (g * 10000) + i
            child = telemetry.step(child)
            child = verifier.step(child)

            if child.verdict == 'REFINE':
                attempts = 0
                sigma0 = proposer.sigma
                while attempts < refine_attempts and child.verdict == 'REFINE':
                    attempts += 1
                    proposer.sigma = sigma0 * (0.75 ** attempts)
                    child2 = proposer.step(parent, rng=rng, child_id=f'{cid}_r{attempts}')
                    telemetry.seed = seed + (g * 10000) + i + attempts
                    child2 = telemetry.step(child2)
                    child2 = verifier.step(child2)
                    child = child2
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
                'q': float(child.score_q),
                'f': float(child.score_f),
                'admitted': bool(admitted),
                'dphi_mean': float(child.dphi.summary.get('dphi_mean', 0.0)) if child.dphi else 0.0,
                'C_mean': float(child.dphi.summary.get('C_mean', 0.0)) if child.dphi else 0.0,
                'delta_norm': float(child.tags.get('delta_norm', 0.0)),
            })

            if (best is None) or (child.score_f > best.score_f):
                best = child

        if best is not None and best.verdict == 'APPROVE':
            parent = best

    archive_pkl = os.path.join(run_path, 'archive.pkl')
    with open(archive_pkl, 'wb') as f:
        pickle.dump(archivist.archive, f)

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

    cfg_hash = sha256_json(config)
    git_hash = os.environ.get('ATHANOR_GIT_HASH', '')

    meta = {
        'timestamp_utc': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'seed': seed,
        'config_hash': cfg_hash,
        'git_commit': git_hash,
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

    return { 'run_path': run_path, 'stats': stats, 'config_hash': cfg_hash }
