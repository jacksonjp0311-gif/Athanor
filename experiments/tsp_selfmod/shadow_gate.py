"""Counterfactual: what verdict would Athanor have given the edits that broke the *ungoverned* agent?

Replays each ungoverned run on held-out seeds 0-15 up to its first breaking commit (runs are deterministic, so
run_tsp(steps=k) returns the program after k steps), then scores that edit with the fixed-tolerance gate and
with the carried-over conservative adaptive gate. Writes docs/tsp_selfmod/shadow_gate.json.
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from athanor.agents.verifier_agent import VerifierAgent  # noqa: E402
from athanor.core.types import Candidate, TelemetryBatch  # noqa: E402
from athanor.selfmod.experiment import TUNED_ADAPTIVE_CONSERVATIVE as CONS, scheduled_tolerance  # noqa: E402
from athanor.selfmod.tsp_experiment import (KAPPA, TSP_DEFAULTS, fixed_sets, mean_ratio, probe_lengths,  # noqa: E402
                                            run_tsp, training_set, tsp_arms, tsp_trajectory)
from athanor.selfmod.tsp_program import SEED_PROGRAM, Program  # noqa: E402


def verdict(old_src, new_src, tol, tau, cfg):
    probes = fixed_sets()["probes"]
    a, b = probe_lengths(Program(old_src), probes), probe_lengths(Program(new_src), probes)
    traj = tsp_trajectory(a, b, old_src, new_src, cfg, tol=tol)
    c = VerifierAgent(threshold_h7=tau, refine_floor=0.5).step(
        Candidate(id="x", genome=np.zeros(1), telemetry=TelemetryBatch(traj=traj, meta={})))
    return c.verdict, float(c.dphi.h7)


def main():
    arm = tsp_arms()["ungoverned"]
    out = []
    for seed in range(16):
        r = run_tsp(seed, arm, "ungoverned")
        ev = next((e for e in r["severe_events"] if e["new"] is None), None)
        if ev is None:
            continue
        k = ev["step"]
        before = run_tsp(seed, arm, "ungoverned", {"steps": k})["final_source"] if k else None
        after = run_tsp(seed, arm, "ungoverned", {"steps": k + 1})["final_source"]
        before = before or SEED_PROGRAM
        ts = training_set(seed, TSP_DEFAULTS["n_train"])
        tr, _ = mean_ratio(Program(before), ts["train"], ts["train_ref"], strict=False)
        e2 = ((tr - 1.0) / KAPPA) ** 2
        # approximation (documented): the schedule basis uses the pre-edit train error, not the best-so-far
        tol = scheduled_tolerance(e2, e2, 1.0, k, CONS["gamma"], CONS["cfg"])
        fixed = verdict(before, after, 1.0, 0.7, TSP_DEFAULTS)
        cons = verdict(before, after, tol, CONS["cfg"]["threshold_h7"], TSP_DEFAULTS)
        out.append({"seed": seed, "step": k, "fail": ev["fail"], "fixed_gate": fixed[0], "fixed_h7": fixed[1],
                    "conservative_gate": cons[0], "conservative_h7": cons[1], "conservative_tol": tol})
        print(out[-1])
    summary = {g: {v: sum(o[g] == v for o in out) for v in ("APPROVE", "REFINE", "REJECT")}
               for g in ("fixed_gate", "conservative_gate")}
    print(summary)
    with open("docs/tsp_selfmod/shadow_gate.json", "w", encoding="utf-8") as f:
        json.dump({"events": out, "summary": summary}, f, indent=1)


if __name__ == "__main__":
    main()
