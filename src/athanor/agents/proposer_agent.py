from __future__ import annotations
import numpy as np
from .base import Agent
from ..adapters import GaussianNoiseAdapter, ProposerAdapter

class ProposerAgent(Agent):
    def __init__(
        self,
        sigma: float = 0.12,
        step_cap: float = 0.50,
        adapter: ProposerAdapter | None = None,
    ):
        self.adapter = adapter or GaussianNoiseAdapter(sigma=sigma, step_cap=step_cap)
        self._sigma = float(sigma)
        self._step_cap = float(step_cap)

    @property
    def sigma(self) -> float:
        if hasattr(self.adapter, "sigma"):
            return float(getattr(self.adapter, "sigma"))
        return self._sigma

    @sigma.setter
    def sigma(self, value: float) -> None:
        if hasattr(self.adapter, "sigma"):
            setattr(self.adapter, "sigma", float(value))
        self._sigma = float(value)

    @property
    def step_cap(self) -> float:
        if hasattr(self.adapter, "step_cap"):
            return float(getattr(self.adapter, "step_cap"))
        return self._step_cap

    @step_cap.setter
    def step_cap(self, value: float) -> None:
        if hasattr(self.adapter, "step_cap"):
            setattr(self.adapter, "step_cap", float(value))
        self._step_cap = float(value)

    def step(self, parent, rng: np.random.Generator, child_id: str):
        return self.adapter.propose(parent=parent, rng=rng, child_id=child_id)
