"""Reproduce the self-modification experiment (same as `athanor selfmod`).

    python experiments/self_modify/run.py            # 16 seeds x 1000 steps
    python experiments/self_modify/run.py --ledgers  # also keep per-run ledgers + final_self.py
"""
import sys

from athanor.scripts.cli import main

if __name__ == "__main__":
    args = sys.argv[1:]
    defaults = ["--seeds", "0-15", "--steps", "1000", "--out", "docs/selfmod", "--chart", "docs/assets/selfmod.png"]
    raise SystemExit(main(["selfmod"] + defaults + args))
