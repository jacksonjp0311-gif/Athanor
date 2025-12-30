Athanor

Coherence-Gated Darwin Gödel Agents  
A Codex H₇ / ΔΦ Stability Governor for Recursive Self-Improvement

H7-gated agent loop  
(Telemetry → Propose → Verify (H7 Gate) → Select → Archive → Commit, with refinement on H7 failure and archive feedback)

## One-Line Description

A multi-agent architecture that constrains recursive self-improvement in Darwin Gödel Machine (DGM)-style systems using the Codex H₇ / ΔΦ coherence horizon as a deterministic stability governor.

## Core Principle

Recursive self-modification is permitted only when internal dynamics remain coherent under bounded phase drift.

- ΔΦ → local drift estimator over trajectories  
- C = 1 / (1 + |ΔΦ|) → local coherence  
- H₇ = mean(C ≥ 0.70) → coherence horizon  

H₇ serves three operational roles:
- Auxiliary fitness regularizer
- Quality-diversity archive admission gate
- Hard verifier for self-modification commits

## Authorship & Credit

- James Paul Jackson (@unifiedenergy11)  
  Originator of the Codex H₇ Coherence Engine, the ΔΦ-based coherence framework, the analytic coherence-horizon gating mechanism, and the overall stability-first safety architecture.  
  Author of the complete implementation in this repository (including the evolutionary loop, agents, MAP-Elites archive, visualization, CLI, and forge system).

- Keith L. Beaudoin (@keithofaptos)  
  Contributed key conceptual synthesis that brought these ideas together through his December 25, 2025 note "Integrating H7 Engine Code into DGM Evolving Codebase". His work on integrating H₇ into DGM/EvoDistill-style evolving codebases — including fitness augmentation, archive gating, and verification strategies — directly shaped the multi-agent design and its compatibility with modern recursive improvement systems.

## Lineage & Inspiration

- Jürgen Schmidhuber — Gödel Machine and formal self-referential learning systems
- Quality-Diversity evolution (MAP-Elites, novelty search, open-endedness)
- Recent EvoDistill / Darwin Gödel Machine advances (Sakana AI et al., 2025)

## Scope & Discipline

This repository implements a computational stability governor.  
It makes no claims about new physics, metaphysics, or consciousness.

## Features

- Full multi-agent loop with explicit agent roles
- Parameter-free core coherence computation (L2 or cosine modes)
- MAP-Elites archive over (H₇, novelty) behavioral descriptor
- Adaptive refinement in the coherence band [0.50, 0.70)
- Rich, versioned run artifacts: ledger.jsonl, archive.pkl, traces, HTML dashboards
- CLI entry point, CI-ready, MIT licensed
- Atomic PowerShell forge for reproducible builds

## Quick Start

bash git clone https://github.com/jacksonjp0311-gif/Athanor.git cd Athanor pip install -e . athanor --config configs/toy_experiment.yaml 

Runs appear under data/archives/run_* with ledger, visualizations, and an interactive dashboard showing the H₇ ridge tightening over generations.

## Intended Use

- Reference implementation for safe recursive improvement research
- Baseline for coherence-gated agents in quality-diversity evolution
- Foundation for workshop / arXiv submissions on stability-first self-improvement

## License

MIT © 2025 James Paul Jackson

---

Forge complete. Stability gate active. H₇ = 0.70 enforced.  
𓂀

athanor/
├── .github/workflows/ci.yml     # CI: install + tests
├── configs/
│   ├── base.yaml               # Default H7, α, ΔΦ mode
│   └── toy_experiment.yaml     # Minimal sanity run
├── data/archives/
│   └── run_*/                  # Each run = immutable record
├── docs/source/
│   └── architecture.md         # System explanation
├── examples/                   # Minimal demos (symbolic / neural)
├── scripts/
│   ├── run_evolution.py        # CLI runner
│   └── root_reflection.py      # Artifact verification
├── src/athanor/
│   ├── core/                   # ΔΦ, C, H7 math
│   ├── agents/                 # Telemetry / Propose / Verify / Select
│   ├── evolution/              # Recursive loop + archive
│   ├── backends/               # Torch / JAX / symbolic hooks
│   └── utils/                  # Logging, seeding, visualization
├── tests/                      # Unit + integration tests
├── pyproject.toml
├── requirements.txt
└── LICENSE
