"""Rebuild the seeded registry and eval cases from Athanor's real history (v2.7.0; TSP family added in 3.0.0).

    python evals/seed_history.py            # from the repo root, with athanor[evals] installed

Every number quoted below is a measurement already in the repo: docs/TUNING_LOG.md,
docs/selfmod/arms_results.md and the v2.1.0 commit 31c1c4a. Capture re-measures
them and refuses to save a case that does not discriminate.
"""
import json, os, sys

from athanor.config_registry import Registry
from athanor.evals.capture import capture_bug, capture_tuning
from athanor.selfmod.experiment import TUNED_ADAPTIVE, TUNED_ADAPTIVE_CONSERVATIVE

REG = Registry("configs/registry")
LIMITS = [{"metric": "broken_commits", "op": "<=", "value": 2.0},
          {"metric": "severe_regressions", "op": "<=", "value": 10.0}]  # the feasibility rule of TUNING_LOG
ADAPTIVE_ARM = {"validity": True, "athanor": True, "gamma": float(TUNED_ADAPTIVE["gamma"])}
TL = "docs/TUNING_LOG.md"


def configs():
    def reg(ref, spec, parent, reason, evidence):
        if os.path.exists(REG.entry_path(ref)):
            return
        REG.register(ref, spec, parent=parent, reason=reason, evidence=evidence)

    reg("selfmod/ungoverned@1.0.0", {"arm": {"validity": False, "athanor": False, "gamma": None}, "cfg": {}}, None,
        "2.4.0 baseline: every improving self-edit is committed, no gate.",
        [{"source": "docs/selfmod/arms_results.md", "seeds": "0-15", "broken_commits": 23, "severe_regressions": 140}])
    reg("selfmod/validity-athanor@1.0.0", {"arm": {"validity": True, "athanor": True, "gamma": None}, "cfg": {}},
        "selfmod/ungoverned@1.0.0", "2.5.0 governed arm: validity pre-gate + Athanor H7 gate, defaults (tau 0.70).",
        [{"source": "docs/selfmod/arms_results.md", "seeds": "0-15", "broken_commits": 0, "severe_regressions": 3}])
    reg("selfmod/validity-athanor@1.1.0", {"arm": {"validity": True, "athanor": True, "gamma": None},
                                           "cfg": {"threshold_h7": 0.8}},
        "selfmod/validity-athanor@1.0.0", "Tuning round 1: tighten tau to 0.80.",
        [{"source": TL, "section": "tau alone (no adaptive, round 1)", "seeds": "100-115",
          "median_mse_100": 2.971, "severe_regressions": 0, "median_steps_to_1p5": "never"}])
    reg("selfmod/adaptive@1.0.0", {"arm": ADAPTIVE_ARM, "cfg": dict(TUNED_ADAPTIVE["cfg"])},
        "selfmod/validity-athanor@1.0.0", "Tuning rounds 6-7 selected setting: adaptive drift tolerance "
        "(gamma 6, p 3, basis best, cap 6, floor 0.7, half-life 50) at tau 0.70.",
        [{"source": TL, "section": "Rounds 6-7", "seeds": "100-115", "broken_commits": 0, "severe_regressions": 8,
          "median_mse_100": 0.750}])
    reg("selfmod/adaptive@1.1.0", {"arm": ADAPTIVE_ARM, "cfg": dict(TUNED_ADAPTIVE_CONSERVATIVE["cfg"])},
        "selfmod/adaptive@1.0.0", "Conservative tau 0.75 neighbour, fixed before held-out evaluation.",
        [{"source": TL, "section": "Held-out evaluation", "seeds": "0-15", "broken_commits": 0,
          "severe_regressions": 2, "median_mse_100": 1.247}])
    reg("selfmod/adaptive-basis-current@1.0.0",
        {"arm": ADAPTIVE_ARM, "cfg": {**TUNED_ADAPTIVE["cfg"], "adaptive_basis": "current"}},
        "selfmod/adaptive@1.0.0", "Round 8 sensitivity: tolerance driven by the current (not best-so-far) error.",
        [{"source": TL, "section": "Sensitivity (round 8)", "seeds": "100-115", "severe_regressions": 30}])
    hist = {e["ref"] for e in REG.events() if e.get("event") == "reject"}
    for ref, why in [
        ("selfmod/ungoverned@1.0.0", "historical: 23 broken commits, 140 severe regressions on held-out seeds 0-15"),
        ("selfmod/validity-athanor@1.1.0", "historical: tau 0.80 freezes the agent (no structural edit passes, "
                                           "dPhi_max = 1/tau - 1 = 0.25), never reaches MSE < 1.5"),
        ("selfmod/adaptive@1.0.0", "historical: overfit; severe regressions 8 on tuning seeds -> 34 on held-out"),
        ("selfmod/adaptive-basis-current@1.0.0", "historical: positive feedback; severe 30 vs 8 on tuning seeds"),
    ]:
        if ref not in hist:
            REG.record("reject", ref, reason=why, historical=True)


BUGS = [
    ("ATH-B001", "log_jsonl wrote a literal backslash-n instead of a newline", "ATH-B001_log_jsonl_newline.py"),
    ("ATH-B002", "Config inheritance dropped nested keys (dict.update instead of deep merge)",
     "ATH-B002_config_inherit_nested.py"),
    ("ATH-B003", "REFINE retries reused other candidates' telemetry seeds", "ATH-B003_seed_overlap.py"),
    ("ATH-B004", "Two runs started in the same second shared one run folder and ledger",
     "ATH-B004_run_folder_collision.py"),
]

TUNING = [
    ("ATH-T001", "Selected adaptive setting overfit its safety on held-out seeds",
     "selfmod/adaptive@1.0.0", "selfmod/adaptive@1.1.0", range(0, 16), LIMITS,
     {"source": TL, "section": "Held-out evaluation", "finding": "severe 8 (tuning) -> 34 (held-out)"}),
    ("ATH-T002", "Tolerance on the current error is a positive feedback loop",
     "selfmod/adaptive-basis-current@1.0.0", "selfmod/adaptive@1.0.0", range(100, 116), LIMITS,
     {"source": TL, "section": "Feedback instability / round 8", "finding": "severe 30 vs 8"}),
    ("ATH-T003", "tau 0.80 is past the threshold cliff and freezes self-improvement",
     "selfmod/validity-athanor@1.1.0", "selfmod/validity-athanor@1.0.0", range(100, 116),
     LIMITS + [{"metric": "median_steps_to_1p5", "op": "<=", "value": 1000.0}],
     {"source": TL, "section": "tau alone (round 1)", "finding": "tau 0.8: MSE@100 2.971, never < 1.5"}),
    ("ATH-T004", "Ungoverned self-modification breaks the program and regresses severely",
     "selfmod/ungoverned@1.0.0", "selfmod/validity-athanor@1.0.0", range(0, 16), LIMITS,
     {"source": "docs/selfmod/arms_results.md", "finding": "broken 23 / severe 140 vs 0 / 3"}),
]


# ---------------------------------------------------------------- TSP family (3.0.0)
TSP_RES = "docs/tsp_selfmod/results.md"
_TSP_TUNED = json.load(open("experiments/tsp_selfmod/tuned.json"))["arm"]
TSP_ADAPTIVE_ARM = {k: _TSP_TUNED[k] for k in ("validity", "athanor", "gamma")}


def configs_tsp():
    def reg(ref, spec, parent, reason, evidence):
        if not os.path.exists(REG.entry_path(ref)):
            REG.register(ref, spec, parent=parent, reason=reason, evidence=evidence)

    reg("tsp/ungoverned@1.0.0", {"arm": {"validity": False, "athanor": False, "gamma": None}, "cfg": {}}, None,
        "2.6.0 TSP baseline: every improving self-edit is committed.",
        [{"source": TSP_RES, "seeds": "0-15", "broken_commits": 16, "severe_regressions": 17}])
    reg("tsp/validity-athanor@1.0.0", {"arm": {"validity": True, "athanor": True, "gamma": None}, "cfg": {}},
        "tsp/ungoverned@1.0.0", "2.6.0 fixed-tolerance validity + Athanor (tau 0.70).",
        [{"source": TSP_RES, "seeds": "0-15", "frozen_runs": 16}])
    reg("tsp/adaptive@1.0.0", {"arm": {"validity": True, "athanor": True,
                                       "gamma": float(TUNED_ADAPTIVE_CONSERVATIVE["gamma"])},
                               "cfg": dict(TUNED_ADAPTIVE_CONSERVATIVE["cfg"])},
        "tsp/validity-athanor@1.0.0", "The 2.5 conservative self-mod setting carried over to TSP unchanged.",
        [{"source": TSP_RES, "seeds": "0-15", "broken_commits": 4, "severe_regressions": 5, "never_good": 9}])
    reg("tsp/adaptive@1.1.0", {"arm": TSP_ADAPTIVE_ARM, "cfg": dict(_TSP_TUNED["cfg"])},
        "tsp/adaptive@1.0.0", "2.6.0 retune on seeds 100-115 (tau 0.78, no half-life).",
        [{"source": TSP_RES, "seeds": "0-15", "broken_commits": 2, "severe_regressions": 2}])
    reg("tsp/adaptive@1.2.0", {"arm": TSP_ADAPTIVE_ARM, "cfg": {**_TSP_TUNED["cfg"], "probe_scaling": "checks"}},
        "tsp/adaptive@1.1.0", "3.0.0: validity checks include inputs at 50/75/100 % of the deployment size "
        "(selected on tuning seeds 100-115: broken 2 -> 0, severe 4 -> 2, same median ratio).",
        [{"source": "docs/tsp_selfmod/probe_scaling_tuning.json", "seeds": "100-115", "broken_commits": 0,
          "severe_regressions": 2}])
    hist = {e["ref"] for e in REG.events() if e.get("event") == "reject"}
    for ref, why in [
        ("tsp/ungoverned@1.0.0", "historical: broke on all 16 held-out seeds (15 silent wrong answers)"),
        ("tsp/validity-athanor@1.0.0", "historical: fixed tolerance froze on all 16 held-out seeds"),
        ("tsp/adaptive@1.0.0", "historical: partial transfer; 4 broken, 5 severe, 9/16 never good"),
    ]:
        if ref not in hist:
            REG.record("reject", ref, reason=why, historical=True)


TSP_TUNING = [
    ("ATH-T005", "The 2.5 conservative setting does not transfer to the TSP solver",
     "tsp/adaptive@1.0.0", "tsp/adaptive@1.1.0", range(0, 16), LIMITS,
     {"source": TSP_RES, "finding": "carried-over: broken 4 / severe 5; retuned: 2 / 2"}),
    ("ATH-T006", "Fixed drift tolerance freezes the TSP solver (no edit is ever committed)",
     "tsp/validity-athanor@1.0.0", "tsp/adaptive@1.1.0", range(0, 16),
     LIMITS + [{"metric": "frozen_runs", "op": "<=", "value": 0.0}, {"metric": "never_good", "op": "<=", "value": 8.0}],
     {"source": TSP_RES, "finding": "frozen 16/16, never good 16 vs 0 frozen, 3 never good"}),
    ("ATH-T007", "Ungoverned TSP self-modification ships silent wrong answers",
     "tsp/ungoverned@1.0.0", "tsp/adaptive@1.1.0", range(0, 16), LIMITS,
     {"source": TSP_RES, "finding": "broken 16 (15 silent invalid) vs 2"}),
]


def cases():
    for cid, title, ver in BUGS:
        if os.path.isdir(os.path.join("evals/cases", cid)):
            continue
        r = capture_bug(case_id=cid, title=title, before_ref="ad23756", after_ref="31c1c4a",
                        verifier=os.path.join("evals/verifiers", ver))
        print(cid, r["validation"], flush=True)
    for cid, title, bad, good, seeds, limits, ev in TUNING:
        if os.path.isdir(os.path.join("evals/cases", cid)):
            continue
        r = capture_tuning(case_id=cid, title=title, bad_ref=bad, good_ref=good, seeds=list(seeds), steps=1000,
                           limits=limits, registry=REG, evidence=ev)
        print(cid, r["validation"], r["sidecar"]["recorded"]["before_violations"], flush=True)
    for cid, title, bad, good, seeds, limits, ev in TSP_TUNING:
        if os.path.isdir(os.path.join("evals/cases", cid)):
            continue
        r = capture_tuning(case_id=cid, title=title, bad_ref=bad, good_ref=good, seeds=list(seeds), steps=1000,
                           limits=limits, registry=REG, evidence=ev, attach_evidence=False)
        print(cid, r["validation"], r["sidecar"]["recorded"]["before_violations"], flush=True)


if __name__ == "__main__":
    configs()
    configs_tsp()
    cases()
