from __future__ import annotations
from .base import Agent

class SelectorAgent(Agent):
    def __init__(self, alpha: float = 0.70):
        self.alpha = float(alpha)

    def step(self, candidate):
        dn = float(candidate.tags.get(""delta_norm"", 0.0))
        q  = 1.0 / (1.0 + dn)
        h7 = float(candidate.dphi.h7) if candidate.dphi else 0.0

        candidate.score_q = float(q)
        candidate.score_f = float((self.alpha * q) + ((1.0 - self.alpha) * h7))
        return candidate