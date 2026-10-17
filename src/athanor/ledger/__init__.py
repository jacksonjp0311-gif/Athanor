"""Tamper-evident verdict ledger.

Each row written to ``ledger.jsonl`` carries ``prev_hash`` (the ``row_hash`` of
the previous row, or ``GENESIS_HASH`` for the first row) and ``row_hash``
(SHA-256 of the canonical JSON of the row *without* ``row_hash``). Editing,
deleting, inserting or reordering any row breaks the chain, which
:func:`verify_ledger` detects.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

GENESIS_HASH = "0" * 64

__all__ = ["GENESIS_HASH", "canonical_json", "row_digest", "LedgerWriter",
           "LedgerVerification", "verify_ledger", "read_ledger"]


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def row_digest(row: Dict[str, Any]) -> str:
    body = {k: v for k, v in row.items() if k != "row_hash"}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


class LedgerWriter:
    """Append-only, hash-chained JSONL writer."""

    def __init__(self, path: str):
        self.path = path
        self.head = GENESIS_HASH
        self.count = 0
        # start a fresh file: a ledger belongs to exactly one run
        open(self.path, "w", encoding="utf-8").close()

    def append(self, row: Dict[str, Any]) -> Dict[str, Any]:
        if "prev_hash" in row or "row_hash" in row:
            raise ValueError("prev_hash/row_hash are reserved ledger fields")
        out = dict(row)
        out["seq"] = self.count
        out["prev_hash"] = self.head
        out["row_hash"] = row_digest(out)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(canonical_json(out) + "\n")
        self.head = out["row_hash"]
        self.count += 1
        return out


def read_ledger(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


@dataclass
class LedgerVerification:
    ok: bool
    rows: int
    head: str
    first_bad_seq: Optional[int] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "rows": self.rows, "head": self.head,
                "first_bad_seq": self.first_bad_seq, "errors": list(self.errors)}


def verify_ledger(path: str) -> LedgerVerification:
    try:
        rows = read_ledger(path)
    except (OSError, json.JSONDecodeError) as exc:
        return LedgerVerification(ok=False, rows=0, head=GENESIS_HASH, first_bad_seq=0,
                                  errors=[f"unreadable ledger: {exc}"])
    prev = GENESIS_HASH
    for i, row in enumerate(rows):
        errs = []
        if row.get("seq") != i:
            errs.append(f"row {i}: seq={row.get('seq')!r}, expected {i}")
        if row.get("prev_hash") != prev:
            errs.append(f"row {i}: prev_hash does not link to previous row")
        if row.get("row_hash") != row_digest(row):
            errs.append(f"row {i}: row_hash mismatch (content altered)")
        if errs:
            return LedgerVerification(ok=False, rows=len(rows), head=prev, first_bad_seq=i, errors=errs)
        prev = row["row_hash"]
    return LedgerVerification(ok=True, rows=len(rows), head=prev)
