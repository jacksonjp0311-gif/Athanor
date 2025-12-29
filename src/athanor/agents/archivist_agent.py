from __future__ import annotations
from .base import Agent
from ..evolution.archive import MapElitesArchive

class ArchivistAgent(Agent):
    def __init__(self, bins=(16,16)):
        self.archive = MapElitesArchive(bins=bins)

    def step(self, candidate):
        admitted = False
        if candidate.verdict == ""APPROVE"":
            admitted = self.archive.add(candidate)
        return admitted
