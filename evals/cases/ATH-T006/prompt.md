# Fixed drift tolerance freezes the TSP solver (no edit is ever committed)

Edit `config.json` (an Athanor `tsp` arm + cfg) so that, on seeds 0–15 for 1000 steps, `broken_commits <= 2`, `severe_regressions <= 10`, `frozen_runs <= 0`, `never_good <= 8` all hold. Do not edit `case.json` or `verify_config.py`.
