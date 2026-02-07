# ATHANOR

**Coherence-Gated Darwin Gödel Agents**  
*A stability governor for recursive self-improvement experiments.*

ATHANOR is a research-grade Python framework for running multi-agent evolutionary loops where candidate self-modifications are only admitted when they preserve measured coherence.

---

## Table of Contents
- [Overview](#overview)
- [Key Concepts](#key-concepts)
- [System Loop](#system-loop)
- [Quickstart](#quickstart)
- [Configuration](#configuration)
- [Run Artifacts](#run-artifacts)
- [Repository Structure](#repository-structure)
- [Documentation & Charters](#documentation--charters)
- [Testing](#testing)
- [Scope & Intended Use](#scope--intended-use)
- [License](#license)

---

## Overview
ATHANOR implements a coherence-gated evolutionary loop:

**Telemetry → Propose → Verify → Select → Archive → Ledger**

The verifier acts as a stability guardrail. Candidate updates are accepted, refined, or rejected based on H₇ thresholds.

---

## Key Concepts
- **ΔΦ**: local residual drift estimator over a trajectory.
- **C = 1 / (1 + |ΔΦ|)**: local coherence derived from drift magnitude.
- **H₇ = mean(C ≥ threshold)**: coherence horizon (fraction of steps meeting threshold).

H₇ is used as:
- a verifier gate for candidate approval,
- an archive admission criterion in quality-diversity space,
- a stabilizing signal in fitness shaping.

The core math and helper metrics live in `athanor.core.coherence`.

---

## System Loop
For each generation:
1. Propose child candidates from parent parameters.
2. Capture telemetry trajectories.
3. Verify with the H₇ gate:
   - `APPROVE` when `H7 >= threshold_h7`
   - `REFINE` when in the configured refine band
   - `REJECT` below refine floor
4. Score/select survivors.
5. Attempt MAP-Elites archive admission.
6. Persist an immutable ledger row per candidate.

---

## Quickstart
### Install
```bash
git clone https://github.com/jacksonjp0311-gif/Athanor.git
cd Athanor
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

> Python 3.10+ is required.

### Run (toy config)
```bash
athanor --config configs/toy_experiment.yaml
```

Or via module invocation:
```bash
python -m athanor --config configs/toy_experiment.yaml
```

A successful run emits JSON to stdout with:
- `run_path`
- `stats`
- `config_hash`

---

## Configuration
ATHANOR uses YAML config files with optional inheritance:

- `configs/base.yaml` defines defaults.
- `configs/toy_experiment.yaml` inherits from `base.yaml` and overrides a subset.

Key fields include:
- `threshold_h7`
- `alpha`
- `steps_per_candidate`
- `population`
- `generations`
- `refine_attempts`
- `dphi_mode`
- `archive.bins`
- `run.out_dir`

---

## Run Artifacts
Each run writes to `data/archives/run_<timestamp>/` and includes:
- `ledger.jsonl`
- `archive.pkl`
- `archive_stats.json`
- `metadata.yaml`
- `h7_trace.png`
- `fitness_trace.png`
- `dashboard.html`

These artifacts provide reproducible traces for analysis, comparison, and reporting.

---

## Repository Structure
```text
.
├── .github/workflows/ci.yml      # CI install + test workflow
├── configs/
│   ├── base.yaml                 # Default experiment config
│   └── toy_experiment.yaml       # Minimal sanity config
├── data/archives/                # Run outputs (run_*/)
├── docs/source/architecture.md   # Architecture and roadmap notes
├── scripts/
│   ├── run_evolution.py          # Scripted runner helper
│   └── root_reflection.py        # Artifact verification helper
├── src/athanor/
│   ├── adapters/                 # Proposal adapter strategies
│   ├── agents/                   # Telemetry/Propose/Verify/Select/Archivist agents
│   ├── backends/                 # Backend hooks
│   ├── core/                     # ΔΦ, C, H₇, telemetry types/math
│   ├── evolution/                # DGM loop + archive implementation
│   ├── experiments/              # Config loader/registry
│   ├── scripts/                  # CLI entrypoint implementation
│   └── utils/                    # Logging, seeding, visualization/dashboard
├── tests/
│   ├── integration/
│   └── unit/
├── pyproject.toml
├── requirements.txt
└── LICENSE
```

---

## Documentation & Charters
- `docs/source/architecture.md` provides system-level architecture and evolution notes.
- Mini-guides are available for each major directory (see `README.md` files inside folders).
- Agent charters:
  - `AGENTS.md`
  - `src/athanor/agents/AGENTS.md`

Research manuscripts (LaTeX) are available under `docs/source/` as optional references.

---

## Testing
Run all tests:
```bash
PYTHONPATH=src pytest -q
```

The suite includes:
- unit checks for coherence math,
- integration checks for CLI + toy config execution.

---

## Scope & Intended Use
ATHANOR is intended as:
- a reference implementation for coherence-gated recursive improvement experiments,
- a baseline for safety-oriented quality-diversity pipelines,
- a foundation for workshop/paper prototypes.

This repository is a computational research system. It does **not** claim new physics, metaphysics, or consciousness results.

---

## License
MIT © 2025 James Paul Jackson
