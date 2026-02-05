from __future__ import annotations
import numpy as np
from .types import DeltaPhiEstimate

def delta_phi(traj: np.ndarray, mode: str = "l2") -> np.ndarray:
    if traj.ndim != 2 or traj.shape[0] < 2:
        return np.zeros((0,), dtype=np.float32)

    a = traj[:-1].astype(np.float32)
    b = traj[1:].astype(np.float32)

    if mode == "cosine":
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

def weighted_coherence_mean(C: np.ndarray, power: float = 1.0) -> float:
    if C.size == 0:
        return 0.0
    p = max(float(power), 0.0)
    w = np.power(np.clip(C.astype(np.float32), 0.0, 1.0), p)
    den = float(w.sum())
    if den <= 1e-12:
        return float(C.mean())
    return float((w * C).sum() / den)

def cusp_limited_h7(C: np.ndarray, threshold: float = 0.70, survival_floor: float = 0.0) -> float:
    if C.size == 0:
        return 0.0
    sf = float(np.clip(survival_floor, 0.0, 1.0))
    kept = C[C >= sf]
    if kept.size == 0:
        return 0.0
    return h7_horizon(kept, threshold=threshold)


def omega_lipschitz_kappa_bound(C0: float) -> float:
    c0 = float(np.clip(C0, 0.0, 1.0))
    return float(c0 ** 2)

def immunity_index(C: np.ndarray, C_perturbed: np.ndarray) -> float:
    if C.size == 0 or C_perturbed.size == 0:
        return 0.0
    n = min(C.size, C_perturbed.size)
    base = C[:n].astype(np.float32)
    pert = C_perturbed[:n].astype(np.float32)
    num = float(np.mean(np.abs(pert - base)))
    den = float(np.mean(np.abs(base))) + 1e-9
    return float(np.clip(1.0 - (num / den), 0.0, 1.0))

def basin_drift(C: np.ndarray, C_perturbed: np.ndarray) -> float:
    if C.size == 0 or C_perturbed.size == 0:
        return 0.0
    n = min(C.size, C_perturbed.size)
    return float(np.mean(C_perturbed[:n] - C[:n]))

def inject_bounded_noise(dphi: np.ndarray, sigma: float, rng: np.random.Generator | None = None) -> np.ndarray:
    if dphi.size == 0:
        return np.zeros((0,), dtype=np.float32)
    s = max(float(sigma), 0.0)
    if rng is None:
        rng = np.random.default_rng(0)
    eps = rng.uniform(-s, s, size=dphi.shape).astype(np.float32)
    return (dphi.astype(np.float32) + eps).astype(np.float32)


def boundary_excess(value: float, boundary: float) -> float:
    return float(value - boundary)

def commensurability_suppression_score(value: float, max_denominator: int = 64) -> float:
    """Higher means harder to approximate with low-denominator rationals."""
    v = float(value)
    m = max(int(max_denominator), 2)
    best = float('inf')
    for q in range(1, m + 1):
        p = round(v * q)
        err = abs(v - (p / q))
        if err < best:
            best = err
    return float(best)

def select_boundary_invariant(
    candidates: list[float],
    degree: int = 2,
    suppression_weight: float = 1.0,
) -> dict:
    """H44-style selector: choose extremal candidate by degree prior + suppression."""
    if not candidates:
        return {"selected": None, "score": 0.0, "degree": int(degree)}

    deg = max(int(degree), 1)
    sw = max(float(suppression_weight), 0.0)

    # degree priors: canonical representatives for minimal collapse classes
    phi = (1.0 + np.sqrt(5.0)) / 2.0
    plastic = 1.3247179572447458
    target = {1: 1.0, 2: phi, 3: plastic}.get(deg, phi)

    best_val = None
    best_score = -1e18
    for x in candidates:
        xv = float(x)
        prox = -abs(xv - target)
        sup = commensurability_suppression_score(xv)
        score = prox + (sw * sup)
        if score > best_score:
            best_score = score
            best_val = xv

    return {"selected": best_val, "score": float(best_score), "degree": deg, "target": float(target)}

def estimate(traj: np.ndarray, threshold: float = 0.70, mode: str = "l2") -> DeltaPhiEstimate:
    d = delta_phi(traj, mode=mode)
    C = coherence_from_dphi(d)
    h7 = h7_horizon(C, threshold=threshold)
    summary = {
        "threshold": float(threshold),
        "mode": str(mode),
        "dphi_mean": float(d.mean()) if d.size else 0.0,
        "dphi_std": float(d.std()) if d.size else 0.0,
        "C_mean": float(C.mean()) if C.size else 0.0,
        "C_std": float(C.std()) if C.size else 0.0,
        "h7": float(h7),
        "h7_weighted": float(weighted_coherence_mean(C, power=1.0)),
        "h7_cusp": float(cusp_limited_h7(C, threshold=threshold, survival_floor=0.50)),
        "kappa_bound": float(omega_lipschitz_kappa_bound(C.mean() if C.size else 0.0)),
    }
    return DeltaPhiEstimate(dphi=d, coherence=C, h7=h7, summary=summary)
