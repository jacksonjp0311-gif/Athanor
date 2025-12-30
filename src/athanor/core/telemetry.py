from __future__ import annotations
import numpy as np
from .types import TelemetryBatch

def capture_trajectory(genome: np.ndarray, steps: int = 24, noise: float = 0.02, seed: int = 0) -> TelemetryBatch:
    rng = np.random.default_rng(int(seed))
    D = int(genome.size)
    A = np.eye(D, dtype=np.float32) + 0.05 * np.tanh(genome.astype(np.float32))
    x = np.zeros((int(steps), D), dtype=np.float32)
    s = rng.normal(0.0, 0.1, size=(D,)).astype(np.float32)

    for t in range(int(steps)):
        x[t] = s
        s = (A @ s) + rng.normal(0.0, float(noise), size=(D,)).astype(np.float32)

    meta = {""steps"": int(steps), ""noise"": float(noise), ""D"": int(D)}
    return TelemetryBatch(traj=x, meta=meta)