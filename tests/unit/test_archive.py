import numpy as np
from athanor.core.types import Candidate, TelemetryBatch
from athanor.core.coherence import estimate
from athanor.evolution.archive import MapElitesArchive

def test_archive_add():
    a = MapElitesArchive(bins=(4,4))
    c = Candidate(id='x', genome=np.zeros((8,), dtype=np.float32))
    c.tags['delta_norm'] = 0.1
    c.telemetry = TelemetryBatch(traj=np.zeros((10,8), dtype=np.float32), meta={})
    c.dphi = estimate(c.telemetry.traj, threshold=0.70)
    c.score_f = 0.5
    c.verdict = 'APPROVE'
    assert a.add(c) is True
