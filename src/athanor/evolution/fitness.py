from __future__ import annotations
def combine(alpha: float, q: float, h7: float) -> float:
    a = float(alpha)
    return (a * float(q)) + ((1.0 - a) * float(h7))
