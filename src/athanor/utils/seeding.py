from __future__ import annotations
import numpy as np
def make_rng(seed: int):
    return np.random.default_rng(int(seed))
