from __future__ import annotations
import os
import yaml


def validate_config(cfg: dict) -> dict:
    out = dict(cfg or {})

    def bounded01(key: str, default: float):
        v = float(out.get(key, default))
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"{key} must be in [0,1], got {v}")
        out[key] = v

    def positive_int(key: str, default: int, min_value: int = 1):
        v = int(out.get(key, default))
        if v < min_value:
            raise ValueError(f"{key} must be >= {min_value}, got {v}")
        out[key] = v

    bounded01('threshold_h7', 0.70)
    bounded01('alpha', 0.70)
    positive_int('steps_per_candidate', 24)
    positive_int('population', 16)
    positive_int('generations', 24)
    positive_int('refine_attempts', 2, min_value=0)
    positive_int('genome_dim', 64)

    bounded01('refine_floor', 0.50)
    if out['refine_floor'] > out['threshold_h7']:
        raise ValueError(
            f"refine_floor must be <= threshold_h7, got {out['refine_floor']} > {out['threshold_h7']}"
        )

    def non_negative(key: str, default: float):
        v = float(out.get(key, default))
        if not (v >= 0.0):
            raise ValueError(f"{key} must be >= 0, got {v}")
        out[key] = v

    non_negative('telemetry_noise', 0.02)
    non_negative('proposer_sigma', 0.12)
    non_negative('proposer_step_cap', 0.50)
    out['seed'] = int(out.get('seed', 1337))

    mode = str(out.get('dphi_mode', 'l2')).strip().lower()
    if mode not in {'l2', 'cosine'}:
        raise ValueError(f"dphi_mode must be 'l2' or 'cosine', got {mode}")
    out['dphi_mode'] = mode

    archive = dict(out.get('archive', {}) or {})
    bins = archive.get('bins', [16, 16])
    if not isinstance(bins, (list, tuple)) or len(bins) != 2:
        raise ValueError("archive.bins must be a list or tuple of length 2")
    bins = tuple(int(b) for b in bins)
    if any(b < 1 for b in bins):
        raise ValueError("archive.bins entries must be >= 1")
    archive['bins'] = list(bins)
    out['archive'] = archive

    run = dict(out.get('run', {}) or {})
    out_dir = str(run.get('out_dir', 'data/archives')).strip()
    if not out_dir:
        raise ValueError("run.out_dir must be a non-empty string")
    run['out_dir'] = out_dir

    tag = run.get('tag')
    if tag is not None:
        tag = str(tag).strip()
        if not tag or any(c in tag for c in '/\\') or tag in {'.', '..'}:
            raise ValueError("run.tag must be a plain, non-empty folder name")
        run['tag'] = tag
    out['run'] = run

    return out


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` into a copy of ``base`` (override wins)."""
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_raw(path: str, _seen: tuple = ()) -> dict:
    real = os.path.realpath(path)
    if real in _seen:
        raise ValueError(f"config inheritance cycle: {' -> '.join(_seen + (real,))}")
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}
    if not isinstance(cfg, dict):
        raise ValueError(f"config {path} must be a mapping")
    inh = cfg.pop('inherits', None)
    if inh:
        base = _load_raw(os.path.join(os.path.dirname(path), inh), _seen + (real,))
        cfg = deep_merge(base, cfg)
    return cfg


def load_config(path: str) -> dict:
    return validate_config(_load_raw(path))
