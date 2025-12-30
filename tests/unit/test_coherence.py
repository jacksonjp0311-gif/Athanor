import numpy as np
from athanor.core.coherence import delta_phi, coherence_from_dphi, h7_horizon

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