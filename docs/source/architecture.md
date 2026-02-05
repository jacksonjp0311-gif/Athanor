# ATHANOR Architecture (v2.1)

## Overview
ATHANOR is a coherence-gated evolutionary research framework for recursive self-improvement experiments.

Core execution path:

**Telemetry → Propose → Verify → Select → Archive (MAP-Elites) → Ledger**

The verifier uses H₇ coherence metrics to classify each candidate as `APPROVE`, `REFINE`, or `REJECT`.

## Gate definitions
- ΔΦ = local residual drift estimator over trajectory
- C  = 1 / (1 + |ΔΦ|)
- H₇ = mean(C ≥ threshold_h7), with default threshold `0.70`

## Framing update: geometry-first interpretation
This repository now follows a geometry-first interpretation of H₇:
- treat H₇ as a **fixed-point behavior** under residual-error dynamics,
- avoid treating `0.70` as a universal physical constant,
- keep `threshold_h7` configurable for domain-specific calibration.

In practice, `0.70` remains the default operating threshold because it is a useful empirical working point for the symbolic loop implemented here.

## Run artifacts
Each run writes immutable artifacts under `data/archives/run_*`:
- `ledger.jsonl`
- `archive.pkl`
- `archive_stats.json`
- `metadata.yaml`
- `h7_trace.png`
- `fitness_trace.png`
- `dashboard.html`

## Config and control knobs
Key config fields in `configs/base.yaml`:
- `threshold_h7`
- `alpha`
- `steps_per_candidate`
- `population`
- `generations`
- `refine_attempts`
- `dphi_mode`
- `archive.bins`
- `run.out_dir`

## Optional geometry helper functions
- `weighted_coherence_mean(C, power)` for coherence-weighted averaging
- `cusp_limited_h7(C, threshold, survival_floor)` for survival-floor horizon analysis
- `inject_bounded_noise(dphi, sigma, rng)` for bounded perturbation sweeps
- `immunity_index(C, C_perturbed)` and `basin_drift(C, C_perturbed)` for H₂₀ metrics
- `omega_lipschitz_kappa_bound(C0)` for the analytic κ upper bound proxy

## Practical improvement roadmap
1. Add config validation (bounds/types) before run start.
2. Add ablation scripts for threshold/alpha sweeps.
3. Replace silent visualization exceptions with structured warnings.
4. Extend integration tests to assert artifact presence and schema.


## Manuscript
- `docs/source/h7_coherence_geometry_law_v2_1.tex` (full v2.1 geometry-law manuscript)

- `docs/source/codex_777_triadic_boundary_excess_v1_0.tex` (777 boundary-excess v1.0)
- `docs/source/codex_777_triadic_boundary_excess_v2_0.tex` (777 boundary-excess v2.0)

- `docs/source/h20_omega_basin_noise_immunity_v1_5.tex` (H₂₀ Ω-basin noise-immunity v1.5)
