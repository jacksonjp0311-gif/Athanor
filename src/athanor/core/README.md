# Core Module

Foundational math, telemetry primitives, and data types.

## Directory snapshot
```text
src/athanor/core/
├── __init__.py
├── coherence.py
├── telemetry.py
└── types.py
```

## What each script does
- `coherence.py` — ΔΦ estimators, coherence transforms, H7, and extended H20/H44 helpers.
- `telemetry.py` — trajectory capture helpers.
- `types.py` — dataclasses and shared structures.

## How it works together
Trajectories are converted to drift (`delta_phi`), transformed into coherence (`C`), and summarized into horizon/stability metrics consumed by higher layers.

> Keep this snapshot updated as the core API changes.
