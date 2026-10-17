"""Public adapter API (3.0.0): plug any self-modifying program into ATHANOR.

You provide three callables about *your* program; ATHANOR provides the gate.

    probe(program)            -> sequence of numbers: the program's behaviour on fixed probe inputs
    propose(program, rng, s)  -> a modified program (s = 1.0, then 0.5, 0.25 on REFINE retries)
    evaluate(program)         -> float, lower is better (your objective)

and optionally ``check(program) -> bool`` (a validity pre-gate: return False or raise to reject).

One-shot gate for a single edit::

    gov = athanor.Governor(probe, scale=0.1)
    d = gov.judge(current, candidate)          # Decision(verdict="APPROVE" | "REFINE" | "REJECT", ...)

Whole governed loop::

    result = athanor.govern(initial, propose, evaluate, probe, steps=200, scale=0.1, check=check)
    result.program, result.counts, result.history

How the verdict is computed (unchanged ATHANOR pipeline): for each probe i the drift is
``|probe(candidate)_i − probe(current)_i| / (scale · tolerance)`` (a crash or a non-finite output
counts as BIG = 1000). The per-probe drifts form a cumulative trajectory, and ATHANOR's
``VerifierAgent`` turns it into ΔΦ → C = 1/(1+ΔΦ) → H7 = share of probes with C ≥ τ → verdict
(APPROVE if H7 ≥ τ, REFINE if H7 ≥ refine_floor, else REJECT). With τ = 0.70 a probe is coherent
when its drift is at most 1/τ − 1 ≈ 0.43 × ``scale``.

``scale`` is the size of a behaviour change you would call "one unit" (e.g. the output's standard
deviation, or 10 % of a typical score). It is the one setting you must choose for your program.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from .agents.verifier_agent import VerifierAgent
from .core.types import Candidate, TelemetryBatch

BIG = 1e3

__all__ = ["Governor", "Decision", "GovernResult", "govern", "GovernorError"]


class GovernorError(ValueError):
    """A user-side error in the adapter (bad probe output, bad settings), with a hint."""


@dataclass
class Decision:
    verdict: str
    h7: float
    dphi_mean: float
    dphi_max: float
    reason: str
    valid: Optional[bool] = None
    tolerance: float = 1.0
    probes: int = 0
    probe_failed: bool = False

    @property
    def approved(self) -> bool:
        return self.verdict == "APPROVE"

    def as_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in ("verdict", "h7", "dphi_mean", "dphi_max", "reason", "valid",
                                               "tolerance", "probes", "probe_failed")}


@dataclass
class GovernResult:
    program: Any
    score: float
    initial_score: float
    counts: Dict[str, int]
    commits: int
    history: List[Dict[str, Any]] = field(default_factory=list)
    ledger: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {"score": self.score, "initial_score": self.initial_score, "counts": dict(self.counts),
                "commits": self.commits, "steps": len(self.history), "ledger": self.ledger}


def _probe_vector(probe: Callable[[Any], Sequence[float]], program: Any) -> Optional[np.ndarray]:
    """The program's probe outputs, or None if the program crashes or returns non-finite values."""
    try:
        out = probe(program)
    except Exception:  # noqa: BLE001 - a crashing program is a behaviour, not an adapter error
        return None
    try:
        v = np.asarray(out, dtype=float).reshape(-1)
    except (TypeError, ValueError) as exc:
        raise GovernorError(f"probe(program) must return a sequence of numbers, got {type(out).__name__}: {exc}") \
            from exc
    if v.size == 0:
        raise GovernorError("probe(program) returned no values; probe the program on at least one fixed input")
    return v if np.all(np.isfinite(v)) else None


class Governor:
    """ATHANOR's gate for one program family. Stateless apart from its settings."""

    def __init__(self, probe: Callable[[Any], Sequence[float]], *, scale: float = 1.0, threshold: float = 0.70,
                 refine_floor: float = 0.50, check: Optional[Callable[[Any], Any]] = None):
        if not callable(probe):
            raise GovernorError("probe must be a callable: probe(program) -> list of numbers")
        if check is not None and not callable(check):
            raise GovernorError("check must be a callable: check(program) -> bool (or raise to reject)")
        if not (isinstance(scale, (int, float)) and math.isfinite(scale) and scale > 0):
            raise GovernorError(f"scale must be a positive number (the size of one unit of behaviour change), "
                                f"got {scale!r}")
        if not (0.0 < float(threshold) < 1.0):
            raise GovernorError(f"threshold must be in (0, 1); 0.70 is the default, got {threshold!r}")
        if not (0.0 <= float(refine_floor) <= float(threshold)):
            raise GovernorError(f"refine_floor must be in [0, threshold], got {refine_floor!r}")
        self.probe, self.check = probe, check
        self.scale, self.threshold, self.refine_floor = float(scale), float(threshold), float(refine_floor)
        self._verifier = VerifierAgent(threshold_h7=self.threshold, refine_floor=self.refine_floor)

    def is_valid(self, program: Any) -> bool:
        if self.check is None:
            return True
        try:
            return bool(self.check(program))
        except Exception:  # noqa: BLE001 - a failing check is a rejection
            return False

    def trajectory(self, cur: Optional[np.ndarray], new: Optional[np.ndarray], tolerance: float = 1.0) -> np.ndarray:
        if cur is None and new is None:
            raise GovernorError("both the current and the candidate program fail probe(); "
                                "the current program must run on every probe input")
        n = (cur if cur is not None else new).size
        if cur is None or new is None:
            d = np.full(n, BIG)
        else:
            if cur.size != new.size:
                raise GovernorError(f"probe() returned {cur.size} values for the current program but {new.size} "
                                    "for the candidate; it must use the same fixed probe inputs every time")
            d = np.minimum(np.abs(new - cur) / (self.scale * float(tolerance)), BIG)
        return np.vstack([np.zeros((1, 1)), np.cumsum(d.reshape(-1, 1), axis=0)])

    def judge(self, current: Any, candidate: Any, *, tolerance: float = 1.0, current_probe=None,
              candidate_probe=None) -> Decision:
        """Gate one edit ``current → candidate``. The validity check (if any) runs first."""
        valid = self.is_valid(candidate) if self.check is not None else None
        if valid is False:
            return Decision("REJECT", 0.0, BIG, BIG, "validity check failed", valid=False, tolerance=tolerance)
        cur = current_probe if current_probe is not None else _probe_vector(self.probe, current)
        new = candidate_probe if candidate_probe is not None else _probe_vector(self.probe, candidate)
        traj = self.trajectory(cur, new, tolerance)
        c = self._verifier.step(Candidate(id="edit", genome=np.zeros(1), telemetry=TelemetryBatch(traj=traj, meta={})))
        dphi = np.asarray(c.dphi.dphi, dtype=float)
        return Decision(c.verdict, float(c.dphi.h7), float(dphi.mean()), float(dphi.max()), c.reason, valid=valid,
                        tolerance=float(tolerance), probes=int(traj.shape[0] - 1), probe_failed=new is None)


def govern(initial: Any, propose: Callable[[Any, np.random.Generator, float], Any],
           evaluate: Callable[[Any], float], probe: Callable[[Any], Sequence[float]], *, steps: int = 100,
           seed: int = 0, scale: float = 1.0, threshold: float = 0.70, refine_floor: float = 0.50,
           refine_attempts: int = 2, check: Optional[Callable[[Any], Any]] = None, ledger: Optional[str] = None,
           governed: bool = True) -> GovernResult:
    """Run a governed self-modification loop.

    Each step: ``propose`` an edit; keep it only if ``evaluate`` improves, the optional ``check``
    passes and ATHANOR APPROVEs. On REFINE the edit is re-proposed at half the scale (up to
    ``refine_attempts`` times). ``governed=False`` keeps every improving edit (the ungoverned
    baseline) while still recording the verdicts. ``ledger`` writes a hash-chained JSONL ledger
    that ``athanor verify``-style tools can check (``athanor.ledger.verify_ledger``).
    """
    for name, fn in (("propose", propose), ("evaluate", evaluate)):
        if not callable(fn):
            raise GovernorError(f"{name} must be a callable")
    gov = Governor(probe, scale=scale, threshold=threshold, refine_floor=refine_floor, check=check)
    cur_probe = _probe_vector(probe, initial)
    if cur_probe is None:
        raise GovernorError("the initial program fails probe() (crash or non-finite output); "
                            "ATHANOR measures drift relative to a working program")
    score0 = float(evaluate(initial))
    if not math.isfinite(score0):
        raise GovernorError(f"evaluate(initial) must be a finite number, got {score0!r}")
    writer = None
    if ledger:
        from .ledger import LedgerWriter
        os.makedirs(os.path.dirname(os.path.abspath(ledger)), exist_ok=True)
        writer = LedgerWriter(ledger)
    program, score = initial, score0
    counts = {"APPROVE": 0, "REFINE": 0, "REJECT": 0, "NOT_IMPROVED": 0, "INVALID": 0, "PROPOSE_FAILED": 0}
    history: List[Dict[str, Any]] = []
    commits = 0
    for step in range(int(steps)):
        row: Dict[str, Any] = {"step": step, "score": score}
        committed, attempt, decision = False, 0, None
        while True:
            rng = np.random.default_rng([int(seed), step, attempt])
            try:
                cand = propose(program, rng, 0.5 ** attempt)
            except Exception as exc:  # noqa: BLE001
                counts["PROPOSE_FAILED"] += 1
                row.update({"outcome": "PROPOSE_FAILED", "error": f"{type(exc).__name__}: {exc}"})
                break
            try:
                new_score = float(evaluate(cand))
            except Exception:  # noqa: BLE001 - a crashing candidate does not improve
                new_score = math.inf
            if not (math.isfinite(new_score) and new_score < score):
                counts["NOT_IMPROVED"] += 1
                row["outcome"] = "NOT_IMPROVED"
                break
            new_probe = _probe_vector(probe, cand)
            decision = gov.judge(program, cand, current_probe=cur_probe, candidate_probe=new_probe)
            if decision.valid is False:
                counts["INVALID"] += 1
                row["outcome"] = "INVALID"
                break
            counts[decision.verdict] += 1
            row.update({"outcome": decision.verdict, "h7": decision.h7, "dphi_mean": decision.dphi_mean,
                        "attempt": attempt})
            if decision.verdict == "REFINE" and governed and attempt < int(refine_attempts):
                attempt += 1
                continue
            if decision.approved or not governed:
                program, score, committed, commits = cand, new_score, True, commits + 1
                cur_probe = new_probe if new_probe is not None else cur_probe
            break
        row.update({"committed": committed, "new_score": score})
        history.append(row)
        if writer:
            writer.append(row)
    return GovernResult(program=program, score=score, initial_score=score0, counts=counts, commits=commits,
                        history=history, ledger=ledger)
