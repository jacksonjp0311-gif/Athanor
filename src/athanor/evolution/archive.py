from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Dict, Tuple, Any

@dataclass
class ArchiveCell:
    best_id: str
    best_f: float
    meta: Dict[str, Any]

class MapElitesArchive:
    def __init__(self, bins=(16,16)):
        self.bins = tuple(int(x) for x in bins)
        self.cells: Dict[Tuple[int,int], ArchiveCell] = {}

    def descriptor(self, cand) -> Tuple[int,int]:
        h7 = float(cand.dphi.h7) if cand.dphi else 0.0
        dn = float(cand.tags.get(""delta_norm"", 0.0))
        i = int(np.clip(h7 * self.bins[0], 0, self.bins[0]-1))
        j = int(np.clip((dn / 1.0) * self.bins[1], 0, self.bins[1]-1))
        return (i, j)

    def add(self, cand) -> bool:
        key = self.descriptor(cand)
        cur = self.cells.get(key)
        if (cur is None) or (float(cand.score_f) > float(cur.best_f)):
            self.cells[key] = ArchiveCell(
                best_id=str(cand.id),
                best_f=float(cand.score_f),
                meta={
                    ""h7"": float(cand.dphi.h7) if cand.dphi else 0.0,
                    ""delta_norm"": float(cand.tags.get(""delta_norm"", 0.0)),
                    ""verdict"": str(cand.verdict),
                },
            )
            return True
        return False

    def stats(self) -> Dict[str, Any]:
        if not self.cells:
            return {""filled"": 0, ""mean_best_f"": 0.0, ""max_best_f"": 0.0}
        fs = np.array([c.best_f for c in self.cells.values()], dtype=np.float32)
        return {
            ""filled"": int(len(self.cells)),
            ""mean_best_f"": float(fs.mean()),
            ""max_best_f"": float(fs.max()),
        }