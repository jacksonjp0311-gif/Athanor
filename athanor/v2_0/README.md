# 𓂀 ATHANOR v2.0 — Coherence Forge (ΔΦ → Ω → H₇ Gate)

**Author:** James Jackson (@jacksonjp0311-gif)  
**Repo:** Athanor  
**Tag:** ⧉ATH-v2.0⧉forge⧉delta-phi⧉omega⧉H7⧉adaptive-damping⧉ledger⧉

## What it is
Athanor is a **numeric coherence-forge**: it evolves candidate transformations through a ΔΦ error-geometry field and only accepts change that preserves the **H₇ coherence horizon**.

## Core mechanics
- **ΔΦ field** from spatial gradients of the evolving field.
- **Ω geometry**: Ω = 1/(1+|ΔΦ|).
- **Adaptive damping**: η(t)=η0*(1-Ω̄) (high Ω keeps motion; low Ω damps spikes).
- **H₇ gate**: track the fraction of coherence values ≥ 0.70.

## Outputs
- state/*.json run snapshot (metrics + paths)
- ledger/*.jsonl append-only run ledger
- isuals/*.png ΔΦ / Ω / Coherence / resonance curve
- public/*.html True-Black report for sharing

## How to run
Open PowerShell at repo root and run:

\\\powershell
.\Athanor_AllOne_v2_0.ps1
\\\

Optional real input:

\\\powershell
.\Athanor_AllOne_v2_0.ps1 -InputPath "path\to\data.npy"
\\\

## Laws
- Universal Truth: C = (E·I)/(1+|ΔΦ|)
- GEO v1.0: Ω = 1/(1+|ΔΦ|)
- ΔΦ Cusp Protocol v2.8 tracked per run (EI, γ, D, D_c, λ, Φ_c, C_cusp)
