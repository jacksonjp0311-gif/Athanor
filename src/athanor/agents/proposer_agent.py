from __future__ import annotations
import numpy as np
from .base import Agent

class ProposerAgent(Agent):
    def __init__(self, sigma: float = 0.12, step_cap: float = 0.50):
        self.sigma = float(sigma)
        self.step_cap = float(step_cap)

    def step(self, parent, rng: np.random.Generator, child_id: str):
        g = parent.genome.astype(np.float32)
        delta = rng.normal(0.0, self.sigma, size=g.shape).astype(np.float32)
        n = float(np.linalg.norm(delta) + 1e-9)
        if n > self.step_cap:
            delta *= (self.step_cap / n)
        child = type(parent)(id=child_id, genome=(g + delta))
        child.tags[""delta_norm""] = float(np.linalg.norm(delta))
        return child
