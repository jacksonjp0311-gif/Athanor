# ATHANOR

**Coherence-Gated Darwin Gödel Agents**  
*A stability governor for recursive self-improvement experiments.*

ATHANOR is a research-oriented Python framework for running a multi-agent evolutionary loop where candidate self-modifications are admitted only when coherence criteria are met.

---

## Table of Contents
- [What this repository is](#what-this-repository-is)
- [Core theory](#core-theory)
- [H₇ geometry-law framing (v2.1)](#h-law-framing-v21)
- [System loop](#system-loop)
- [Repository structure](#repository-structure)
- [Installation](#installation)
  - [Bash (Linux/macOS)](#bash-linuxmacos)
  - [PowerShell (Windows)](#powershell-windows)
- [How to run](#how-to-run)
- [Configuration](#configuration)
- [Run artifacts](#run-artifacts)
- [Testing](#testing)
- [Project quality](#project-quality)
- [Intended use and scope](#intended-use-and-scope)
- [Credits](#credits)
- [H₇ geometry-law manuscript](#h-law-geometry-law-manuscript)
- [777 triadic-boundary manuscripts](#777-triadic-boundary-manuscripts)
- [H₂₀ Ω-basin manuscript](#h-basin-manuscript)
- [H₄₄ boundary algebra manuscript](#h-boundary-algebra-manuscript)
- [License](#license)

---

## What this repository is
ATHANOR implements a symbolic loop for coherence-gated candidate evolution:

**Telemetry → Propose → Verify → Select → Archive → Ledger**

The verifier acts as a stability guardrail. Candidate updates are accepted, refined, or rejected based on H₇ thresholds.

---

## Core theory
ATHANOR uses three key quantities:

- **ΔΦ**: local residual drift estimator over a trajectory.
- **C = 1 / (1 + |ΔΦ|)**: local coherence derived from drift magnitude.
- **H₇ = mean(C ≥ threshold)**: coherence horizon (fraction of steps meeting threshold).

Operationally, H₇ is used as:
- a verifier gate for candidate approval,
- an archive admission criterion in quality-diversity space,
- a stabilizing signal in fitness shaping.

For experimentation with geometry-style weighting/survival ideas, `athanor.core.coherence` now also exposes:
- `weighted_coherence_mean(C, power=...)`
- `cusp_limited_h7(C, threshold=..., survival_floor=...)`
- `inject_bounded_noise(ΔΦ, sigma, rng=None, seed=None)`
- `immunity_index(C, C_perturbed)` and `basin_drift(C, C_perturbed)`
- `omega_lipschitz_kappa_bound(C0)`
- `boundary_excess(value, boundary)`
- `commensurability_suppression_score(value, max_denominator)`
- `select_boundary_invariant(candidates, degree, suppression_weight)`

---

## H₇ geometry-law framing (v2.1)
This repository adopts a geometry-first interpretation aligned with your latest framing:

- H₇ should be treated as a **fixed-point behavior** under residual-error dynamics,
  nonlinear weighting, and survival constraints.
- The often-observed band near **0.70–0.72** is a useful empirical projection,
  not a universal numerical constant.
- In code, `threshold_h7` remains configurable and defaults to `0.70` as a practical
  operating point for this symbolic implementation.

This reframing helps keep the project scientifically disciplined while still
retaining the useful default gate for engineering workflows.

---

## System loop
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

## Repository structure
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
├── athanor-latex-paper.tex       # Extended theoretical/technical write-up
├── pyproject.toml
├── requirements.txt
└── LICENSE
```

---

## Installation

### Bash (Linux/macOS)
```bash
git clone https://github.com/jacksonjp0311-gif/Athanor.git
cd Athanor
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### PowerShell (Windows)
```powershell
git clone https://github.com/jacksonjp0311-gif/Athanor.git
Set-Location Athanor
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

> Python 3.10+ is required.

---

## How to run
Run the packaged CLI with the toy config:

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

Important fields include:
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

## Run artifacts
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

## Testing
Run all tests:

```bash
PYTHONPATH=src pytest -q
```

Test suite includes:
- unit checks for coherence math,
- integration check for CLI + toy config execution.

---

## Project quality
- CI runs on push/PR and executes unit + integration tests.
- Core coherence utilities are covered by focused unit tests (including H₂₀/H₄₄ helpers).
- CLI smoke path (`python -m athanor --config ...`) is continuously validated by integration tests.

---


## Intended use and scope
ATHANOR is intended as:
- a reference implementation for coherence-gated recursive improvement experiments,
- a baseline for safety-oriented quality-diversity pipelines,
- a foundation for workshop/paper prototypes.

This repository is a computational research system. It does **not** claim new physics, metaphysics, or consciousness results.

---

## Credits
- **James Paul Jackson** (@unifiedenergy11)  
  Originator of the Codex H₇ coherence engine concept and primary author of the implementation in this repository.

- **Keith L. Beaudoin** (@keithofaptos)  
  Contributed conceptual synthesis on integrating H₇ gating strategies into DGM/EvoDistill-style evolving codebases.

Lineage and inspiration include:
- Jürgen Schmidhuber’s Gödel Machine framing,
- Quality-Diversity methods (MAP-Elites, novelty/open-endedness),
- modern Darwin Gödel / EvoDistill-era recursive-improvement work.

---

## H₇ geometry-law manuscript
A full LaTeX manuscript of the v2.1 geometry-law framing is included at:

- `docs/source/h7_coherence_geometry_law_v2_1.tex`

This is provided as a research document and conceptual framing reference for the repository.

---


## 777 triadic-boundary manuscripts
The repository now also includes two LaTeX geometry notes:

- `docs/source/codex_777_triadic_boundary_excess_v1_0.tex`
- `docs/source/codex_777_triadic_boundary_excess_v2_0.tex`

These are included as mathematical reference documents and do not change runtime behavior by themselves.

---

## H₂₀ Ω-basin manuscript
A full LaTeX manuscript of the H₂₀ Ω-basin noise-immunity framing is included at:

- `docs/source/h20_omega_basin_noise_immunity_v1_5.tex`

This can be used to guide perturbation robustness experiments around ΔΦ/Ω stability.

---

## H₄₄ boundary algebra manuscript
A full LaTeX manuscript of the H₄₄ Boundary Algebra layer is included at:

- `docs/source/h44_boundary_algebra_layer_v1_0.tex`

This provides a selection-layer framing for extremal invariants at feasibility boundaries.

---

## License
MIT © 2025 James Paul Jackson
