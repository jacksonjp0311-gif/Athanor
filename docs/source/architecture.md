# ATHANOR Architecture (v2.0)

## Gate
- ΔΦ = local drift estimator over trajectory
- C  = 1 / (1 + |ΔΦ|)
- H7 = mean(C ≥ 0.70)
- verdict ∈ { APPROVE, REFINE, REJECT }

## Loop (symbolic v2.0)
Telemetry → Propose → Verify → Select → Archive (MAP-Elites) → Ledger

## Run artifacts
A run directory under data/archives/run_* containing:
- ledger.jsonl
- archive.pkl
- archive_stats.json
- metadata.yaml
- h7_trace.png, fitness_trace.png, dashboard.html