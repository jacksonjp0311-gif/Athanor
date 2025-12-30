from __future__ import annotations
import numpy as np
from .types import DeltaPhiEstimate

def delta_phi(traj: np.ndarray, mode: str = ""l2"") -> np.ndarray:
    if traj.ndim != 2 or traj.shape[0] < 2:
        return np.zeros((0,), dtype=np.float32)

    a = traj[:-1].astype(np.float32)
    b = traj[1:].astype(np.float32)

    if mode == ""cosine"":
        na = np.linalg.norm(a, axis=1) + 1e-9
        nb = np.linalg.norm(b, axis=1) + 1e-9
        cos = (a * b).sum(axis=1) / (na * nb)
        cos = np.clip(cos, -1.0, 1.0)
        return np.arccos(cos).astype(np.float32)

    return np.linalg.norm(b - a, axis=1).astype(np.float32)

def coherence_from_dphi(dphi: np.ndarray) -> np.ndarray:
    return (1.0 / (1.0 + np.abs(dphi))).astype(np.float32)

def h7_horizon(C: np.ndarray, threshold: float = 0.70) -> float:
    if C.size == 0:
        return 0.0
    return float(np.mean(C >= float(threshold)))

def estimate(traj: np.ndarray, threshold: float = 0.70, mode: str = ""l2"") -> DeltaPhiEstimate:
    d = delta_phi(traj, mode=mode)
    C = coherence_from_dphi(d)
    h7 = h7_horizon(C, threshold=threshold)
    summary = {
        ""threshold"": float(threshold),
        ""mode"": str(mode),
        ""dphi_mean"": float(d.mean()) if d.size else 0.0,
        ""dphi_std"": float(d.std()) if d.size else 0.0,
        ""C_mean"": float(C.mean()) if C.size else 0.0,
        ""C_std"": float(C.std()) if C.size else 0.0,
        ""h7"": float(h7),
    }
    return DeltaPhiEstimate(dphi=d, coherence=C, h7=h7, summary=summary)