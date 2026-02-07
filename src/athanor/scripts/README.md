# Package Scripts Module

Packaged command-layer entrypoints.

## Directory snapshot
```text
src/athanor/scripts/
├── __init__.py
└── cli.py
```

## What each script does
- `cli.py` — `athanor` executable adapter from config path to run loop.

## How it works together
CLI receives config path, loads validated config, executes loop, prints JSON summary.

> Keep this snapshot updated as command interfaces evolve.
