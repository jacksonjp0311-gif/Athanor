"""Eval-gated, Athanor-governed config promotion (``athanor registry promote``).

A candidate config becomes the family's incumbent only if

1. **the eval suite passes** with the candidate injected: no captured bug has come
   back in the code, and the candidate satisfies every captured tuning limit of its
   family (so a new config cannot re-break an old fix); and
2. **Athanor approves the change itself** (dogfooding). On fresh *gate seeds* the
   candidate and the incumbent are both run; for every seed s the behaviour
   signature is ``σ_s = log10 MSE`` of the current self at checkpoints
   {10, 30, 100, 300, 1000} (clipped to [-3, 6], a broken self counts as 6). The
   per-seed drift is the RMS difference

       ΔΦ_s = ‖σ_s(candidate) − σ_s(incumbent)‖₂ / √k

   laid out as a trajectory so Athanor's own ``estimate`` (ΔΦ → C = 1/(1+ΔΦ) → H7)
   and ``VerifierAgent`` produce the verdict. APPROVE promotes, REFINE records the
   candidate as ``refine`` (promote with ``--allow-refine``), REJECT rejects it.

The gate is a *floor plus a step-size rule*, not an objective: it stops configs that
re-break captured cases or that change behaviour too abruptly on unseen seeds.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ..agents.verifier_agent import VerifierAgent
from ..config_registry import Registry
from ..core.types import Candidate, TelemetryBatch

CHECKPOINTS = (10, 30, 100, 300, 1000)
GATE_SEEDS = tuple(range(200, 216))  # never used by tuning (100-115) or the held-out report (0-15)
LOG_CLIP = (-3.0, 6.0)


def signature(series: Sequence[Optional[float]], checkpoints: Sequence[int] = CHECKPOINTS) -> np.ndarray:
    T = len(series)
    out = []
    for t in checkpoints:
        v = series[min(t, T) - 1]
        if v is None or not math.isfinite(float(v)) or float(v) <= 0:
            out.append(LOG_CLIP[1] if v is None or not math.isfinite(float(v)) else LOG_CLIP[0])
        else:
            out.append(float(np.clip(math.log10(float(v)), *LOG_CLIP)))
    return np.array(out, dtype=np.float64)


def _runs(spec: Dict[str, Any], seeds: Sequence[int], steps: int, workers: Optional[int]) -> Dict[int, Any]:
    from ..selfmod.arms import run_arms
    res = run_arms(list(seeds), {"x": dict(spec["arm"])}, {**spec["cfg"], "steps": int(steps)}, workers)
    return {int(r["seed"]): r for r in res["runs"]}, res["summary"]["x"]


def behaviour_verdict(candidate: Dict[str, Any], incumbent: Dict[str, Any], *, seeds: Sequence[int] = GATE_SEEDS,
                      steps: int = 1000, threshold: float = 0.70, refine_floor: float = 0.50,
                      workers: Optional[int] = None) -> Dict[str, Any]:
    cps = [c for c in CHECKPOINTS if c <= steps] or [steps]
    rc, sc = _runs(candidate["spec"], seeds, steps, workers)
    ri, si = _runs(incumbent["spec"], seeds, steps, workers)
    rows = []
    for s in seeds:
        d = (signature(rc[s]["series"]["test_mse"], cps) - signature(ri[s]["series"]["test_mse"], cps)) / math.sqrt(len(cps))
        rows.append(d)
    D = np.stack(rows)
    traj = np.vstack([np.zeros((1, D.shape[1])), np.cumsum(D, axis=0)])
    v = VerifierAgent(threshold_h7=threshold, refine_floor=refine_floor)
    c = v.step(Candidate(id=candidate["ref"], genome=np.zeros(1), telemetry=TelemetryBatch(traj=traj, meta={})))
    dphi = [float(x) for x in c.dphi.dphi]
    return {"verdict": c.verdict, "reason": c.reason, "h7": float(c.dphi.h7), "threshold": threshold,
            "refine_floor": refine_floor, "dphi_max_allowed": 1.0 / threshold - 1.0,
            "seeds": [int(s) for s in seeds], "steps": int(steps), "checkpoints": cps,
            "dphi_per_seed": [round(x, 6) for x in dphi], "C_per_seed": [round(1 / (1 + x), 6) for x in dphi],
            "dphi_mean": float(np.mean(dphi)), "dphi_max": float(np.max(dphi)),
            "candidate_summary": _brief(sc), "incumbent_summary": _brief(si)}


def _brief(s: Dict[str, Any]) -> Dict[str, Any]:
    keep = ("broken_commits", "severe_regressions", "median_mse_100", "median_mse_final",
            "median_steps_to_1p5", "never_reached_1p5", "commits")
    out = {}
    for k in keep:
        v = s.get(k)
        out[k] = "inf" if isinstance(v, float) and math.isinf(v) else (round(v, 6) if isinstance(v, float) else v)
    return out


def promote(registry: Registry, ref: str, *, cases_root: str, out_dir: Optional[str] = None,
            seeds: Sequence[int] = GATE_SEEDS, steps: int = 1000, allow_refine: bool = False,
            dry_run: bool = False, workers: Optional[int] = None, src_root: Optional[str] = None,
            bootstrap: bool = False) -> Dict[str, Any]:
    from .suite import run_suite
    entry = registry.get(ref)
    status = registry.status(ref)
    if status in ("promoted",):
        raise ValueError(f"{ref} is already the promoted incumbent")
    if status == "rejected":
        raise ValueError(f"{ref} was rejected; register a new version instead")
    incumbent_ref = registry.incumbent(entry["family"])
    if incumbent_ref is None and not bootstrap:
        raise ValueError(f"family {entry['family']!r} has no incumbent; use --bootstrap for the first promotion")
    cand = {"ref": ref, "family": entry["family"], "spec": entry["spec"], "spec_hash": entry["spec_hash"]}
    suite = run_suite(cases_root=cases_root, out_dir=out_dir, candidate=cand, src_root=src_root)
    report: Dict[str, Any] = {"ref": ref, "incumbent": incumbent_ref, "suite": {
        k: suite[k] for k in ("ok", "failing", "counts", "suite_digest", "ledger")}}
    if not suite["ok"]:
        decision, why = "reject", "eval suite failed: " + ", ".join(suite["failing"])
        report["verdict"] = None
    elif incumbent_ref is None:
        decision, why = "promote", "bootstrap: first incumbent of the family (suite passed)"
        report["verdict"] = None
    else:
        verdict = behaviour_verdict(cand, registry.get(incumbent_ref), seeds=seeds, steps=steps, workers=workers)
        report["verdict"] = verdict
        if verdict["verdict"] == "APPROVE":
            decision, why = "promote", f"suite passed; Athanor APPROVE (H7={verdict['h7']:.3f})"
        elif verdict["verdict"] == "REFINE" and allow_refine:
            decision, why = "promote", f"suite passed; Athanor REFINE (H7={verdict['h7']:.3f}) accepted by --allow-refine"
        elif verdict["verdict"] == "REFINE":
            decision, why = "refine", f"suite passed; Athanor REFINE (H7={verdict['h7']:.3f}): step too large, take a smaller one"
        else:
            decision, why = "reject", f"suite passed; Athanor REJECT (H7={verdict['h7']:.3f})"
    report["decision"], report["reason"] = decision, why
    if not dry_run:
        fields = {"reason": why, "suite_digest": suite["suite_digest"], "suite_counts": suite["counts"]}
        if report["verdict"]:
            v = report["verdict"]
            fields.update({"verdict": v["verdict"], "h7": v["h7"], "gate_seeds": [v["seeds"][0], v["seeds"][-1]],
                           "dphi_mean": round(v["dphi_mean"], 6), "dphi_max": round(v["dphi_max"], 6)})
        if decision == "promote" and incumbent_ref:
            fields["replaces"] = incumbent_ref
        report["event"] = registry.record(decision, ref, **fields)
    return report
