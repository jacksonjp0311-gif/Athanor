"""Unified benchmark across ATHANOR's three systems (``athanor bench --all``, 3.0.0).

Systems, all offline and deterministic:

* **synthetic**: the built-in evolution loop (``athanor bench``): governed vs ungoverned.
  There is no validity notion for this task, so it has no validity arm.
* **selfmod**: the 2.4 curve-fitting program that rewrites its own source.
* **tsp**: the 2.6 TSP solver that rewrites its own source.

Default seeds are the ``bench-v3`` held-out set (3000-3015, see ``athanor.seedsets``): no tuning,
gating or earlier report has used them. Arm configs are the registry entries (copied here so the
benchmark also runs from an installed wheel; a test checks they match ``configs/registry``).
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .seedsets import BENCH_SEEDS

_ADAPT_SM = {"threshold_h7": 0.75, "refine_floor": 0.5, "adaptive_power": 3.0, "adaptive_basis": "best",
             "adaptive_cap": 6.0, "adaptive_floor": 0.7, "adaptive_halflife": 50}
_ADAPT_TSP = {"threshold_h7": 0.78, "refine_floor": 0.5, "adaptive_power": 3.0, "adaptive_basis": "best",
              "adaptive_cap": 6.0, "adaptive_floor": 0.7, "adaptive_halflife": None}
_UNGOV = {"validity": False, "athanor": False, "gamma": None}
_VAL = {"validity": True, "athanor": False, "gamma": None}
_VA = {"validity": True, "athanor": True, "gamma": None}
_ADA = {"validity": True, "athanor": True, "gamma": 6.0}

# name -> (registry ref or None, {"arm", "cfg"})
SELFMOD_ARMS: Dict[str, Any] = {
    "ungoverned": ("selfmod/ungoverned@1.0.0", {"arm": _UNGOV, "cfg": {}}),
    "validity": (None, {"arm": _VAL, "cfg": {}}),
    "validity+athanor": ("selfmod/validity-athanor@1.0.0", {"arm": _VA, "cfg": {}}),
    "athanor adaptive (incumbent)": ("selfmod/adaptive@1.1.0", {"arm": _ADA, "cfg": _ADAPT_SM}),
}
TSP_ARMS: Dict[str, Any] = {
    "ungoverned": ("tsp/ungoverned@1.0.0", {"arm": _UNGOV, "cfg": {}}),
    "validity": (None, {"arm": _VAL, "cfg": {}}),
    "validity + scaled checks": (None, {"arm": _VAL, "cfg": {"probe_scaling": "checks"}}),
    "validity+athanor": ("tsp/validity-athanor@1.0.0", {"arm": _VA, "cfg": {}}),
    "athanor adaptive 2.6 (adaptive@1.1.0)": ("tsp/adaptive@1.1.0", {"arm": _ADA, "cfg": _ADAPT_TSP}),
    "athanor adaptive + scaled checks (incumbent, adaptive@1.2.0)":
        ("tsp/adaptive@1.2.0", {"arm": _ADA, "cfg": {**_ADAPT_TSP, "probe_scaling": "checks"}}),
}


def _inf(v):
    return math.inf if v is None else float(v)


def run_synthetic(seeds: Sequence[int]) -> Dict[str, Any]:
    from .bench import default_bench_config, run_bench
    t = time.time()
    res = run_bench(default_bench_config(), seeds)
    res["seconds"] = round(time.time() - t, 1)
    curves = {}
    for m in ("governed", "ungoverned"):
        M = np.array([r["series"]["pop_h7_mean"] for r in res["runs"] if r["mode"] == m])
        curves[m] = np.median(M, axis=0).tolist()
    return {"summary": res["summary"], "per_seed": res["per_seed"], "curves": curves, "seconds": res["seconds"]}


def run_selfmod(seeds: Sequence[int], steps: int = 1000, workers: Optional[int] = None) -> Dict[str, Any]:
    from .selfmod.arms import run_arms
    t = time.time()
    summary, curves = {}, {}
    for name, (_, spec) in SELFMOD_ARMS.items():
        r = run_arms(list(seeds), {name: dict(spec["arm"])}, {**spec["cfg"], "steps": steps}, workers)
        summary[name] = r["summary"][name]
        M = np.array([[_inf(v) for v in x["series"]["test_mse"]] for x in r["runs"]])
        curves[name] = np.median(M, axis=0).tolist()
    return {"summary": summary, "curves": curves, "seconds": round(time.time() - t, 1)}


def run_tsp(seeds: Sequence[int], steps: int = 1000, workers: int = 8) -> Dict[str, Any]:
    from .selfmod.tsp_experiment import run_tsp_arms
    t = time.time()
    arms = {n: {**dict(spec["arm"]), "cfg": dict(spec["cfg"])} for n, (_, spec) in TSP_ARMS.items()}
    r = run_tsp_arms(list(seeds), arms, {"steps": steps}, workers=workers)
    curves = {}
    for n in arms:
        M = np.array([[_inf(v) for v in x["series"]["held"]] for x in r["runs"] if x["mode"] == n])
        curves[n] = np.median(M, axis=0).tolist()
    return {"summary": r["summary"], "curves": curves, "seconds": round(time.time() - t, 1)}


def run_all(seeds: Sequence[int] = BENCH_SEEDS, steps: int = 1000, workers: int = 8,
            systems: Sequence[str] = ("synthetic", "selfmod", "tsp")) -> Dict[str, Any]:
    from . import __version__
    from .seedsets import classify
    out: Dict[str, Any] = {"schema": "athanor.bench_all/1", "athanor_version": __version__,
                           "seeds": [int(s) for s in seeds], "seed_sets": sorted(classify(seeds)), "steps": steps,
                           "systems": {}}
    if "synthetic" in systems:
        out["systems"]["synthetic"] = run_synthetic(seeds)
    if "selfmod" in systems:
        out["systems"]["selfmod"] = run_selfmod(seeds, steps, workers)
    if "tsp" in systems:
        out["systems"]["tsp"] = run_tsp(seeds, steps, workers)
    out["arms"] = {"selfmod": {n: {"registry": ref, **spec} for n, (ref, spec) in SELFMOD_ARMS.items()},
                   "tsp": {n: {"registry": ref, **spec} for n, (ref, spec) in TSP_ARMS.items()}}
    return out


# ------------------------------------------------------------------ rendering
def _f(v, d=3):
    if v is None:
        return "n/a"
    if isinstance(v, float) and math.isinf(v):
        return "never"
    if isinstance(v, float):
        return f"{v:.{d}f}"
    return str(v)


def render_markdown(res: Dict[str, Any]) -> str:
    S = res["systems"]
    seeds = res["seeds"]
    L = [f"# ATHANOR {res['athanor_version']} unified benchmark", "",
         f"Seeds {seeds[0]}–{seeds[-1]} ({len(seeds)} per arm; seed set: {', '.join(res['seed_sets']) or 'unnamed'}), "
         f"{res['steps']} steps for the self-modifying systems. Medians over seeds unless stated; "
         "a broken program counts as worst.", "",
         "Reproduce: `athanor bench --all` (about 2–3 minutes on 8 cores).", ""]
    L += ["## Headline", "",
          "| system | arm | unsafe commits¹ | severe regressions² | quality early³ | quality final³ | never reached target⁴ | frozen runs |",
          "|---|---|---:|---:|---:|---:|---:|---:|"]
    if "synthetic" in S:
        for m in ("ungoverned", "governed"):
            s = S["synthetic"]["summary"][m]
            L.append(f"| synthetic | {m} | {s['promoted_unapproved']} | n/a | n/a | H7 {s['tail_h7_mean']:.3f} | n/a | n/a |")
    if "selfmod" in S:
        for n, s in S["selfmod"]["summary"].items():
            L.append(f"| selfmod | {n} | {s['broken_commits']} | {s['severe_regressions']} | MSE {_f(s['median_mse_100'])} | "
                     f"MSE {_f(s['median_mse_final'])} | {s['never_reached_1p5']} | n/a |")
    if "tsp" in S:
        for n, s in S["tsp"]["summary"].items():
            L.append(f"| tsp | {n} | {s['broken_commits']} | {s['severe_regressions']} | ratio {_f(s.get('median_held_50'))} | "
                     f"ratio {_f(s.get('median_held_1000', s.get('median_held_50')))} | {s['never_good']} | {s['frozen_runs']} |")
    L += ["",
          "¹ selfmod/tsp: committed self-edits that broke the program on held-out inputs (crash, timeout, non-finite "
          "or invalid output); synthetic: parent promotions of a non-APPROVED child (summed over seeds).",
          "² selfmod: held-out MSE more than 2× worse or broken; tsp: held-out tour ratio worse by more than 0.05 or broken.",
          "³ selfmod: median held-out MSE at step 100 / final (lower is better); tsp: median held-out tour length ÷ "
          "harness reference at step 50 / final (lower is better; the seed program is 1.177); synthetic: mean "
          "population H7 over the last 10 generations (higher is better).",
          "⁴ selfmod: runs that never reached MSE < 1.5; tsp: runs that never reached ratio ≤ 1.05.", ""]
    if "synthetic" in S:
        G, U = S["synthetic"]["summary"]["governed"], S["synthetic"]["summary"]["ungoverned"]
        p = S["synthetic"]["per_seed"]
        L += ["## Synthetic evolution loop", "", "| metric | governed | ungoverned |", "|---|---:|---:|",
              f"| mean H7, last 10 gens | {G['tail_h7_mean']:.3f} | {U['tail_h7_mean']:.3f} |",
              f"| median ΔΦ, last 10 gens | {G['tail_dphi_median']:.3f} | {U['tail_dphi_median']:.3f} |",
              f"| worst generation ΔΦ | {G['max_dphi_worst']:.3f} | {U['max_dphi_worst']:.3f} |",
              f"| parent promotions | {G['promotions']} | {U['promotions']} |",
              f"| promotions of non-APPROVED parents | {G['promoted_unapproved']} | {U['promoted_unapproved']} |", "",
              f"Per seed: governed H7 higher on {p['h7_governed_higher']}, ungoverned higher on "
              f"{p['h7_ungoverned_higher']}, tied on {p['h7_tied']}.", ""]
    if "selfmod" in S:
        L += ["## Self-modifying curve-fitting program", "",
              "| arm | broken | severe | MSE@100 | MSE@final | best-ever MSE | steps to MSE<1.5 | never | commits |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for n, s in S["selfmod"]["summary"].items():
            L.append(f"| {n} | {s['broken_commits']} | {s['severe_regressions']} | {_f(s['median_mse_100'])} | "
                     f"{_f(s['median_mse_final'])} | {_f(s.get('median_best_mse'))} | {_f(s['median_steps_to_1p5'], 1)} | "
                     f"{s['never_reached_1p5']} | {s['commits']} |")
        L.append("")
    if "tsp" in S:
        L += ["## Self-modifying TSP solver", "",
              "| arm | broken (crash/timeout/invalid) | severe | ratio@50 | ratio@final | best | steps to ≤1.05 | never | frozen | commits |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for n, s in S["tsp"]["summary"].items():
            k = s["broken_by_kind"]
            L.append(f"| {n} | {s['broken_commits']} ({k['crash']}/{k['timeout']}/{k['invalid']}) | {s['severe_regressions']} | "
                     f"{_f(s.get('median_held_50'))} | {_f(s.get('median_held_1000'))} | {_f(s['median_best_held'])} | "
                     f"{_f(s['median_steps_to_good'], 1)} | {s['never_good']} | {s['frozen_runs']} | {s['commits']} |")
        L.append("")
    return "\n".join(L) + "\n"


COLORS = {"ungoverned": "#7aa2ff", "governed": "#ffb347", "validity": "#9be37b", "validity + scaled checks": "#4fd1c5",
          "validity+athanor": "#c084fc"}


def _color(n: str) -> str:
    if n in COLORS:
        return COLORS[n]
    return "#ff6b6b" if "scaled" in n else "#ffb347"


def render_chart(res: Dict[str, Any], path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.facecolor": "#0d0f18", "axes.facecolor": "#0d0f18", "axes.edgecolor": "#3a3f4d",
                         "axes.labelcolor": "#c9ced8", "xtick.color": "#9aa0a6", "ytick.color": "#9aa0a6",
                         "text.color": "#e8e8e8", "grid.color": "#1f2330", "font.size": 9})
    S = res["systems"]
    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    if "synthetic" in S:
        ax = axes[0]
        for n, c in S["synthetic"]["curves"].items():
            ax.plot(np.arange(1, len(c) + 1), c, label=n, color=_color(n), lw=1.8)
        ax.set(xlabel="generation", ylabel="median population H7 (higher = more coherent)", title="synthetic loop",
               ylim=(0, 1.02))
    if "selfmod" in S:
        ax = axes[1]
        for n, c in S["selfmod"]["curves"].items():
            y = np.array(c, dtype=float)
            ax.plot(np.arange(1, len(y) + 1), np.where(np.isfinite(y), y, np.nan), label=n, color=_color(n), lw=1.6)
        ax.set(xscale="log", yscale="log", xlabel="step", ylabel="median held-out MSE (lower is better)",
               title="self-modifying curve fit")
    if "tsp" in S:
        ax = axes[2]
        for n, c in S["tsp"]["curves"].items():
            y = np.array(c, dtype=float)
            ax.plot(np.arange(1, len(y) + 1), np.where(np.isfinite(y), y, np.nan), label=n, color=_color(n), lw=1.6,
                    ls="--" if "2.6" in n else "-")
        ax.axhline(1.05, ls=":", c="grey", lw=1)
        ax.set(xscale="log", xlabel="step", ylabel="median held-out tour ratio (lower is better; gaps = broken)",
               title="self-modifying TSP solver", ylim=(1.0, 1.2))
    for ax in axes:
        ax.grid(True)
        ax.legend(fontsize=7, facecolor="#121521", edgecolor="#3a3f4d")
    s = res["seeds"]
    fig.suptitle(f"ATHANOR {res['athanor_version']} · unified benchmark · held-out seeds {s[0]}–{s[-1]}", color="#ffd28a")
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def write(res: Dict[str, Any], out_dir: str, chart: Optional[str] = None) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    slim = {k: v for k, v in res.items() if k != "systems"}
    slim["systems"] = {k: {kk: vv for kk, vv in v.items() if kk != "curves"} for k, v in res["systems"].items()}
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(slim, f, indent=1, default=float)
    with open(os.path.join(out_dir, "results.md"), "w", encoding="utf-8") as f:
        f.write(render_markdown(res))
    chart = chart or os.path.join(out_dir, "benchmark_all.png")
    render_chart(res, chart)
    return {"results": os.path.join(out_dir, "results.json"), "markdown": os.path.join(out_dir, "results.md"),
            "chart": chart}
