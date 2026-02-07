# Data

Runtime output root for generated experiment artifacts.

## Directory snapshot
```text
data/
└── archives/
```

## How it works with the system
`run.out_dir` in config points here by default; each execution writes an immutable `run_*` folder under `data/archives/`.

> Keep this snapshot updated when storage structure changes.
