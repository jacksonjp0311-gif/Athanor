# Agents Module

This package defines the operational roles in ATHANOR's coherence-gated evolution loop.

## Purpose
Agents separate responsibilities so each stage can be reasoned about, tested, and evolved independently.

## Files
- `base.py` — minimal agent interface shared by all agent roles.
- `telemetry_agent.py` — captures candidate trajectories and telemetry payloads.
- `proposer_agent.py` — generates candidate mutations from the current parent.
- `verifier_agent.py` — computes coherence metrics and assigns `APPROVE` / `REFINE` / `REJECT`.
- `selector_agent.py` — combines quality and coherence into final scalar selection score.
- `archivist_agent.py` — mediates admission into the MAP-Elites-style archive.
- `__init__.py` — agent exports.

## Evolutionary coherence note
The module is structured as a controllable pipeline: propose change, measure drift, verify coherence, then preserve only stable improvements.
