import numpy as np
from athanor.core.coherence import estimate

def test_h7_range():
    traj = np.zeros((10, 4), dtype=np.float32)
    est = estimate(traj, threshold=0.70, mode='l2')
    assert 0.0 <= est.h7 <= 1.0
