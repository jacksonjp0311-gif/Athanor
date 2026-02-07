# ATHANOR Agent Charter

This document defines the operating principle for contributors (human and AI) working in this repository.

## Core principle
ATHANOR evolves through **coherence-first change**:

1. Propose an improvement.
2. Measure drift and coherence impact.
3. Preserve only changes that keep system behavior stable and auditable.

In practical terms, we value:
- reproducibility over novelty-only changes,
- explicit validation over implicit assumptions,
- clear artifacts over hidden state.

## Evolution path
The project progresses in layers:
1. **Core math stability** (ΔΦ, C, H7 and helper metrics).
2. **Agent pipeline reliability** (telemetry/proposal/verification/selection/archive).
3. **Experiment discipline** (validated configs, deterministic controls where requested).
4. **Observability and evidence** (ledger, stats, plots, dashboard, tests).
5. **Theory-to-execution bridges** (H7/H20/H44/777 ideas expressed as optional, testable utilities).

## Folder-level guidance
For local responsibilities, use the folder mini-guides and section docs.

- Package overview: `src/athanor/README.md`
- Agent subsystem detail: `src/athanor/agents/AGENTS.md`
- Theory/architecture references: `docs/source/`

## Contribution contract
Any substantive change should include:
- a clear reason,
- tests or checks demonstrating behavior,
- documentation updates if interfaces/flows changed.

This keeps repository evolution coherent with the same principles the system itself enforces.
