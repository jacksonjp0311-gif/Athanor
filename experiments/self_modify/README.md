# Self-modifying program experiment

A small, offline, deterministic agent whose "self" is the Python source of `f(x)`. Each step it parses its own source with `ast`, mutates it, writes the new source back, compiles it and runs it. ATHANOR gates each self-edit.

- Code: [`src/athanor/selfmod/`](../../src/athanor/selfmod/) (`agent.py` = the self-modifying program, `experiment.py` = task, ΔΦ definition, governed/ungoverned loop, results)
- Run: `python experiments/self_modify/run.py` or `athanor selfmod --seeds 0-15 --steps 1000`
- Write-up and results: [`docs/selfmod.md`](../../docs/selfmod.md)
