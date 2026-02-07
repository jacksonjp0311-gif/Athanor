import numpy as np

from athanor.adapters import ProposerAdapter
from athanor.agents.proposer_agent import ProposerAgent
from athanor.core.types import Candidate


class StubAdapter(ProposerAdapter):
    name = "stub"

    def __init__(self):
        self.calls = 0

    def propose(self, parent: Candidate, rng: np.random.Generator, child_id: str) -> Candidate:
        self.calls += 1
        child = type(parent)(id=child_id, genome=parent.genome.copy())
        child.tags["adapter"] = self.name
        return child


def test_proposer_agent_uses_adapter():
    adapter = StubAdapter()
    proposer = ProposerAgent(adapter=adapter)
    rng = np.random.default_rng(123)
    parent = Candidate(id="parent", genome=np.zeros((4,), dtype=np.float32))

    child = proposer.step(parent=parent, rng=rng, child_id="child")

    assert adapter.calls == 1
    assert child.tags["adapter"] == "stub"


def test_proposer_agent_defaults_to_gaussian_noise_adapter():
    proposer = ProposerAgent()
    rng = np.random.default_rng(123)
    parent = Candidate(id="parent", genome=np.zeros((4,), dtype=np.float32))

    child = proposer.step(parent=parent, rng=rng, child_id="child")

    assert "delta_norm" in child.tags
    assert child.tags["proposer_adapter"] == "gaussian_noise"
