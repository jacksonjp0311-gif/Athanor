# Core Module

This package implements ATHANOR's core math, telemetry primitives, and data types.

## Purpose
Provide deterministic, reusable coherence primitives that every higher layer depends on.

## Files
- `coherence.py` — ΔΦ estimators, coherence transforms, H7 horizon, and H20/H44 helper utilities.
- `telemetry.py` — trajectory capture helpers used by telemetry agents.
- `types.py` — dataclasses for candidates, telemetry batches, and ΔΦ estimates.
- `__init__.py` — public core API exports.

## How it works
1. Convert trajectories to local drift (`delta_phi`).
2. Map drift to coherence (`coherence_from_dphi`).
3. Derive horizon and auxiliary robustness/selection metrics.

## Evolutionary coherence note
The core layer is intentionally minimal and composable so new theory layers can be added without destabilizing existing run semantics.
