"""Minimal example: plug a self-modifying program into ATHANOR with ``athanor.govern``.

The "program" is Python source for ``f(x)``. It rewrites itself by editing its own constants
and operators, and wants to fit ``y = sin(x)`` on training points. ATHANOR only lets an edit
through if the program's behaviour on fixed probe inputs moves by a coherent amount.

    python examples/govern_quickstart.py
"""
import math
import re

import numpy as np

import athanor

X_TRAIN = np.linspace(-3, 3, 24)
Y_TRAIN = np.sin(X_TRAIN)
X_PROBE = np.linspace(-4, 4, 16)          # fixed probe inputs, wider than training (where breaks hide)
OPS = ["+", "-", "*"]


def compile_program(src):
    ns = {"math": math}
    exec(src, ns)                          # the program is its own source code
    return ns["f"]


def evaluate(src):                         # objective: training MSE (lower is better)
    f = compile_program(src)
    return float(np.mean([(f(x) - y) ** 2 for x, y in zip(X_TRAIN, Y_TRAIN)]))


def probe(src):                            # behaviour on fixed probes
    f = compile_program(src)
    return [f(x) for x in X_PROBE]


def propose(src, rng, scale):              # self-edit: nudge a constant, or swap an operator
    nums = list(re.finditer(r"-?\d+\.\d+", src))
    if nums and rng.random() < 0.8:
        m = nums[rng.integers(len(nums))]
        new = float(m.group()) + rng.normal(0, 0.2 * scale)
        return src[:m.start()] + f"{new:.4f}" + src[m.end():]
    ops = [m for m in re.finditer(r" [+\-*] ", src)]
    m = ops[rng.integers(len(ops))]
    return src[:m.start()] + f" {OPS[rng.integers(len(OPS))]} " + src[m.end():]


SCALE = float(np.std(Y_TRAIN))      # one "unit" of behaviour change: the target's spread
SEED = "def f(x):\n    return 0.1000 * x + 0.0000 * x * x * x + 0.0000\n"

if __name__ == "__main__":
    for governed in (True, False):
        r = athanor.govern(SEED, propose, evaluate, probe, steps=400, seed=0, scale=SCALE, governed=governed)
        worst_probe = max(abs(v) for v in probe(r.program))
        print(f"{'governed  ' if governed else 'ungoverned'}  train MSE {r.initial_score:.3f} -> {r.score:.3f}  "
              f"commits {r.commits:3d}  verdicts {r.counts}  max |f| on probes {worst_probe:.2f}")
    # One-off gate for a single edit:
    gov = athanor.Governor(probe, scale=SCALE)
    d = gov.judge(SEED, SEED.replace("0.1000 * x", "0.1500 * x"))
    print("single edit:", d.verdict, f"H7={d.h7:.2f}", f"mean dPhi={d.dphi_mean:.3f}")
