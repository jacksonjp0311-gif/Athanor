"""Governed vs. ungoverned comparison (``athanor bench``).

Runs the same self-modification task twice per seed: once with the governor
(verdicts gate REFINE retries and parent promotion) and once without it
(``governor.enabled = false``: verdicts are measured and ledgered, but the
best-fitness child always becomes the parent). Per-generation population means
of ΔΦ, C and H7 come from each run's ``decision_record.json``.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
from typing import Any, Dict, List, Sequence

import numpy as np

from .evolution.dgm_loop import run as run_loop
from .experiments.registry import validate_config

MODES = ("governed", "ungoverned")

# Built-in copy of configs/bench.yaml (merged over defaults) so `athanor bench`
# works from an installed wheel without the repo's configs/ folder.
DEFAULT_BENCH_OVERRIDES: Dict[str, Any] = {
    "alpha": 1.0, "generations": 40, "population": 12,
    "proposer_sigma": 0.5, "proposer_step_cap": 2.0,
    "archive": {"bins": [16, 16], "novelty_eps": 0.02}, "backend": "symbolic",
}


def default_bench_config() -> Dict[str, Any]:
    return validate_config(copy.deepcopy(DEFAULT_BENCH_OVERRIDES))
TAIL = 10  # summary window: last N generations


def _one(cfg: Dict[str, Any], seed: int, governed: bool, out_dir: str) -> Dict[str, Any]:
    c = copy.deepcopy(cfg)
    c["seed"] = int(seed)
    c["governor"] = {"enabled": bool(governed)}
    c.setdefault("run", {})["out_dir"] = out_dir
    c["run"].pop("tag", None)
    out = run_loop(validate_config(c))
    with open(os.path.join(out["run_path"], "decision_record.json"), encoding="utf-8") as f:
        rec = json.load(f)
    L = rec["lineage"]
    series = {k: [float(x[k]) for x in L] for k in ("pop_dphi_mean", "pop_C_mean", "pop_h7_mean")}
    tail = slice(-min(TAIL, len(L)), None)
    promoted_unapproved = sum(1 for x in L if x["promoted"] and x["best_verdict"] != "APPROVE")
    return {
        "seed": int(seed),
        "mode": "governed" if governed else "ungoverned",
        "run_digest": out["run_digest"],
        "verdict_counts": rec["verdict_counts"],
        "promotions": rec["promotions"],
        "promoted_unapproved": promoted_unapproved,
        "tail_h7": float(np.mean(series["pop_h7_mean"][tail])),
        "tail_C": float(np.mean(series["pop_C_mean"][tail])),
        "tail_dphi": float(np.mean(series["pop_dphi_mean"][tail])),
        "max_dphi": float(np.max(series["pop_dphi_mean"])),
        "series": series,
    }


def run_bench(cfg: Dict[str, Any], seeds: Sequence[int], work_dir: str | None = None) -> Dict[str, Any]:
    tmp = None
    if work_dir is None:
        tmp = tempfile.TemporaryDirectory()
        work_dir = tmp.name
    try:
        runs = [_one(cfg, s, m == "governed", os.path.join(work_dir, m)) for s in seeds for m in MODES]
    finally:
        if tmp is not None:
            tmp.cleanup()

    summary: Dict[str, Any] = {}
    for m in MODES:
        rs = [r for r in runs if r["mode"] == m]
        vc = {k: int(sum(r["verdict_counts"].get(k, 0) for r in rs)) for k in ("APPROVE", "REFINE", "REJECT")}
        summary[m] = {
            "tail_h7_mean": float(np.mean([r["tail_h7"] for r in rs])),
            "tail_C_mean": float(np.mean([r["tail_C"] for r in rs])),
            "tail_dphi_median": float(np.median([r["tail_dphi"] for r in rs])),
            "tail_dphi_mean": float(np.mean([r["tail_dphi"] for r in rs])),
            "max_dphi_worst": float(np.max([r["max_dphi"] for r in rs])),
            "verdict_counts": vc,
            "promotions": int(sum(r["promotions"] for r in rs)),
            "promoted_unapproved": int(sum(r["promoted_unapproved"] for r in rs)),
        }
    g = {r["seed"]: r for r in runs if r["mode"] == "governed"}
    u = {r["seed"]: r for r in runs if r["mode"] == "ungoverned"}
    eps = 1e-9
    per_seed = {
        "h7_governed_higher": sum(g[s]["tail_h7"] > u[s]["tail_h7"] + eps for s in seeds),
        "h7_ungoverned_higher": sum(u[s]["tail_h7"] > g[s]["tail_h7"] + eps for s in seeds),
        "h7_tied": sum(abs(g[s]["tail_h7"] - u[s]["tail_h7"]) <= eps for s in seeds),
    }
    return {"schema": "athanor.bench/1", "seeds": list(map(int, seeds)), "tail_generations": TAIL,
            "config": cfg, "summary": summary, "per_seed": per_seed, "runs": runs}


def render_markdown(res: Dict[str, Any]) -> str:
    s, n = res["summary"], len(res["seeds"])
    G, U = s["governed"], s["ungoverned"]
    rows = [
        ("Mean H7, last %d gens" % res["tail_generations"], f"{G['tail_h7_mean']:.3f}", f"{U['tail_h7_mean']:.3f}"),
        ("Mean C, last %d gens" % res["tail_generations"], f"{G['tail_C_mean']:.3f}", f"{U['tail_C_mean']:.3f}"),
        ("Median ΔΦ, last %d gens" % res["tail_generations"], f"{G['tail_dphi_median']:.3f}", f"{U['tail_dphi_median']:.3f}"),
        ("Mean ΔΦ, last %d gens" % res["tail_generations"], f"{G['tail_dphi_mean']:.3f}", f"{U['tail_dphi_mean']:.3f}"),
        ("Worst generation ΔΦ (any seed)", f"{G['max_dphi_worst']:.3f}", f"{U['max_dphi_worst']:.3f}"),
        ("APPROVE / REFINE / REJECT (final verdicts)",
         "{APPROVE} / {REFINE} / {REJECT}".format(**G["verdict_counts"]),
         "{APPROVE} / {REFINE} / {REJECT}".format(**U["verdict_counts"])),
        ("Parent promotions", str(G["promotions"]), str(U["promotions"])),
        ("Promotions of non-APPROVED parents", str(G["promoted_unapproved"]), str(U["promoted_unapproved"])),
    ]
    out = [f"Seeds: {res['seeds']} ({n} runs per mode). Population means per generation.", "",
           "| Metric | Governed | Ungoverned |", "|---|---:|---:|"]
    out += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    p = res["per_seed"]
    out += ["", f"Per seed (mean H7 over the last {res['tail_generations']} gens): governed higher on "
            f"{p['h7_governed_higher']}/{n}, ungoverned higher on {p['h7_ungoverned_higher']}/{n}, tied on {p['h7_tied']}/{n}.",
            "", "| Seed | Governed H7 | Ungoverned H7 | Governed ΔΦ | Ungoverned ΔΦ |", "|---:|---:|---:|---:|---:|"]
    by = {(r["seed"], r["mode"]): r for r in res["runs"]}
    for sd in res["seeds"]:
        g, u = by[(sd, "governed")], by[(sd, "ungoverned")]
        out.append(f"| {sd} | {g['tail_h7']:.3f} | {u['tail_h7']:.3f} | {g['tail_dphi']:.3f} | {u['tail_dphi']:.3f} |")
    return "\n".join(out) + "\n"


def render_chart(res: Dict[str, Any], path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"governed": "#ffb347", "ungoverned": "#7aa2ff"}
    plt.rcParams.update({"figure.facecolor": "#0d0f18", "axes.facecolor": "#0d0f18", "axes.edgecolor": "#3a3f4d",
                         "axes.labelcolor": "#c9ced8", "xtick.color": "#9aa0a6", "ytick.color": "#9aa0a6",
                         "text.color": "#e8e8e8", "grid.color": "#1f2330", "font.size": 10})
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.2))
    panels = [("pop_dphi_mean", "Drift ΔΦ (population mean, log)", True),
              ("pop_C_mean", "Coherence C (population mean)", False),
              ("pop_h7_mean", "Horizon H7 (population mean)", False)]
    for ax, (key, title, log) in zip(axes.flat, panels):
        for m in MODES:
            S = np.array([r["series"][key] for r in res["runs"] if r["mode"] == m])
            x = np.arange(S.shape[1])
            med = np.median(S, axis=0)
            ax.fill_between(x, S.min(axis=0), S.max(axis=0), color=colors[m], alpha=0.15, linewidth=0)
            ax.plot(x, med, color=colors[m], linewidth=2, label=f"{m} (median, min–max band)")
        if log:
            ax.set_yscale("log")
        if key == "pop_h7_mean":
            ax.axhline(float(res["config"].get("threshold_h7", 0.7)), color="#ff5d5d", linestyle="--", linewidth=1, label="τ")
        ax.set_title(title)
        ax.set_xlabel("generation")
        ax.grid(True)
        ax.legend(loc="best", fontsize=8, facecolor="#121521", edgecolor="#3a3f4d")
    ax = axes.flat[3]
    labels = ("APPROVE", "REFINE", "REJECT")
    x = np.arange(3)
    for k, m in enumerate(MODES):
        vals = [res["summary"][m]["verdict_counts"][l] for l in labels]
        ax.bar(x + (k - 0.5) * 0.38, vals, width=0.38, color=colors[m], label=m)
    ax.set_xticks(x, labels)
    ax.set_title("Final verdicts (all seeds)")
    ax.grid(True, axis="y")
    ax.legend(fontsize=8, facecolor="#121521", edgecolor="#3a3f4d")
    fig.suptitle(f"ATHANOR: governed vs ungoverned · seeds {res['seeds'][0]}–{res['seeds'][-1]}", color="#ffd28a")
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
