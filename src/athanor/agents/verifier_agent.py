from __future__ import annotations
from .base import Agent
from ..core.coherence import estimate

class VerifierAgent(Agent):
    def __init__(self, threshold_h7: float = 0.70, dphi_mode: str = ""l2"", refine_floor: float = 0.50):
        self.threshold = float(threshold_h7)
        self.mode = str(dphi_mode)
        self.refine_floor = float(refine_floor)

    def step(self, candidate):
        if candidate.telemetry is None:
            candidate.verdict = ""REJECT""
            candidate.reason  = ""missing telemetry""
            return candidate

        est = estimate(candidate.telemetry.traj, threshold=self.threshold, mode=self.mode)
        candidate.dphi = est

        h7 = float(est.h7)
        if h7 >= self.threshold:
            candidate.verdict = ""APPROVE""
            candidate.reason  = ""H7>=threshold""
            return candidate

        if h7 >= self.refine_floor:
            candidate.verdict = ""REFINE""
            candidate.reason  = ""H7 in refine band""
            return candidate

        candidate.verdict = ""REJECT""
        candidate.reason  = ""H7 below refine floor""
        return candidate