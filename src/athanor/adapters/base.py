from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np

from ..core.types import Candidate


class ProposerAdapter(ABC):
    name: str = "adapter"

    @abstractmethod
    def propose(
        self,
        parent: Candidate,
        rng: np.random.Generator,
        child_id: str,
    ) -> Candidate:
        raise NotImplementedError
