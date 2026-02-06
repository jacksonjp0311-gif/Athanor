# Experiments Module

Configuration loading and validation for runs.

## Directory snapshot
```text
src/athanor/experiments/
├── __init__.py
└── registry.py
```

## What each script does
- `registry.py` — resolves config inheritance and validates run parameters.

## How it works together
Config enters through this module before loop execution, ensuring invalid run settings fail fast.

> Keep this snapshot updated as experiment tooling expands.
