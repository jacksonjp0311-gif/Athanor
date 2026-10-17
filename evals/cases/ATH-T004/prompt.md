# Ungoverned self-modification breaks the program and regresses severely

Edit `config.json` (an Athanor `selfmod` arm + cfg) so that, on seeds 0–15 for 1000 steps, `broken_commits <= 2`, `severe_regressions <= 10` all hold. Do not edit `case.json` or `verify_config.py`.
