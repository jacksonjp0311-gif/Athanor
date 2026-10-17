"""Iterative tuning of the validity + Athanor arm on TUNING seeds (100-115) only.

Every setting in the Cartesian grid is evaluated on seeds 100-115 and appended to
docs/tuning/log.json. Held-out seeds 0-15 are never used here.

    python experiments/self_modify/tune.py --round 4 --gammas 2,4 \\
        --grid "threshold_h7=0.7;adaptive_power=2,3;adaptive_basis=best;adaptive_cap=2,4,none"

Selection rule (fixed before tuning): feasible = broken_commits <= 2 and
severe_regressions <= 10 on the 16 tuning seeds; among feasible settings minimise
median held-out MSE at step 100, tie-break median MSE at the final step.
Stop when a round improves the best feasible objective by < 2 %.
"""
import argparse, itertools, json, os, time

from athanor.selfmod.arms import run_arms

TUNE_SEEDS = list(range(100, 116))
LOG = "docs/tuning/log.json"
SAFE_BROKEN, SAFE_SEVERE = 2, 10


def feasible(s):
    return s["broken_commits"] <= SAFE_BROKEN and s["severe_regressions"] <= SAFE_SEVERE


def objective(s):
    return (s["median_mse_100"], s["median_mse_final"])


def _val(v):
    if v == "none":
        return None
    for conv in (int, float):
        try:
            return conv(v)
        except ValueError:
            pass
    return v


def parse_grid(text):
    out = {}
    for part in filter(None, (p.strip() for p in text.split(";"))):
        k, vs = part.split("=", 1)
        out[k.strip()] = [_val(v.strip()) for v in vs.split(",")]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--gammas", default="none")
    ap.add_argument("--grid", default="threshold_h7=0.7")
    ap.add_argument("--note", default="")
    ap.add_argument("--register-best", default=None, metavar="REF",
                    help="register this round's best feasible setting as a registry candidate, "
                         "e.g. selfmod/adaptive@1.2.0 (then: athanor registry promote REF)")
    ap.add_argument("--parent", default=None, help="registry parent of --register-best")
    a = ap.parse_args(argv)
    start = len(json.load(open(LOG))) if os.path.exists(LOG) else 0
    log = json.load(open(LOG)) if os.path.exists(LOG) else []
    grid = parse_grid(a.grid)
    keys = list(grid)
    for combo in itertools.product(*[grid[k] for k in keys]):
        base = dict(zip(keys, combo))
        base.setdefault("threshold_h7", 0.7)
        base["threshold_h7"] = float(base["threshold_h7"])
        base.setdefault("refine_floor", min(0.5, base["threshold_h7"]))
        for g in a.gammas.split(","):
            gamma = None if g == "none" else float(g)
            arm = {"validity": True, "athanor": True, "gamma": gamma}
            t0 = time.time()
            s = run_arms(TUNE_SEEDS, {"v+a": arm}, base)["summary"]["v+a"]
            entry = {"round": a.round, "note": a.note, "seeds": "100-115", "cfg": base, "arm": arm,
                     "summary": s, "feasible": feasible(s), "seconds": round(time.time() - t0, 1)}
            log.append(entry)
            print(json.dumps({**{k: base[k] for k in keys}, "gamma": gamma, "ok": entry["feasible"],
                              "brk": s["broken_commits"], "sev": s["severe_regressions"],
                              "m100": round(s["median_mse_100"], 3), "fin": round(s["median_mse_final"], 3),
                              "steps": s["median_steps_to_1p5"]}), flush=True)
            json.dump(log, open(LOG, "w"), indent=1)
    if a.register_best:
        register_best(log[start:], a.register_best, a.parent, a.round)


def register_best(entries, ref, parent, rnd):
    """Hand the round's winner to the versioned registry. Promotion is a separate, eval-gated step."""
    from athanor.config_registry import Registry
    ok = [e for e in entries if e["feasible"]]
    if not ok:
        print(json.dumps({"registered": None, "reason": "no feasible setting this round"}))
        return None
    best = min(ok, key=lambda e: objective(e["summary"]))
    s = best["summary"]
    entry = Registry().register(ref, {"arm": best["arm"], "cfg": best["cfg"]}, parent=parent,
                                reason=f"tune.py round {rnd}: best feasible on seeds 100-115",
                                evidence=[{"source": LOG, "round": rnd, "seeds": "100-115",
                                           "broken_commits": s["broken_commits"],
                                           "severe_regressions": s["severe_regressions"],
                                           "median_mse_100": s["median_mse_100"]}])
    print(json.dumps({"registered": ref, "spec_hash": entry["spec_hash"], "next": f"athanor registry promote {ref}"}))
    return entry


if __name__ == "__main__":
    main()
