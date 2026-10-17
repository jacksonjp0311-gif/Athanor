from __future__ import annotations
from typing import Any, Dict, List, Optional

import numpy as np

from .base import Agent
from ..core.coherence import (
    estimate, inject_bounded_noise, coherence_from_dphi, immunity_index,
    basin_drift, boundary_excess,
)

APPROVE, REFINE, REJECT = "APPROVE", "REFINE", "REJECT"


class VerifierAgent(Agent):
    """H7 gate with optional H20 (noise-immunity) and H44 (boundary-excess) gates.

    The primary H7 gate decides APPROVE / REFINE / REJECT. Optional gates can only
    *downgrade* an APPROVE to REFINE; they never upgrade a verdict. Every gate
    evaluated is recorded in ``candidate.tags['checks']`` so the ledger explains
    each verdict.
    """

    def __init__(
        self,
        threshold_h7: float = 0.70,
        dphi_mode: str = "l2",
        refine_floor: float = 0.50,
        h20: Optional[Dict[str, Any]] = None,
        h44: Optional[Dict[str, Any]] = None,
    ):
        self.threshold = float(threshold_h7)
        self.mode = str(dphi_mode)
        self.refine_floor = float(refine_floor)
        self.h20 = dict(h20 or {"enabled": False})
        self.h44 = dict(h44 or {"enabled": False})

    def _h20_check(self, est, seed: int) -> Dict[str, Any]:
        sigma = float(self.h20.get("sigma", 0.05))
        limit = float(self.h20.get("min_immunity", 0.90))
        d_pert = inject_bounded_noise(est.dphi, sigma=sigma, seed=int(seed))
        c_pert = coherence_from_dphi(d_pert)
        i20 = immunity_index(est.coherence, c_pert)
        return {"gate": "H20", "metric": "immunity_index", "value": float(i20), "limit": limit,
                "passed": bool(i20 >= limit), "sigma": sigma,
                "basin_drift": float(basin_drift(est.coherence, c_pert))}

    def _h44_check(self, h7: float) -> Dict[str, Any]:
        limit = float(self.h44.get("min_excess", 0.0))
        ex = boundary_excess(h7, self.threshold)
        return {"gate": "H44", "metric": "boundary_excess", "value": float(ex), "limit": limit,
                "passed": bool(ex >= limit)}

    def step(self, candidate, gate_seed: int = 0):
        checks: List[Dict[str, Any]] = []
        candidate.tags["checks"] = checks
        if candidate.telemetry is None:
            candidate.verdict = REJECT
            candidate.reason = "missing telemetry"
            return candidate

        est = estimate(candidate.telemetry.traj, threshold=self.threshold, mode=self.mode)
        candidate.dphi = est
        h7 = float(est.h7)

        checks.append({"gate": "H7", "metric": "h7", "value": h7, "limit": self.threshold,
                       "refine_floor": self.refine_floor, "passed": bool(h7 >= self.threshold)})

        if h7 < self.refine_floor:
            candidate.verdict, candidate.reason = REJECT, "H7 below refine floor"
            return candidate
        if h7 < self.threshold:
            candidate.verdict, candidate.reason = REFINE, "H7 in refine band"
            return candidate

        failed = []
        if self.h20.get("enabled"):
            c = self._h20_check(est, gate_seed)
            checks.append(c)
            if not c["passed"]:
                failed.append("H20 immunity below min_immunity")
        if self.h44.get("enabled"):
            c = self._h44_check(h7)
            checks.append(c)
            if not c["passed"]:
                failed.append("H44 boundary excess below min_excess")

        if failed:
            candidate.verdict, candidate.reason = REFINE, "H7>=threshold but " + "; ".join(failed)
        else:
            candidate.verdict, candidate.reason = APPROVE, "H7>=threshold"
        return candidate
