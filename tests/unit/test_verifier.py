import numpy as np
from athanor.core.types import Candidate, TelemetryBatch
from athanor.agents.verifier_agent import VerifierAgent

def test_verdict_present():
    c = Candidate(id='x', genome=np.zeros((8,), dtype=np.float32))
    c.telemetry = TelemetryBatch(traj=np.zeros((10,8), dtype=np.float32), meta={})
    v = VerifierAgent(threshold_h7=0.70, dphi_mode='l2')
    c = v.step(c)
    assert c.verdict in ('APPROVE','REFINE','REJECT')
