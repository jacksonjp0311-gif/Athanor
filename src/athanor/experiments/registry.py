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

    mode = str(out.get('dphi_mode', 'l2')).strip().lower()
    if mode not in {'l2', 'cosine'}:
        raise ValueError(f"dphi_mode must be 'l2' or 'cosine', got {mode}")
    out['dphi_mode'] = mode

    return out


def load_config(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}
    inh = cfg.get('inherits')
    if inh:
        base_path = os.path.join(os.path.dirname(path), inh)
        base = load_config(base_path)
        base.update(cfg)
        cfg = base
    return validate_config(cfg)
