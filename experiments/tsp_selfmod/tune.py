"""Small tuning pass for the TSP testbed: tuning seeds 100-115 and a separate tuning instance set only.

    python experiments/tsp_selfmod/tune.py --round 1 --grid "threshold_h7=0.70,0.75;adaptive_halflife=50,200,0;adaptive_cap=6,12"

Every config is the validity+athanor adaptive arm (gamma 6, p 3, basis best, floor 0.7) with the listed
overrides (adaptive_halflife=0 means no decay). Feasible = broken commits <= 2 and severe regressions <= 10
summed over the 16 tuning seeds (the 2.5 rule, unchanged). Objective = minimise median ratio@50, tie-break
median ratio@1000. Results are appended to docs/tsp_selfmod/tuning_log.json. Held-out seeds 0-15 and the
held-out instances are never touched here.
"""
import argparse
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from athanor.selfmod.experiment import TUNED_ADAPTIVE_CONSERVATIVE  # noqa: E402
from athanor.selfmod.tsp_experiment import run_tsp_arms  # noqa: E402

LOG = "docs/tsp_selfmod/tuning_log.json"


def parse_grid(g):
    keys, vals = [], []
    for part in g.split(";"):
        k, _, v = part.partition("=")
        keys.append(k.strip())
        vals.append([float(x) if "." in x else int(x) for x in v.split(",")])
    return [dict(zip(keys, c)) for c in itertools.product(*vals)]


def feasible(s):
    return s["broken_commits"] <= 2 and s["severe_regressions"] <= 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--grid", required=True)
    ap.add_argument("--seeds", default="100-115")
    ap.add_argument("--steps", type=int, default=1000)
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split("-"))
    seeds = list(range(lo, hi + 1))
    assert min(seeds) >= 100, "tuning must use seeds disjoint from held-out 0-15"
    arms = {}
    for over in parse_grid(a.grid):
        cfg = {**TUNED_ADAPTIVE_CONSERVATIVE["cfg"], **over}
        if cfg.get("adaptive_halflife") == 0:
            cfg["adaptive_halflife"] = None
        name = ",".join(f"{k}={v}" for k, v in over.items())
        arms[name] = {"validity": True, "athanor": True, "gamma": TUNED_ADAPTIVE_CONSERVATIVE["gamma"], "cfg": cfg}
    res = run_tsp_arms(seeds, arms, {"steps": a.steps, "eval_set": "tuning"})
    rows = []
    for name, s in res["summary"].items():
        rows.append({"round": a.round, "config": name, "arm": arms[name], "feasible": feasible(s),
                     **{k: s[k] for k in ("broken_commits", "severe_regressions", "median_held_50",
                                          "median_held_1000", "median_best_held", "median_steps_to_good",
                                          "never_good", "frozen_runs", "runs_broken_at_end")}})
    log = json.load(open(LOG)) if os.path.exists(LOG) else []
    log = [r for r in log if r["round"] != a.round] + rows
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=1, default=float)
    for r in sorted(rows, key=lambda r: (not r["feasible"], r["median_held_50"], r["median_held_1000"])):
        print(f"{r['config']:<60} feas={r['feasible']!s:<5} broken={r['broken_commits']:<3} severe={r['severe_regressions']:<3} "
              f"@50={r['median_held_50']:.3f} @1000={r['median_held_1000']:.3f} never={r['never_good']} frozen={r['frozen_runs']}")


if __name__ == "__main__":
    main()
