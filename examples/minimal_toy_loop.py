import json
from athanor.experiments.registry import load_config
from athanor.evolution.dgm_loop import run

cfg = load_config('configs/toy_experiment.yaml')
out = run(cfg)
print(json.dumps(out, indent=2))
