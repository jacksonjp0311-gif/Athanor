from __future__ import annotations
from .base import Agent
from ..core.telemetry import capture_trajectory

class TelemetryAgent(Agent):
    def __init__(self, steps: int, noise: float, seed: int):
        self.steps = int(steps)
        self.noise = float(noise)
        self.seed  = int(seed)

    def step(self, candidate):
        candidate.telemetry = capture_trajectory(candidate.genome, steps=self.steps, noise=self.noise, seed=self.seed)
        return candidate