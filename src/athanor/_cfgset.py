"""``--set path=value`` overrides for registry specs (values parsed as JSON when possible)."""
from __future__ import annotations

import copy
import json
from typing import Any, Dict, Iterable


def _value(text: str) -> Any:
    if text == "none":
        return None
    try:
        return json.loads(text)
    except ValueError:
        return text


def apply_sets(spec: Dict[str, Any], sets: Iterable[str]) -> Dict[str, Any]:
    out = copy.deepcopy(spec)
    for item in sets:
        if "=" not in item:
            raise ValueError(f"bad --set {item!r}; expected path=value")
        path, value = item.split("=", 1)
        keys = path.strip().split(".")
        if keys[0] not in ("arm", "cfg"):
            raise ValueError(f"--set path must start with arm. or cfg., got {path!r}")
        cur = out
        for k in keys[:-1]:
            cur = cur.setdefault(k, {})
        cur[keys[-1]] = _value(value.strip())
    return out
