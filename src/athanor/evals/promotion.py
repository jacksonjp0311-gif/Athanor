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
GATE_SEEDS = tuple(range(200, 216))  # the 2.7 gate block; spent. 3.0 takes fresh blocks (athanor.seedsets)
LOG_CLIP = (-3.0, 6.0)
TSP_BROKEN_RATIO = 2.0   # a broken TSP self counts as tour ratio 2.0 (seed program: 1.177)


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


def _runs(spec: Dict[str, Any], seeds: Sequence[int], steps: int, workers: Optional[int],
          family: str = "selfmod"):
    if family == "tsp":
        from ..selfmod.tsp_experiment import run_tsp_arms
        arm = {**dict(spec["arm"]), "cfg": dict(spec.get("cfg") or {})}
        res = run_tsp_arms(list(seeds), {"x": arm}, {"steps": int(steps)}, workers=workers or 8)
    else:
        from ..selfmod.arms import run_arms
        res = run_arms(list(seeds), {"x": dict(spec["arm"])}, {**spec["cfg"], "steps": int(steps)}, workers)
    return {int(r["seed"]): r for r in res["runs"]}, res["summary"]["x"]


def tsp_signature(series: Sequence[Optional[float]], checkpoints: Sequence[int] = CHECKPOINTS) -> np.ndarray:
    """Held-out tour ratio at checkpoints, in units of the testbed's a-priori scale KAPPA (10 %)."""
    from ..selfmod.tsp_experiment import KAPPA
    T = len(series)
    vals = []
    for t in checkpoints:
        v = series[min(t, T) - 1]
        vals.append(TSP_BROKEN_RATIO if v is None or not math.isfinite(float(v)) else min(float(v), TSP_BROKEN_RATIO))
    return np.array(vals, dtype=np.float64) / KAPPA


def behaviour_verdict(candidate: Dict[str, Any], incumbent: Dict[str, Any], *, seeds: Sequence[int] = GATE_SEEDS,
                      steps: int = 1000, threshold: float = 0.70, refine_floor: float = 0.50,
                      workers: Optional[int] = None) -> Dict[str, Any]:
    family = candidate.get("family", "selfmod")
    cps = [c for c in CHECKPOINTS if c <= steps] or [steps]
    rc, sc = _runs(candidate["spec"], seeds, steps, workers, family)
    ri, si = _runs(incumbent["spec"], seeds, steps, workers, family)
    if family == "tsp":
        sig, key = tsp_signature, "held"
    elif family == "selfmod":
        sig, key = signature, "test_mse"
    else:
        raise ValueError(f"no behaviour signature for family {family!r} (supported: selfmod, tsp)")
    rows = []
    for s in seeds:
        d = (sig(rc[s]["series"][key], cps) - sig(ri[s]["series"][key], cps)) / math.sqrt(len(cps))
        rows.append(d)
    D = np.stack(rows)
    traj = np.vstack([np.zeros((1, D.shape[1])), np.cumsum(D, axis=0)])
    v = VerifierAgent(threshold_h7=threshold, refine_floor=refine_floor)
    c = v.step(Candidate(id=candidate["ref"], genome=np.zeros(1), telemetry=TelemetryBatch(traj=traj, meta={})))
    dphi = [float(x) for x in c.dphi.dphi]
    return {"verdict": c.verdict, "reason": c.reason, "h7": float(c.dphi.h7), "threshold": threshold,
            "family": family, "refine_floor": refine_floor, "dphi_max_allowed": 1.0 / threshold - 1.0,
            "seeds": [int(s) for s in seeds], "steps": int(steps), "checkpoints": cps,
            "dphi_per_seed": [round(x, 6) for x in dphi], "C_per_seed": [round(1 / (1 + x), 6) for x in dphi],
            "dphi_mean": float(np.mean(dphi)), "dphi_max": float(np.max(dphi)),
            "candidate_summary": _brief(sc), "incumbent_summary": _brief(si)}


def _brief(s: Dict[str, Any]) -> Dict[str, Any]:
    keep = ("broken_commits", "severe_regressions", "median_mse_100", "median_mse_final",
            "median_steps_to_1p5", "never_reached_1p5", "commits",
            "median_held_50", "median_held_1000", "median_steps_to_good", "never_good", "frozen_runs")
    out = {}
    for k in keep:
        if k not in s:
            continue
        v = s.get(k)
        out[k] = "inf" if isinstance(v, float) and math.isinf(v) else (round(v, 6) if isinstance(v, float) else v)
    return out


def promote(registry: Registry, ref: str, *, cases_root: str, out_dir: Optional[str] = None,
            seeds: Optional[Sequence[int]] = None, steps: int = 1000, allow_refine: bool = False,
            dry_run: bool = False, workers: Optional[int] = None, src_root: Optional[str] = None,
            bootstrap: bool = False, require_fresh_evidence: bool = False,
            allow_seed_reuse: bool = False) -> Dict[str, Any]:
    """``seeds=None`` takes the next never-used gate block (``athanor.seedsets``); a dry run uses scratch seeds."""
    from ..seedsets import choose_gate_seeds
    from .suite import run_suite
    entry = registry.get(ref)
    seeds, seed_policy = choose_gate_seeds(registry.events(), seeds, dry_run=dry_run, allow_reuse=allow_seed_reuse)
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
    report: Dict[str, Any] = {"ref": ref, "incumbent": incumbent_ref, "gate_seed_policy": seed_policy, "suite": {
        k: suite[k] for k in ("ok", "failing", "counts", "suite_digest", "ledger")}}
    report["evidence"] = evidence = check_promotion_evidence(registry, entry, cases_root, suite)
    if not suite["ok"]:
        decision, why = "reject", "eval suite failed: " + ", ".join(suite["failing"])
    elif require_fresh_evidence and evidence.get("hard"):
        decision, why = "refine", ("stale evidence: " + ", ".join(sorted({h["path"] for h in evidence["hard"]}))
                                   + " changed since it was cited; re-verify before promoting")
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
                           "dphi_mean": round(v["dphi_mean"], 6), "dphi_max": round(v["dphi_max"], 6),
                           "gate_seed_source": seed_policy["source"]})
            if seed_policy.get("reuse"):
                fields["seed_reuse"] = seed_policy.get("overlaps")
        if evidence.get("checked") is not None:
            fields["evidence_checked"] = evidence["checked"]
            fields["stale_evidence"] = sorted({x["path"] for x in evidence.get("stale", [])})
        if decision == "promote" and incumbent_ref:
            fields["replaces"] = incumbent_ref
        report["event"] = registry.record(decision, ref, **fields)
    return report


def check_promotion_evidence(registry: Registry, entry: Dict[str, Any], cases_root: str,
                             suite: Dict[str, Any]) -> Dict[str, Any]:
    """Re-verify every past result the promotion relies on (needs ``athanor[search]``).

    Sources: the candidate's own registry evidence that carries a SHA-256, and the
    AgentSearch citations of the tuning cases of its family.
    """
    import os
    from ..config_registry import check_row_evidence
    from ..search import search_available
    repo = os.path.dirname(os.path.dirname(os.path.abspath(cases_root)))
    rows = check_row_evidence(entry.get("evidence", []), repo)
    if not search_available():
        if not rows:
            return {"checked": None, "note": "AgentSearch not installed; evidence not verified"}
        return _evidence_report(rows, {"registry_rows": len(rows)},
                                note="AgentSearch not installed; only pinned log rows verified")
    from ..search import EvidenceIndex, read_evidence
    from .cases import load_cases
    cites = [e for e in entry.get("evidence", []) if isinstance(e, dict) and e.get("sha256") and e.get("path")]
    sources = {"registry": len(cites), "registry_rows": len(rows)}
    for ac in load_cases(cases_root, kinds=["tuning"]):
        if ac.family == entry["family"]:
            c = read_evidence(ac.path)
            sources[ac.case_id] = len(c)
            cites.extend(c)
    results = list(rows)
    if cites:
        with EvidenceIndex(repo) as idx:
            results += idx.check(cites)["results"]
    return _evidence_report(results, sources)


def _evidence_report(results, sources, note=None) -> Dict[str, Any]:
    from ..search import HARD
    stale = [{k: x.get(k) for k in ("path", "status", "detail")} for x in results if x["status"] != "fresh"]
    out = {"checked": len(results), "fresh": len(results) - len(stale), "sources": sources,
           "stale": stale, "hard": [x for x in stale if x["status"] in HARD]}
    if note:
        out["note"] = note
    return out
