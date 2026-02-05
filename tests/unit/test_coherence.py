import numpy as np
from athanor.core.coherence import (
    delta_phi,
    coherence_from_dphi,
    h7_horizon,
    weighted_coherence_mean,
    cusp_limited_h7,
)

def test_delta_phi_l2_basic():
    traj = np.array([[0,0],[3,4],[3,4]], dtype=np.float32)
    d = delta_phi(traj, mode='l2')
    assert d.shape == (2,)
    assert float(d[0]) == 5.0
    assert float(d[1]) == 0.0

def test_coherence_monotone():
    d = np.array([0.0, 1.0, 9.0], dtype=np.float32)
    c = coherence_from_dphi(d)
    assert c[0] > c[1] > c[2]

def test_h7_horizon():
    c = np.array([0.71, 0.69, 0.70, 0.10], dtype=np.float32)
    h7 = h7_horizon(c, threshold=0.70)
    assert abs(h7 - 0.5) < 1e-6

def test_weighted_and_cusp_h7_helpers():
    c = np.array([0.2, 0.6, 0.9], dtype=np.float32)
    wm = weighted_coherence_mean(c, power=2.0)
    assert wm > float(c.mean())

    h7_all = h7_horizon(c, threshold=0.7)
    h7_cusp = cusp_limited_h7(c, threshold=0.7, survival_floor=0.5)
    assert h7_all <= h7_cusp <= 1.0
