"""TSP self-modification testbed: run the arms on held-out seeds (or tuning seeds with --tuning).

    python experiments/tsp_selfmod/run.py                  # held-out seeds 0-15, carried-over arms
    python experiments/tsp_selfmod/run.py --with-tuned     # + the setting chosen in tune.py (tuning seeds only)
    python experiments/tsp_selfmod/run.py --seeds 100-115 --out /tmp/x   # any seed range
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from athanor.selfmod.tsp_experiment import (compact_tsp, run_tsp_arms, tsp_arms, tsp_chart,  # noqa: E402
                                            tsp_markdown)


def seed_range(s):
    a, _, b = s.partition("-")
    return list(range(int(a), int(b or a) + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-15")
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--out", default="docs/tsp_selfmod")
    ap.add_argument("--chart", default="docs/assets/tsp_selfmod.png")
    ap.add_argument("--with-tuned", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--ledgers", help="directory for per-run hash-chained ledgers + final programs")
    a = ap.parse_args()
    arms = tsp_arms()
    if a.with_tuned:
        with open(os.path.join(os.path.dirname(__file__), "tuned.json"), encoding="utf-8") as f:
            arms["validity+athanor-tuned"] = json.load(f)["arm"]
    seeds = seed_range(a.seeds)
    t = time.time()
    res = run_tsp_arms(seeds, arms, {"steps": a.steps}, workers=a.workers, ledger_dir=a.ledgers)
    res["config"] = {"steps": a.steps, "seconds": round(time.time() - t, 1)}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(compact_tsp(res), f, indent=1, default=float)
    md = tsp_markdown(res)
    with open(os.path.join(a.out, "results.md"), "w", encoding="utf-8") as f:
        f.write(md)
    if a.chart:
        tsp_chart(res, a.chart, f"ATHANOR on a self-modifying TSP solver · seeds {seeds[0]}–{seeds[-1]}")
    print(md)


if __name__ == "__main__":
    main()
