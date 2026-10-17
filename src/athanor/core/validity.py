"""Hard validity pre-gate.

H7 measures *drift*; it does not test correctness. An edit that crashes or goes
non-finite on a few inputs can still be coherent on most of them. Run this check
*before* the coherence gate: any failure is a hard REJECT.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, Iterable, Sequence

VALIDITY_ERRORS = (ArithmeticError, ValueError, TypeError)


def validity_check(fn: Callable[[Any], Any], inputs: Iterable[Any],
                   errors: Sequence[type] = VALIDITY_ERRORS) -> Dict[str, Any]:
    """Call ``fn`` on every input; fail on an exception in ``errors`` or a non-finite numeric result."""
    n = failures = 0
    first = None
    for x in inputs:
        n += 1
        try:
            v = fn(x)
            ok = all(math.isfinite(float(t)) for t in (v if isinstance(v, (list, tuple)) else [v]))
        except tuple(errors) as exc:
            ok, v = False, repr(exc)
        if not ok:
            failures += 1
            if first is None:
                first = {"input": x, "output": v if isinstance(v, str) else repr(v)}
    return {"gate": "VALIDITY", "passed": failures == 0, "inputs": n, "failures": failures,
            "first_failure": first}
