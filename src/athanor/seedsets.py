"""Seed-set policy (3.0.0): which seeds may be used for what, and which are spent.

Every number reported by ATHANOR comes from a named seed set. A set has one purpose.
A *held-out* or *gate* set is spent once a result on it has been looked at, and it is
never used to choose anything again.

==================  =============  ==========================================================
set                 seeds          purpose / status
==================  =============  ==========================================================
tuning              100-115        tuning only (selfmod 2.5, TSP 2.6). Free to reuse for tuning.
heldout-v2          0-15           held-out report of 2.4-2.6. **Spent**: since 2.7 the eval
                                   cases ATH-T001/T004/T005-T007 check these seeds on every run.
gate-v2.7           200-215        promotion gate of 2.7 (``adaptive@1.1.0``). **Spent**.
bench-v3            3000-3015      held-out seeds of the 3.0 unified benchmark (``athanor bench
                                   --all``). Used once for the published table.
gate-pool           10000 + 16k    promotion gate blocks. Each real promotion takes the next
                                   unused block of 16; the block is recorded in the registry
                                   ledger and never reused.
dry-run             90000-90015    scratch seeds for ``promote --dry-run``. Not a held-out set:
                                   nothing chosen on them is reported as held-out.
==================  =============  ==========================================================

Explicit ``--gate-seeds`` that overlap any set other than ``dry-run`` are refused
unless ``--allow-seed-reuse`` is given, and the reuse is then recorded.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

SEED_SETS: Dict[str, Dict[str, object]] = {
    "tuning": {"range": (100, 115), "status": "tuning", "note": "tuning only; reuse for tuning is fine"},
    "heldout-v2": {"range": (0, 15), "status": "spent", "note": "2.4-2.6 held-out; eval cases check it since 2.7"},
    "gate-v2.7": {"range": (200, 215), "status": "spent", "note": "2.7 promotion gate"},
    "bench-v3": {"range": (3000, 3015), "status": "held-out", "note": "3.0 unified benchmark, used once"},
    "dry-run": {"range": (90000, 90015), "status": "scratch", "note": "promote --dry-run only"},
}
GATE_POOL_START = 10000
GATE_BLOCK = 16
DRY_RUN_SEEDS = tuple(range(90000, 90016))
BENCH_SEEDS = tuple(range(3000, 3016))


def seeds_of(name: str) -> Tuple[int, ...]:
    a, b = SEED_SETS[name]["range"]  # type: ignore[misc]
    return tuple(range(int(a), int(b) + 1))


def classify(seeds: Iterable[int]) -> Dict[str, List[int]]:
    """Which named sets (and the gate pool) these seeds fall in."""
    out: Dict[str, List[int]] = {}
    for s in seeds:
        hit = False
        for name, meta in SEED_SETS.items():
            a, b = meta["range"]  # type: ignore[misc]
            if a <= s <= b:
                out.setdefault(name, []).append(int(s))
                hit = True
        if not hit and GATE_POOL_START <= s < SEED_SETS["dry-run"]["range"][0]:  # type: ignore[index]
            out.setdefault("gate-pool", []).append(int(s))
    return out


def used_gate_seeds(events: Iterable[Dict[str, object]]) -> Set[int]:
    """Every seed a recorded promotion decision has looked at (``gate_seeds`` is [first, last])."""
    used: Set[int] = set()
    for e in events:
        g = e.get("gate_seeds")
        if isinstance(g, (list, tuple)) and len(g) == 2:
            used.update(range(int(g[0]), int(g[1]) + 1))
    return used


def next_gate_block(events: Iterable[Dict[str, object]]) -> Tuple[int, ...]:
    used = used_gate_seeds(events)
    k = 0
    while True:
        block = tuple(range(GATE_POOL_START + GATE_BLOCK * k, GATE_POOL_START + GATE_BLOCK * (k + 1)))
        if not used.intersection(block):
            return block
        k += 1


class SeedReuseError(ValueError):
    pass


def choose_gate_seeds(events: Sequence[Dict[str, object]], requested: Optional[Sequence[int]] = None, *,
                      dry_run: bool = False, allow_reuse: bool = False) -> Tuple[Tuple[int, ...], Dict[str, object]]:
    """Return (seeds, policy record). Refuses spent or reserved seeds unless ``allow_reuse``."""
    if requested is None:
        seeds = DRY_RUN_SEEDS if dry_run else next_gate_block(events)
        return seeds, {"source": "dry-run" if dry_run else "gate-pool", "reuse": False}
    seeds = tuple(int(s) for s in requested)
    clash = {k: v for k, v in classify(seeds).items() if k not in ("dry-run",)}
    used = used_gate_seeds(events).intersection(seeds)
    if used:
        clash["previously-gated"] = sorted(used)
    clash.pop("gate-pool", None)  # an unused pool seed is fresh; a used one is caught above
    if clash and not allow_reuse and not dry_run:
        detail = "; ".join(f"{k}: {v[0]}..{v[-1]}" for k, v in clash.items())
        raise SeedReuseError(f"gate seeds overlap reserved or spent seed sets ({detail}). "
                             "Omit --gate-seeds to take the next fresh block, or pass --allow-seed-reuse "
                             "(recorded in the ledger).")
    return seeds, {"source": "explicit", "reuse": bool(clash), "overlaps": sorted(clash)}
