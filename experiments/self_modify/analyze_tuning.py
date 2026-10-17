"""Analyse docs/tuning/log.json: Pareto frontier, fitted trade-off, sensitivity, generalisation gap.

Writes docs/tuning/analysis.json and docs/assets/tuning_pareto.png. Uses only logged measurements
(tuning seeds 100-115) and docs/selfmod/arms_results.json (held-out seeds 0-15).
"""
import json, math, os

import numpy as np

LOG = "docs/tuning/log.json"
HELD = "docs/selfmod/arms_results.json"


def pareto(points):
    """Indices of points not dominated in (speed=m100 lower, severe lower)."""
    idx = []
    for i, (a, b) in enumerate(points):
        if not any((c <= a and d <= b) and (c < a or d < b) for j, (c, d) in enumerate(points) if j != i):
            idx.append(i)
    return sorted(idx, key=lambda i: points[i][0])


def spearman(x, y):
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])


def main():
    log = json.load(open(LOG))
    tuned = [e for e in log if e["round"] >= 1]
    pts = [(e["summary"]["median_mse_100"], e["summary"]["severe_regressions"]) for e in tuned]
    front = pareto(pts)
    m100 = np.array([p[0] for p in pts]); sev = np.array([p[1] for p in pts], float)
    # fitted trade-off on the frontier: log(severe+1) = a + b * log(m100)
    uniq = sorted({(round(pts[i][0], 6), pts[i][1]) for i in front})
    fx = np.log([u[0] for u in uniq]); fy = np.log([u[1] + 1 for u in uniq])
    b, a = np.polyfit(fx, fy, 1) if len(front) >= 2 else (float("nan"), float("nan"))
    # adaptive-only correlation of speed vs safety
    ad = [i for i, e in enumerate(tuned) if e["arm"]["gamma"] is not None]
    rho = spearman(m100[ad], sev[ad]) if len(ad) > 2 else None
    # tau sweep without adaptive (round 1)
    tau_sweep = sorted([(e["cfg"]["threshold_h7"], e["summary"]["median_mse_100"], e["summary"]["severe_regressions"],
                         e["summary"]["median_steps_to_1p5"]) for e in tuned
                        if e["round"] == 1 and e["arm"]["gamma"] is None])
    best_per_round = {}
    for e in tuned:
        if e["feasible"]:
            r = e["round"]; v = e["summary"]["median_mse_100"]
            if r not in best_per_round or v < best_per_round[r]["m100"]:
                best_per_round[r] = {"m100": v, "final": e["summary"]["median_mse_final"], "cfg": e["cfg"],
                                     "gamma": e["arm"]["gamma"], "severe": e["summary"]["severe_regressions"]}
    running, trace = math.inf, []
    for r in sorted({e["round"] for e in tuned}):
        if r in best_per_round:
            running = min(running, best_per_round[r]["m100"])
        trace.append({"round": r, "best_feasible_m100_so_far": None if math.isinf(running) else running,
                      "configs": sum(1 for e in tuned if e["round"] == r),
                      "feasible": sum(1 for e in tuned if e["round"] == r and e["feasible"])})
    out = {"n_configs": len(tuned), "frontier": [{"m100": pts[i][0], "severe": pts[i][1], "cfg": tuned[i]["cfg"],
                                                  "gamma": tuned[i]["arm"]["gamma"], "round": tuned[i]["round"]} for i in front],
           "frontier_fit": {"model": "log(severe+1) = a + b*log(m100), fitted on unique frontier points",
                            "a": float(a), "b": float(b), "points": len(uniq)},
           "spearman_m100_vs_severe_adaptive": rho, "tau_sweep_nonadaptive": tau_sweep,
           "best_feasible_per_round": best_per_round, "plateau_trace": trace}
    json.dump(out, open("docs/tuning/analysis.json", "w"), indent=1)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.facecolor": "#0d0f18", "axes.facecolor": "#0d0f18", "axes.edgecolor": "#3a3f4d",
                         "axes.labelcolor": "#c9ced8", "xtick.color": "#9aa0a6", "ytick.color": "#9aa0a6",
                         "text.color": "#e8e8e8", "grid.color": "#1f2330", "font.size": 10})
    fig, ax = plt.subplots(figsize=(10, 6.2))
    feas = np.array([e["feasible"] for e in tuned])
    ax.scatter(m100[~feas], sev[~feas] + 1, s=18, color="#5a6170", label="tuning configs (infeasible)")
    ax.scatter(m100[feas], sev[feas] + 1, s=26, color="#3ddc97", label="tuning configs (feasible: broken≤2, severe≤10)")
    fxs = [pts[i][0] for i in front]; fys = [pts[i][1] + 1 for i in front]
    ax.step(fxs, fys, where="post", color="#ffb347", lw=1.5, label="Pareto frontier (tuning seeds)")
    base = {e.get("arm_name"): e["summary"] for e in log if e["round"] == 0}
    for n, mk in [("ungoverned", "s"), ("validity", "D"), ("athanor", "^"), ("validity+athanor", "v")]:
        if n in base:
            ax.scatter(base[n]["median_mse_100"], base[n]["severe_regressions"] + 1, marker=mk, s=70,
                       facecolors="none", edgecolors="#7aa2ff", lw=1.5)
            ax.annotate(f"{n} (tuning)", (base[n]["median_mse_100"], base[n]["severe_regressions"] + 1),
                        textcoords="offset points", xytext=(6, 4 if n != "validity" else -12), fontsize=8, color="#7aa2ff")
    if os.path.exists(HELD):
        H = json.load(open(HELD))["summary"]
        for n in ("ungoverned", "validity+athanor", "validity+athanor-adaptive", "validity+athanor-adaptive-τ0.75"):
            if n in H:
                ax.scatter(H[n]["median_mse_100"], H[n]["severe_regressions"] + 1, marker="*", s=160, color="#ff5d9e")
                ax.annotate(f"{n} (held-out)", (H[n]["median_mse_100"], H[n]["severe_regressions"] + 1),
                            textcoords="offset points", xytext=(6, -10), fontsize=8, color="#ff5d9e")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("median held-out MSE after 100 steps (lower = faster)")
    ax.set_ylabel("severe regressions + 1, 16 seeds (lower = safer)")
    ax.set_title(f"Speed-safety trade-off: {len(tuned)} tuning configs (seeds 100–115) + held-out results (seeds 0–15)")
    ax.grid(True, which="both"); ax.legend(fontsize=8, facecolor="#121521", edgecolor="#3a3f4d", loc="upper right")
    fig.tight_layout(); fig.savefig("docs/assets/tuning_pareto.png", dpi=110); plt.close(fig)
    print(json.dumps({k: out[k] for k in ("n_configs", "frontier_fit", "spearman_m100_vs_severe_adaptive", "plateau_trace")}, indent=1))
    for f in out["frontier"]:
        print(round(f["m100"], 3), f["severe"], f["gamma"], f["round"], f["cfg"])


if __name__ == "__main__":
    main()
