# Evolution Module

Recursive improvement loop and archive subsystem.

## Directory snapshot
```text
src/athanor/evolution/
├── __init__.py
├── archive.py
└── dgm_loop.py
```

## What each script does
- `dgm_loop.py` — generation loop orchestration + artifact writing.
- `archive.py` — MAP-Elites-style archive and summary stats.

## How it works together
The loop executes telemetry/proposal/verification/selection cycles, then stores coherent diversity in the archive and writes reproducibility artifacts.

> Keep this snapshot updated when loop/archive files change.
