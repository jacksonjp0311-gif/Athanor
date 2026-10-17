"""Multi-arm comparison and tuning helpers for the self-modification experiment."""
from __future__ import annotations

import math
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List, Sequence

import numpy as np

from .experiment import ARMS, DEFAULTS, run_selfmod

ARM_COLORS = {"ungoverned": "#7aa2ff", "validity": "#3ddc97", "athanor": "#ffb347",
              "validity+athanor": "#ff7a1a", "athanor-adaptive": "#c792ea",
              "validity+athanor-adaptive": "#ff5d9e", "validity+athanor-adaptive-τ0.75": "#ffd28a",
              "validity+athanor-conservative": "#ffd28a", "validity+athanor-tuned": "#00e5ff"}


def _color(n):
    return ARM_COLORS.get(n, "#e8e8e8")


def _job(args):
    seed, name, arm, cfg = args
    r = run_selfmod(seed, cfg=cfg, arm=arm, arm_name=name)
    r["series"] = {"test_mse": r["series"]["test_mse"], "broken": r["series"]["broken"],
                   "committed": r["series"]["committed"]}
    return r


def run_many(jobs: List[tuple], workers: int | None = None) -> List[Dict[str, Any]]:
    workers = workers or min(8, os.cpu_count() or 1)
    if workers <= 1:
        return [_job(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(_job, jobs, chunksize=1))


def _inf(v):
    return math.inf if v is None else float(v)


def summarize(rs: Sequence[Dict[str, Any]], steps: int) -> Dict[str, Any]:
    """The headline metrics used everywhere (README, algorithm card, tuning log)."""
    def med_at(t):
        return float(np.median([_inf(r["series"]["test_mse"][min(t, steps) - 1]) for r in rs]))
    finite = [v for r in rs for v in r["series"]["test_mse"] if v is not None]
    reach = [_inf(r["steps_to_1p5"]) for r in rs]
    return {
        "runs": len(rs),
        "broken_commits": int(sum(r["broken_commits"] for r in rs)),
        "severe_regressions": int(sum(r["severe_regressions"] for r in rs)),
        "worst_mse": float(max(finite)) if finite else None,
        "median_mse_100": med_at(100),
        "median_mse_final": med_at(steps),
        "median_best_mse": float(np.median([_inf(r["best_test_mse"]) for r in rs])),
        "median_steps_to_1p5": float(np.median(reach)),
        "never_reached_1p5": int(sum(math.isinf(x) for x in reach)),
        "runs_broken_at_end": int(sum(r["final_test_mse"] is None for r in rs)),
        "commits": int(sum(r["commits"] for r in rs)),
        "regressions": int(sum(r["regressions"] for r in rs)),
        "validity_rejections": int(sum(r["validity_rejections"] for r in rs)),
    }


def run_arms(seeds: Sequence[int], arms: Dict[str, Dict[str, Any]], cfg: Dict[str, Any] | None = None,
             workers: int | None = None) -> Dict[str, Any]:
    cfg = {**DEFAULTS, **(cfg or {})}
    jobs = [(s, n, a, cfg) for n, a in arms.items() for s in seeds]
    runs = run_many(jobs, workers)
    summary = {n: summarize([r for r in runs if r["mode"] == n], int(cfg["steps"])) for n in arms}
    return {"schema": "athanor.selfmod.arms/1", "seeds": list(map(int, seeds)), "config": cfg,
            "arms": arms, "summary": summary, "runs": runs}


def fmt(v, digits=3):
    if v is None:
        return "n/a"
    if isinstance(v, float) and math.isinf(v):
        return "∞"
    if isinstance(v, float):
        if abs(v) >= 1e5:
            return f"{v:.1e}"
        return f"{v:.{digits}f}"
    return str(v)


ROWS = [("Commits that broke the program", "broken_commits"),
        ("Severe regressions (>2× worse or broken)", "severe_regressions"),
        ("Worst held-out MSE ever committed", "worst_mse"),
        ("Median held-out MSE @100", "median_mse_100"),
        ("Median held-out MSE @final", "median_mse_final"),
        ("Median best-ever held-out MSE", "median_best_mse"),
        ("Median steps to MSE < 1.5", "median_steps_to_1p5"),
        ("Runs never reaching MSE < 1.5", "never_reached_1p5"),
        ("Committed self-edits", "commits")]


def arms_markdown(res: Dict[str, Any]) -> str:
    names = list(res["summary"])
    out = [f"Seeds {res['seeds'][0]}–{res['seeds'][-1]} ({len(res['seeds'])} per arm), "
           f"{res['config']['steps']} steps.", "",
           "| Metric | " + " | ".join(names) + " |", "|---|" + "---:|" * len(names)]
    for label, key in ROWS:
        out.append(f"| {label} | " + " | ".join(fmt(res["summary"][n][key]) for n in names) + " |")
    return "\n".join(out) + "\n"


def arms_chart(res: Dict[str, Any], path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.facecolor": "#0d0f18", "axes.facecolor": "#0d0f18", "axes.edgecolor": "#3a3f4d",
                         "axes.labelcolor": "#c9ced8", "xtick.color": "#9aa0a6", "ytick.color": "#9aa0a6",
                         "text.color": "#e8e8e8", "grid.color": "#1f2330", "font.size": 10})
    names = list(res["summary"])
    T = int(res["config"]["steps"])
    x = np.arange(1, T + 1)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), gridspec_kw={"width_ratios": [1.5, 1, 1]})
    ax = axes[0]
    for n in names:
        S = np.array([[np.nan if v is None else v for v in r["series"]["test_mse"]] for r in res["runs"] if r["mode"] == n])
        with np.errstate(all="ignore"):
            ax.plot(x, np.nanmedian(S, axis=0), lw=2, color=_color(n), label=n)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_ylim(0.4, 3.5)
    ax.set_title("Median held-out MSE of the current self"); ax.set_xlabel("self-edit step (log)")
    ax.grid(True); ax.legend(fontsize=8, facecolor="#121521", edgecolor="#3a3f4d")
    for ax, key, title in [(axes[1], "severe_regressions", "Severe regressions (all seeds)"),
                           (axes[2], "broken_commits", "Commits that broke the program")]:
        vals = [res["summary"][n][key] for n in names]
        bars = ax.bar(range(len(names)), vals, color=[_color(n) for n in names])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + max(vals + [1]) * 0.02, str(v), ha="center", fontsize=9)
        ax.set_xticks(range(len(names)), [n.replace("+", "+\n").replace("-adaptive", "\nadaptive").replace("-τ", "\nτ") for n in names], fontsize=7)
        ax.set_title(title); ax.grid(True, axis="y")
    fig.suptitle(f"ATHANOR self-modifying program: {len(names)} arms · held-out seeds {res['seeds'][0]}–{res['seeds'][-1]}",
                 color="#ffd28a")
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
