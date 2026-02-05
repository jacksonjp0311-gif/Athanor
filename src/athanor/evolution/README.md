# Evolution Module

This package orchestrates ATHANOR's generation loop and archive behavior.

## Files
- `dgm_loop.py` — main recursive improvement loop and artifact writer.
- `archive.py` — MAP-Elites-style archive structure and stats.
- `__init__.py` — exports.

## Loop flow
Telemetry → Propose → Verify → Select → Archive → Ledger

The loop keeps improving candidates while preserving run reproducibility artifacts (`ledger.jsonl`, stats, metadata, plots/dashboard).
