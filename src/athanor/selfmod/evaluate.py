"""Held-out evaluation of all arms (``athanor selfmod-arms``)."""
from __future__ import annotations

import copy
from typing import Any, Dict, Sequence

from .arms import run_arms, summarize
from .experiment import ARMS, DEFAULTS, TUNED_ADAPTIVE, TUNED_ADAPTIVE_CONSERVATIVE, adaptive_arms


def evaluate_all(seeds: Sequence[int], steps: int = 1000, workers: int | None = None) -> Dict[str, Any]:
    base = run_arms(seeds, ARMS, {"steps": steps}, workers)
    tuned_cfg = {**TUNED_ADAPTIVE["cfg"], "steps": steps}
    tuned = run_arms(seeds, adaptive_arms(TUNED_ADAPTIVE["gamma"]), tuned_cfg, workers)
    cons_cfg = {**TUNED_ADAPTIVE_CONSERVATIVE["cfg"], "steps": steps}
    cons = run_arms(seeds, {"validity+athanor-adaptive-τ0.75": {"validity": True, "athanor": True,
                                                               "gamma": TUNED_ADAPTIVE_CONSERVATIVE["gamma"]}},
                    cons_cfg, workers)
    res = copy.copy(base)
    res["arms"] = {**base["arms"], **tuned["arms"], **cons["arms"]}
    res["summary"] = {**base["summary"], **tuned["summary"], **cons["summary"]}
    res["runs"] = base["runs"] + tuned["runs"] + cons["runs"]
    res["arm_configs"] = {"base": {**DEFAULTS, "steps": steps}, "adaptive": tuned_cfg, "adaptive_tau075": cons_cfg,
                          "gamma": TUNED_ADAPTIVE["gamma"]}
    return res


def compact_arms(res: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(res)
    out["runs"] = [{k: v for k, v in r.items() if k != "series"} for r in res["runs"]]
    return out
