from __future__ import annotations
import os
import yaml

def load_config(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}
    inh = cfg.get('inherits')
    if inh:
        base_path = os.path.join(os.path.dirname(path), inh)
        base = load_config(base_path)
        base.update(cfg)
        return base
    return cfg
