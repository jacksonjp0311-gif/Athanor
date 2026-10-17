# TSP self-modification (transfer test, v2.6.0)

A multi-function TSP solver that rewrites its own source via AST mutation, with real crashes, deterministic
loop timeouts, silent wrong answers and held-out regressions. Used to test whether the v2.5 governor settings
transfer without retuning. Write-up: [`docs/tsp_selfmod.md`](../../docs/tsp_selfmod.md).

| script | what it does |
|---|---|
| `run.py` | runs all arms on held-out seeds 0–15 and writes `docs/tsp_selfmod/results.*` and `docs/assets/tsp_selfmod.png` (`--with-tuned` adds `tuned.json`) |
| `tune.py` | grid round on tuning seeds 100–115 and the separate tuning instance set only, logged to `docs/tsp_selfmod/tuning_log.json` |
| `shadow_gate.py` | the verdicts the gate *would* have given the edits that broke the ungoverned agent |
| `tuned.json` | the setting selected by the tuning pass (rule and round recorded inside) |
