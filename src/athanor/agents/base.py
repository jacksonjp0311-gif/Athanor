from __future__ import annotations
from abc import ABC, abstractmethod

class Agent(ABC):
    @abstractmethod
    def step(self, *args, **kwargs):
        raise NotImplementedError