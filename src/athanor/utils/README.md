# Utils Module

Support utilities for observability and reproducibility.

## Directory snapshot
```text
src/athanor/utils/
├── __init__.py
├── logging.py
├── seeding.py
└── visualization.py
```

## What each script does
- `logging.py` — JSONL logging helpers.
- `seeding.py` — random seed helper utilities.
- `visualization.py` — plots and dashboard generation from run artifacts.

## How it works together
These utilities keep experiment outputs inspectable and reproducible without changing selection policy logic.

> Keep this snapshot updated as utility modules change.
