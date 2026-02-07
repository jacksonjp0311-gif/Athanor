# Configurations

Experiment configuration files for ATHANOR runs.

## What this folder does
This folder defines runtime control planes (thresholds, population, generations, archive bins, and output paths).

## Directory snapshot
```text
configs/
├── base.yaml
└── toy_experiment.yaml
```

## How it works with the system
- `base.yaml` provides canonical defaults.
- `toy_experiment.yaml` inherits from `base.yaml` and overrides a minimal subset for fast smoke/integration runs.

> Keep this snapshot updated when adding or removing config files.
