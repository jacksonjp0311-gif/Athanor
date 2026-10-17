# tau 0.80 is past the threshold cliff and freezes self-improvement

Edit `config.json` (an Athanor `selfmod` arm + cfg) so that, on seeds 100–115 for 1000 steps, `broken_commits <= 2`, `severe_regressions <= 10`, `median_steps_to_1p5 <= 1000` all hold. Do not edit `case.json` or `verify_config.py`.
