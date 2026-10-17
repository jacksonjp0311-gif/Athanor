"""Second self-modification testbed: a multi-function TSP solver that rewrites its own source.

Everything is offline and deterministic. The proposer is programmatic AST mutation (see
``tsp_program.mutate_program``); no LLM is used. Athanor's governor (``VerifierAgent``), the validity
pre-gate (``validity_check``) and the adaptive schedule (``scheduled_tolerance``) are reused unchanged.

Per step the agent proposes one edit to its own program. It *wants* to commit any edit that shortens
its tours on a minibatch of its own training instances. The arms decide what else must hold.

ΔΦ for an edit: per probe instance, |L_new - L_old| / (L_old * KAPPA * tol) (BIG if either program fails
on that probe), plus ``structure_weight`` x module-level structural distance. KAPPA = 0.10 is fixed a
priori: a 10% change in tour length plays the role sigma_y plays in the 2.4 testbed.
"""
from __future__ import annotations

import hashlib
import math
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..agents.verifier_agent import VerifierAgent
from ..core.types import Candidate, TelemetryBatch
from ..core.validity import validity_check
from ..evolution.dgm_loop import derive_seed
from ..ledger import LedgerWriter
from .experiment import ARMS, BIG, TUNED_ADAPTIVE, TUNED_ADAPTIVE_CONSERVATIVE, scheduled_tolerance
from .tsp_program import SEED_PROGRAM, BrokenProgram, Program, run_instance, structural_distance, mutate_program

KAPPA = 0.10            # a priori ΔΦ scale: 10% relative tour-length change
SEVERE_DELTA = 0.05     # severe regression: held-out mean ratio worse by > 0.05 (5% of the reference)
GOOD_RATIO = 1.05       # "good": held-out mean ratio <= 1.05 (within 5% of the harness reference)
CHECKPOINTS = (50, 1000)  # early / late held-out checkpoints (step counts)

TSP_DEFAULTS: Dict[str, Any] = {
    "steps": 1000, "minibatch": 4, "n_train": 24, "threshold_h7": 0.7, "refine_floor": 0.5,
    "refine_attempts": 2, "structure_weight": 0.5, "eval_set": "held",
    # 3.0: size-scaled probe/validity inputs. None (2.6 behaviour) | "checks" | "checks+probes"
    "probe_scaling": None, "deploy_n_max": None,
}
SCALE_FRACTIONS = (0.5, 0.75, 1.0)   # scaled inputs at these fractions of the deployment size


# ------------------------------------------------------------- instances
def _instance(rng: np.random.Generator, n: int, kind: str) -> List[List[float]]:
    if kind == "uniform":
        pts = rng.uniform(0, 100, size=(n, 2))
    else:  # clustered
        k = max(2, n // 8)
        centres = rng.uniform(0, 100, size=(k, 2))
        pts = centres[rng.integers(k, size=n)] + rng.normal(0, 6, size=(n, 2))
    d = np.sqrt(((pts[:, None, :] - pts[None, :, :]) ** 2).sum(-1))
    return [[float(round(v, 6)) for v in row] for row in d]


def _instances(seed_parts: Tuple[int, ...], count: int, lo: int, hi: int) -> List[List[List[float]]]:
    rng = np.random.default_rng(derive_seed(*seed_parts))
    return [_instance(rng, int(rng.integers(lo, hi + 1)), "uniform" if i % 2 == 0 else "clustered")
            for i in range(count)]


def reference_length(D: List[List[float]]) -> float:
    """Harness reference: best of nearest-neighbour-from-every-start + 2-opt to convergence."""
    n = len(D)
    best = math.inf
    for s in range(n):
        tour, left = [s], set(range(n)) - {s}
        while left:
            j = min(left, key=lambda c: (D[tour[-1]][c], c))
            tour.append(j)
            left.discard(j)
        changed = True
        while changed:
            changed = False
            for i in range(1, n - 1):
                for j in range(i + 1, n):
                    a, b, c, e = tour[i - 1], tour[i], tour[j], tour[(j + 1) % n]
                    if D[a][c] + D[b][e] - D[a][b] - D[c][e] < -1e-9:
                        tour[i:j + 1] = tour[i:j + 1][::-1]
                        changed = True
        best = min(best, math.fsum(D[tour[k]][tour[(k + 1) % n]] for k in range(n)))
    return float(best)


@lru_cache(maxsize=None)
def fixed_sets() -> Dict[str, Any]:
    """Probe and held-out instances, fixed for every seed (the agent never sees held-out scores)."""
    probes = _instances((9001,), 16, 8, 16)
    held = _instances((9002,), 32, 20, 45)
    return {"probes": probes, "held": held, "held_ref": [reference_length(D) for D in held]}


@lru_cache(maxsize=None)
def tuning_sets() -> Dict[str, Any]:
    """Same distribution as the held-out set but different instances: used only by the tuning pass,
    so tuning never touches held-out seeds *or* held-out instances."""
    base = fixed_sets()
    tune = _instances((9003,), 32, 20, 45)
    return {"probes": base["probes"], "held": tune, "held_ref": [reference_length(D) for D in tune]}


@lru_cache(maxsize=None)
def scaled_inputs(n_max: int) -> Tuple[Tuple[Tuple[float, ...], ...], ...]:
    """Validity/probe inputs that scale with the task: one uniform and one clustered instance at
    each of 50 %, 75 % and 100 % of the largest deployment size ``n_max``. Generated from their own
    seed, so they share no instance with training, probes, tuning or held-out sets."""
    rng = np.random.default_rng(derive_seed(9005, int(n_max)))
    out = []
    for f in SCALE_FRACTIONS:
        n = max(3, int(math.ceil(f * n_max)))
        for kind in ("uniform", "clustered"):
            out.append(tuple(tuple(r) for r in _instance(rng, n, kind)))
    return tuple(out)


def deploy_n_max(cfg: Dict[str, Any], sets: Dict[str, Any]) -> int:
    """The largest instance the solver is deployed on: ``cfg['deploy_n_max']`` or the largest
    evaluation instance (only its *size* is used; the agent never sees held-out scores)."""
    return int(cfg.get("deploy_n_max") or max(len(D) for D in sets["held"]))


@lru_cache(maxsize=64)
def training_set(seed: int, n_train: int) -> Dict[str, Any]:
    tr = _instances((seed, 11), n_train, 10, 30)
    return {"train": tr, "train_ref": [reference_length(D) for D in tr]}


# ------------------------------------------------------------- scoring
def mean_ratio(prog: Optional[Program], Ds, refs, strict: bool = True) -> Tuple[Optional[float], Optional[str]]:
    """Mean tour/ref ratio over instances; (None, failure status) if any instance fails.

    strict=False is the agent's own (lenient) scoring: it does not check that tours are permutations."""
    if prog is None:
        return None, "compile"
    parts = []
    for D, r in zip(Ds, refs):
        st, L = run_instance(prog, D, strict=strict)
        if st != "ok":
            return None, st
        parts.append(L / r)
    return math.fsum(parts) / len(Ds), None


def probe_lengths(prog: Program, probes) -> List[Optional[float]]:
    """Behaviour on the probes as the agent observes it (lenient lengths; None on crash/timeout)."""
    out = []
    for D in probes:
        st, L = run_instance(prog, D, strict=False)
        out.append(L if st == "ok" else None)
    return out


def tsp_trajectory(old_len, new_len, old_src: str, new_src: str, cfg, tol: float = 1.0) -> np.ndarray:
    beh = np.array([BIG if (a is None or b is None) else min(BIG, abs(b - a) / (a * KAPPA * float(tol)))
                    for a, b in zip(old_len, new_len)], dtype=float)
    st = float(cfg["structure_weight"]) * structural_distance(old_src, new_src)
    d = np.stack([beh, np.full_like(beh, st)], axis=1)
    return np.vstack([np.zeros((1, 2)), np.cumsum(d, axis=0)])


# ------------------------------------------------------------- unit-test-style check suite
def check_suite(train: Sequence, extra: Sequence = ()) -> List[Tuple[str, Any]]:
    """Checks the agent's program must pass (no held-out data): its own training + probe instances,
    edge cases, unit tests of the heuristic helpers, and (3.0, optional) size-scaled inputs."""
    sets = fixed_sets()
    cases: List[Tuple[str, Any]] = [("solve", D) for D in list(sets["probes"]) + list(train)]
    cases += [("solve", [list(r) for r in D]) for D in extra]
    cases += [("solve", [[0.0, 1.0, 1.0], [1.0, 0.0, 1.0], [1.0, 1.0, 0.0]]),  # n = 3
              ("solve", [[0.0] * 5 for _ in range(5)])]                        # duplicate points
    cases += [("priority", (d, k, n)) for d in (0.0, 1.5, 70.0) for k, n in ((1, 10), (9, 10), (20, 45))]
    cases += [("budget", n) for n in (3, 10, 45)] + [("pick_start", n) for n in (3, 10, 45)]
    return cases


def make_check(prog: Program):
    """Adapter: each check returns 0.0 or raises ValueError, so ``validity_check`` is reused unchanged."""
    def check(case):
        what, arg = case
        try:
            if what == "solve":
                st, _ = run_instance(prog, arg)
                if st != "ok":
                    raise ValueError(st)
                return 0.0
            prog._ticks = 0
            v = prog.ns[what](*arg) if what == "priority" else prog.ns[what](arg)
            v = float(v)
            if what == "budget" and not (v >= 0):
                raise ValueError("negative budget")
            return v
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001 - any crash/timeout of the agent's code fails the check
            raise ValueError(type(exc).__name__) from exc
    return check


# ------------------------------------------------------------- arms
def tsp_arms() -> Dict[str, Dict[str, Any]]:
    """Arms carried over from 2.5 unchanged (incl. the conservative setting, *not* retuned)."""
    arms: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in ARMS.items()}
    arms["validity+athanor-conservative"] = {"validity": True, "athanor": True,
                                             "gamma": TUNED_ADAPTIVE_CONSERVATIVE["gamma"],
                                             "cfg": dict(TUNED_ADAPTIVE_CONSERVATIVE["cfg"])}
    arms["validity+athanor-adaptive"] = {"validity": True, "athanor": True, "gamma": TUNED_ADAPTIVE["gamma"],
                                         "cfg": dict(TUNED_ADAPTIVE["cfg"])}
    return arms


def _compile(src: str) -> Optional[Program]:
    try:
        return Program(src)
    except (BrokenProgram, SyntaxError, RecursionError, ValueError, TypeError):
        return None


def run_tsp(seed: int, arm: Dict[str, Any], arm_name: str = "custom", cfg: Dict[str, Any] | None = None,
            out_dir: str | None = None) -> Dict[str, Any]:
    cfg = {**TSP_DEFAULTS, **(arm.get("cfg") or {}), **(cfg or {})}
    use_validity, use_athanor, gamma = bool(arm["validity"]), bool(arm["athanor"]), arm.get("gamma")
    sets = tuning_sets() if cfg.get("eval_set") == "tuning" else fixed_sets()
    ts = training_set(seed, int(cfg["n_train"]))
    train, train_ref, probes = ts["train"], ts["train_ref"], sets["probes"]
    scaling = cfg.get("probe_scaling")
    if scaling not in (None, "checks", "checks+probes"):
        raise ValueError(f"probe_scaling must be None, 'checks' or 'checks+probes', not {scaling!r}")
    extra = scaled_inputs(deploy_n_max(cfg, sets)) if scaling else ()
    if scaling == "checks+probes":
        probes = list(probes) + [[list(r) for r in D] for D in extra]
    suite = check_suite(train, extra)
    verifier = VerifierAgent(threshold_h7=cfg["threshold_h7"], refine_floor=cfg["refine_floor"])
    src = SEED_PROGRAM
    prog = Program(src)
    held, held_fail = mean_ratio(prog, sets["held"], sets["held_ref"])
    seed_held = held
    cur_probe = probe_lengths(prog, probes)
    cur_train, _ = mean_ratio(prog, train, train_ref, strict=False)
    best_train = cur_train if cur_train is not None else math.inf
    writer = LedgerWriter(os.path.join(out_dir, "ledger.jsonl")) if out_dir else None
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    series: Dict[str, List[Any]] = {"held": [], "committed": []}
    counts = {"APPROVE": 0, "REFINE": 0, "REJECT": 0}
    commits = regressions = severe = broken_commits = validity_rejections = proposals_invalid = 0
    broken_by_kind = {"crash": 0, "timeout": 0, "invalid": 0}
    broken_by_verdict = {"APPROVE": 0, "REFINE": 0, "REJECT": 0, "UNGATED": 0}
    severe_events: List[Dict[str, Any]] = []

    for step in range(int(cfg["steps"])):
        brng = np.random.default_rng(derive_seed(seed, 3, step))
        idx = sorted(brng.choice(len(train), size=int(cfg["minibatch"]), replace=False).tolist())
        mb, mb_ref = [train[i] for i in idx], [train_ref[i] for i in idx]
        cur_mb, _ = mean_ratio(prog, mb, mb_ref, strict=False)
        cur_mb = math.inf if cur_mb is None else cur_mb
        tol = 1.0
        if gamma:
            e_cur = ((cur_train - 1.0) / KAPPA) ** 2 if cur_train is not None else math.inf
            e_best = ((best_train - 1.0) / KAPPA) ** 2 if math.isfinite(best_train) else math.inf
            tol = scheduled_tolerance(e_cur, e_best, 1.0, step, gamma, cfg)

        def propose(attempt: int, scale: float):
            rng = np.random.default_rng(derive_seed(seed, 4, step, attempt))
            new_src, kind = mutate_program(src, rng, scale=scale)
            p = _compile(new_src)
            return None if p is None else (new_src, kind, p)

        def judge(new_src, new_prog):
            nl = probe_lengths(new_prog, probes) if use_athanor else None
            if not use_athanor:
                return None
            traj = tsp_trajectory(cur_probe, nl, src, new_src, cfg, tol=tol)
            c = Candidate(id=f"s{step}", genome=np.zeros(1), telemetry=TelemetryBatch(traj=traj, meta={}))
            return verifier.step(c), nl

        def improves(new_prog) -> bool:
            r, _ = mean_ratio(new_prog, mb, mb_ref, strict=False)
            return r is not None and r < cur_mb - 1e-12

        def valid(new_prog) -> bool:
            return validity_check(make_check(new_prog), suite)["passed"]

        row: Dict[str, Any] = {"step": step, "seed": seed, "mode": arm_name, "tolerance": tol}
        committed, verdict, trail = False, None, []
        p = propose(0, 1.0)
        if p is None:
            proposals_invalid += 1
            row["verdict"] = "INVALID"
        else:
            new_src, kind, new_prog = p
            imp = improves(new_prog)
            ok = valid(new_prog) if (use_validity and imp) else True
            j = judge(new_src, new_prog) if (use_athanor and imp and ok) else None
            verdict = j[0].verdict if j else None
            trail.append({"attempt": 0, "kind": kind, "verdict": verdict, "improved": imp, "valid": ok})
            k = 0
            while j is not None and verdict == "REFINE" and k < int(cfg["refine_attempts"]):
                k += 1
                q = propose(k, 0.5 ** k)
                if q is None:
                    break
                new_src, kind, new_prog = q
                imp = improves(new_prog)
                ok = valid(new_prog) if (use_validity and imp) else True
                j = judge(new_src, new_prog) if (imp and ok) else None
                verdict = j[0].verdict if j else None
                trail.append({"attempt": k, "kind": kind, "verdict": verdict, "improved": imp, "valid": ok})
            if imp and not ok:
                validity_rejections += 1
            if verdict:
                counts[verdict] += 1
            committed = imp and ok and (not use_athanor or verdict == "APPROVE")
            if j is not None:
                c = j[0]
                row.update({"h7": float(c.dphi.h7), "dphi_mean": float(c.dphi.summary["dphi_mean"])})
            row["verdict"] = verdict or ("NOT_IMPROVED" if not imp else ("INVALID_CHECKS" if not ok else "UNGATED"))

        if committed:
            old = held
            src, prog = new_src, new_prog
            held, held_fail = mean_ratio(prog, sets["held"], sets["held_ref"])
            cur_probe = j[1] if (use_athanor and j is not None) else probe_lengths(prog, probes)
            cur_train, _ = mean_ratio(prog, train, train_ref, strict=False)
            if cur_train is not None:
                best_train = min(best_train, cur_train)
            commits += 1
            # only transitions count: an already-broken program staying broken is not a new event
            if old is not None and (held is None or held > old):
                regressions += 1
            if old is not None and (held is None or held > old + SEVERE_DELTA):
                severe += 1
                severe_events.append({"step": step, "old": old, "new": held, "fail": held_fail, "verdict": verdict})
            if held is None and old is not None:
                broken_commits += 1
                broken_by_kind[held_fail if held_fail in broken_by_kind else "crash"] += 1
                broken_by_verdict[verdict or "UNGATED"] = broken_by_verdict.get(verdict or "UNGATED", 0) + 1
        series["held"].append(held)
        series["committed"].append(committed)
        row.update({"committed": committed, "trail": trail, "held_ratio": held,
                    "source_sha256": hashlib.sha256(src.encode()).hexdigest()})
        if writer:
            writer.append(row)

    if out_dir:
        with open(os.path.join(out_dir, "final_self.py"), "w", encoding="utf-8") as f:
            f.write(src)
    finite = [v for v in series["held"] if v is not None]
    good = next((i + 1 for i, v in enumerate(series["held"]) if v is not None and v <= GOOD_RATIO), None)
    worst = max((math.inf if v is None else v) for v in series["held"]) if series["held"] else None
    return {"seed": seed, "mode": arm_name, "arm": {k: v for k, v in arm.items()}, "seed_held": seed_held,
            "final_held": series["held"][-1], "best_held": min(finite) if finite else None,
            "worst_held": worst, "steps_to_good": good, "commits": commits, "regressions": regressions,
            "severe_regressions": severe, "severe_events": severe_events, "broken_commits": broken_commits,
            "broken_by_kind": broken_by_kind, "broken_by_verdict": broken_by_verdict,
            "validity_rejections": validity_rejections, "proposals_invalid": proposals_invalid,
            "verdicts": counts, "final_source": src, "series": series}


# ------------------------------------------------------------- multi-seed arms
def _job(args):
    seed, name, arm, cfg, ledger_dir = args
    out = os.path.join(ledger_dir, f"{name}_seed{seed}") if ledger_dir else None
    return run_tsp(seed, arm, name, cfg, out)


WORKER_MEMORY_LIMIT_GB = 2   # 3.0: a self-edited program that allocates without bound fails with MemoryError


def _limit_memory(gb: float) -> None:
    """Cap a worker's address space so runaway allocation by the agent's own code raises MemoryError
    (scored as a crash by ``run_instance``) instead of exhausting the machine. Normal runs peak under
    100 MB. Found in 3.0 on held-out seed 3005: a validity-only program grew a list until the OOM
    killer stopped the whole pool; its results are identical under a 2 GB and a 5 GB cap."""
    try:
        import resource
        lim = int(gb * (1 << 30))
        resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
    except (ImportError, ValueError, OSError):  # non-POSIX or not permitted: run without the cap
        pass


def run_tsp_arms(seeds: Sequence[int], arms: Dict[str, Dict[str, Any]] | None = None,
                 cfg: Dict[str, Any] | None = None, workers: int = 8, ledger_dir: str | None = None,
                 memory_limit_gb: float | None = WORKER_MEMORY_LIMIT_GB):
    from concurrent.futures import ProcessPoolExecutor
    arms = arms or tsp_arms()
    jobs = [(s, n, a, cfg, ledger_dir) for n, a in arms.items() for s in seeds]
    if workers <= 1:
        runs = [_job(j) for j in jobs]
    else:
        init = (_limit_memory, (memory_limit_gb,)) if memory_limit_gb else (None, ())
        with ProcessPoolExecutor(workers, initializer=init[0], initargs=init[1]) as ex:
            runs = list(ex.map(_job, jobs))
    return {"seeds": list(seeds), "arms": {n: {k: v for k, v in a.items()} for n, a in arms.items()},
            "summary": summarize_tsp(runs, list(arms)), "runs": runs}


def _at(series, t):
    v = series[min(t, len(series)) - 1]
    return math.inf if v is None else v


def summarize_tsp(runs: List[Dict[str, Any]], names: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for n in names:
        rs = [r for r in runs if r["mode"] == n]
        T = len(rs[0]["series"]["held"])
        worst_finite = [max((v for v in r["series"]["held"] if v is not None), default=None) for r in rs]
        kinds = {k: int(sum(r["broken_by_kind"][k] for r in rs)) for k in ("crash", "timeout", "invalid")}
        reach = [r["steps_to_good"] for r in rs]
        out[n] = {
            "runs": len(rs),
            "broken_commits": int(sum(r["broken_commits"] for r in rs)), "broken_by_kind": kinds,
            "runs_broken_at_end": int(sum(r["final_held"] is None for r in rs)),
            "broken_step_fraction": float(np.mean([np.mean([v is None for v in r["series"]["held"]]) for r in rs])),
            "severe_regressions": int(sum(r["severe_regressions"] for r in rs)),
            "regressions": int(sum(r["regressions"] for r in rs)),
            "worst_committed_ratio": max(w for w in worst_finite if w is not None),
            "broken_by_verdict": {k: int(sum(r["broken_by_verdict"].get(k, 0) for r in rs))
                                  for k in ("APPROVE", "REFINE", "REJECT", "UNGATED")},
            **{f"median_held_{c}": float(np.median([_at(r["series"]["held"], c) for r in rs])) for c in CHECKPOINTS
               if c <= T},
            "median_best_held": float(np.median([math.inf if r["best_held"] is None else r["best_held"] for r in rs])),
            "median_steps_to_good": float(np.median([math.inf if x is None else x for x in reach])),
            "never_good": int(sum(x is None for x in reach)),
            "commits": int(sum(r["commits"] for r in rs)),
            "validity_rejections": int(sum(r["validity_rejections"] for r in rs)),
            "frozen_runs": int(sum(r["commits"] == 0 for r in rs)),
        }
    return out


def _f(v, d=3):
    if v is None:
        return "-"
    if isinstance(v, float) and not math.isfinite(v):
        return "broken/never"
    return f"{v:.{d}f}" if isinstance(v, float) else str(v)


def tsp_markdown(res: Dict[str, Any], title: str = "TSP self-modification arms") -> str:
    S = res["summary"]
    lines = [f"# {title}", "", f"Seeds: {res['seeds'][0]}-{res['seeds'][-1]} ({len(res['seeds'])}), "
             "metric = mean tour length / harness reference over 32 held-out instances (lower is better; "
             "1.177 = the seed program). Medians over seeds; a broken program counts as worst.", "",
             "| arm | broken commits (crash/timeout/silent-invalid) | runs broken at end | severe | worst committed "
             "ratio | held@50 | held@1000 | best | steps to <=1.05 (never) | frozen runs | % run-steps broken |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
    for n, s in S.items():
        k = s["broken_by_kind"]
        lines.append(f"| {n} | {s['broken_commits']} ({k['crash']}/{k['timeout']}/{k['invalid']}) | "
                     f"{s['runs_broken_at_end']} | {s['severe_regressions']} | {_f(s['worst_committed_ratio'])} | "
                     f"{_f(s.get('median_held_50'))} | {_f(s.get('median_held_1000'))} | {_f(s['median_best_held'])} | "
                     f"{_f(s['median_steps_to_good'], 1)} ({s['never_good']}) | {s['frozen_runs']} | "
                     f"{100 * s['broken_step_fraction']:.1f} |")
    return "\n".join(lines) + "\n"


def tsp_chart(res: Dict[str, Any], path: str, title: str = "TSP self-modification (held-out seeds)") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .arms import _color
    plt.rcParams.update({"figure.facecolor": "#0d0f18", "axes.facecolor": "#0d0f18", "axes.edgecolor": "#3a3f4d",
                         "axes.labelcolor": "#c9ced8", "xtick.color": "#9aa0a6", "ytick.color": "#9aa0a6",
                         "text.color": "#e8e8e8", "grid.color": "#1f2330", "font.size": 10})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5.2))
    names = list(res["summary"])
    for n in names:
        rs = [r for r in res["runs"] if r["mode"] == n]
        M = np.array([[math.inf if v is None else v for v in r["series"]["held"]] for r in rs])
        med = np.median(M, axis=0)
        broken = np.mean(~np.isfinite(M), axis=0)
        x = np.arange(1, M.shape[1] + 1)
        a1.plot(x, np.where(np.isfinite(med), med, np.nan), label=n, color=_color(n), lw=1.6)
        a2.plot(x, broken * 100, label=n, color=_color(n), lw=1.6)
    a1.axhline(GOOD_RATIO, ls=":", c="grey", lw=1)
    a1.set(xscale="log", xlabel="step", ylabel="median held-out ratio (lower is better)", ylim=(1.0, 1.2),
           title="held-out tour quality")
    a2.set(xscale="log", xlabel="step", ylabel="% of runs whose committed program is broken",
           title="broken programs on held-out")
    a1.grid(True); a2.grid(True)
    a1.legend(fontsize=8, facecolor="#121521", edgecolor="#3a3f4d")
    fig.suptitle(title, color="#ffd28a")
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def compact_tsp(res: Dict[str, Any]) -> Dict[str, Any]:
    keep = {k: v for k, v in res.items() if k != "runs"}
    keep["runs"] = [{k: v for k, v in r.items() if k not in ("series", "final_source")} for r in res["runs"]]
    return keep
