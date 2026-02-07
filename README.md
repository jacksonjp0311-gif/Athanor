# ATHANOR

**Coherence-Gated Darwin Gödel Agents**  
*A stability governor for recursive self-improvement.*

ATHANOR is a research-oriented Python framework for running a multi-agent evolutionary loop where candidate self-modifications are admitted only when coherence criteria are met.

---

## Overview
ATHANOR implements a coherence-gated loop:

**Telemetry → Propose → Verify → Select → Archive → Ledger**

The verifier applies the H₇ coherence horizon as a stability guardrail, with optional refinement for borderline candidates.

---

## Core principle
Recursive self-modification is permitted only when internal dynamics remain coherent under bounded phase drift.

- **ΔΦ**: residual drift estimator over a trajectory.
- **C = 1 / (1 + |ΔΦ|)**: local coherence derived from drift magnitude.
- **H₇ = mean(C ≥ threshold)**: coherence horizon.

Operationally, H₇ serves as:
- a verifier gate for candidate approval,
- an archive admission criterion in quality-diversity space,
- a stabilizing signal in fitness shaping.

---

## Features
- Multi-agent loop with explicit telemetry, proposal, verification, selection, and archive roles.
- Deterministic coherence math (L2 or cosine ΔΦ modes).
- MAP-Elites archive over behavioral descriptors.
- Adaptive refinement in the coherence band [0.50, 0.70).
- Immutable run artifacts: ledger, archive, traces, and dashboards.
- CLI entry point and CI-ready tests.

---

## Quick start

```bash
git clone https://github.com/jacksonjp0311-gif/Athanor.git
cd Athanor
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

athanor --config configs/toy_experiment.yaml
```

A successful run writes `run_*` artifacts under `data/archives/`.

---

## Configuration
ATHANOR uses YAML config files with inheritance:

- `configs/base.yaml` defines defaults.
- `configs/toy_experiment.yaml` inherits and overrides a minimal subset.

Key fields include `threshold_h7`, `alpha`, `steps_per_candidate`, `population`, `generations`, `refine_attempts`, `dphi_mode`, `archive.bins`, and `run.out_dir`.

---

## Repository structure
```text
.
├── configs/                 # Experiment configs
├── data/archives/           # Run outputs (run_*/)
├── docs/source/             # Architecture notes + manuscripts
├── scripts/                 # Local runner helpers
├── src/athanor/             # Core package
└── tests/                   # Unit + integration tests
```

Folder-specific READMEs provide scoped guidance (e.g. `configs/README.md`, `src/README.md`, `docs/README.md`).

---

## Documentation & references
- Architecture notes: `docs/source/architecture.md`
- Agent charter: `AGENTS.md`
- Agent subsystem charter: `src/athanor/agents/AGENTS.md`

---

## License
MIT © 2025 James Paul Jackson
