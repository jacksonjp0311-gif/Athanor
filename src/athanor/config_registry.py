"""Versioned config registry (``configs/registry/``).

Every tuned configuration is an immutable JSON entry::

    configs/registry/<family>/<name>/<semver>.json

with a ``spec`` (what is actually run: ``{"arm": ..., "cfg": ...}``), its
``spec_hash`` (SHA-256 of the canonical JSON of ``spec``), a ``parent`` reference
(lineage), a human ``reason`` and the ``evidence`` it came from.

A reference is written ``family/name@version`` (e.g. ``selfmod/adaptive@1.1.0``).

Status is never edited inside an entry. Every event (register, promote, refine,
reject) is appended to the hash-chained ``configs/registry/ledger.jsonl``, and an
entry's status is derived from the latest event that names it. The current
*incumbent* of a family is the most recently promoted entry.

Versioning rule (enforced against the parent when it has the same name):

* major bump: the arm (which mechanisms are switched on) changed;
* minor bump: only ``cfg`` values changed;
* patch bump: the spec is identical (metadata / evidence only).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from . import __version__
from .ledger import GENESIS_HASH, canonical_json, read_ledger, row_digest, verify_ledger

SCHEMA = "athanor.config/1"
DEFAULT_ROOT = os.path.join("configs", "registry")
_REF = re.compile(r"^(?P<family>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+)@(?P<version>\d+\.\d+\.\d+)$")
STATUSES = ("candidate", "promoted", "refine", "rejected", "retired")


def spec_hash(spec: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(spec).encode("utf-8")).hexdigest()


def parse_ref(ref: str) -> Tuple[str, str, str]:
    m = _REF.match(str(ref).strip())
    if not m:
        raise ValueError(f"bad config reference {ref!r}; expected family/name@MAJOR.MINOR.PATCH")
    return m["family"], m["name"], m["version"]


def semver(v: str) -> Tuple[int, int, int]:
    a, b, c = (int(x) for x in v.split("."))
    return a, b, c


def required_bump(parent_spec: Dict[str, Any], child_spec: Dict[str, Any]) -> str:
    if canonical_json(parent_spec.get("arm")) != canonical_json(child_spec.get("arm")):
        return "major"
    if canonical_json(parent_spec) != canonical_json(child_spec):
        return "minor"
    return "patch"


def bump_kind(old: str, new: str) -> Optional[str]:
    o, n = semver(old), semver(new)
    if n <= o:
        return None
    if n[0] > o[0]:
        return "major"
    if n[1] > o[1]:
        return "minor"
    return "patch"


_ORDER = {"patch": 0, "minor": 1, "major": 2}


@dataclass
class Registry:
    root: str = DEFAULT_ROOT

    # ------------------------------------------------------------------ paths
    @property
    def ledger_path(self) -> str:
        return os.path.join(self.root, "ledger.jsonl")

    def entry_path(self, ref: str) -> str:
        family, name, version = parse_ref(ref)
        return os.path.join(self.root, family, name, f"{version}.json")

    # ---------------------------------------------------------------- reading
    def get(self, ref: str) -> Dict[str, Any]:
        path = self.entry_path(ref)
        if not os.path.exists(path):
            raise KeyError(f"unknown config {ref} (no {path})")
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
        if entry.get("ref") != ref:
            raise ValueError(f"{path}: ref field {entry.get('ref')!r} does not match its location {ref!r}")
        return entry

    def refs(self, family: Optional[str] = None) -> List[str]:
        out = []
        if not os.path.isdir(self.root):
            return out
        for fam in sorted(os.listdir(self.root)):
            fdir = os.path.join(self.root, fam)
            if not os.path.isdir(fdir) or (family and fam != family):
                continue
            for name in sorted(os.listdir(fdir)):
                ndir = os.path.join(fdir, name)
                if not os.path.isdir(ndir):
                    continue
                versions = [f[:-5] for f in os.listdir(ndir) if f.endswith(".json")]
                for v in sorted(versions, key=semver):
                    out.append(f"{fam}/{name}@{v}")
        return out

    def events(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.ledger_path):
            return []
        return read_ledger(self.ledger_path)

    def status(self, ref: str) -> str:
        st = None
        for ev in self.events():
            if ev.get("ref") == ref:
                st = {"register": "candidate", "promote": "promoted", "refine": "refine",
                      "reject": "rejected", "retire": "retired"}.get(ev.get("event"), st)
            elif ev.get("event") == "promote" and ev.get("replaces") == ref:
                st = "retired"
        return st or "unregistered"

    def incumbent(self, family: str) -> Optional[str]:
        cur = None
        for ev in self.events():
            if ev.get("event") == "promote" and ev.get("family") == family:
                cur = ev["ref"]
        return cur

    def lineage(self, ref: str) -> List[Dict[str, Any]]:
        chain, seen = [], set()
        while ref and ref not in seen:
            seen.add(ref)
            e = self.get(ref)
            chain.append({"ref": ref, "reason": e.get("reason"), "status": self.status(ref),
                          "spec_hash": e["spec_hash"]})
            ref = e.get("parent")
        return chain

    # ---------------------------------------------------------------- writing
    def _append_event(self, row: Dict[str, Any]) -> Dict[str, Any]:
        os.makedirs(self.root, exist_ok=True)
        rows = self.events()
        if rows:
            check = verify_ledger(self.ledger_path)
            if not check.ok:
                raise ValueError(f"registry ledger is corrupt: {check.errors}")
        out = dict(row)
        out["seq"] = len(rows)
        out["prev_hash"] = rows[-1]["row_hash"] if rows else GENESIS_HASH
        out["row_hash"] = row_digest(out)
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(canonical_json(out) + "\n")
        return out

    def register(self, ref: str, spec: Dict[str, Any], *, parent: Optional[str], reason: str,
                 evidence: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        family, name, version = parse_ref(ref)
        if not isinstance(spec, dict) or "arm" not in spec or "cfg" not in spec:
            raise ValueError("spec must be an object with 'arm' and 'cfg'")
        path = self.entry_path(ref)
        if os.path.exists(path):
            raise FileExistsError(f"{ref} already registered; entries are immutable, bump the version")
        if not reason or not str(reason).strip():
            raise ValueError("a reason is required for every registered config")
        if parent:
            pfam, pname, pver = parse_ref(parent)
            pentry = self.get(parent)
            if pfam != family:
                raise ValueError(f"parent {parent} is in another family")
            if pname == name:
                have = bump_kind(pver, version)
                need = required_bump(pentry["spec"], spec)
                if have is None:
                    raise ValueError(f"version {version} must be greater than parent {pver}")
                if _ORDER[have] < _ORDER[need]:
                    raise ValueError(f"{parent} -> {ref} is a {have} bump but the spec change needs a {need} bump")
        for other in self.refs(family):
            if other.split("@")[0] == f"{family}/{name}" and semver(other.split("@")[1]) >= semver(version):
                raise ValueError(f"{ref} is not newer than existing {other}")
        evidence = _hash_evidence(evidence or [], os.path.dirname(os.path.dirname(os.path.abspath(self.root))))
        entry = {"schema": SCHEMA, "ref": ref, "family": family, "name": name, "version": version,
                 "spec": spec, "spec_hash": spec_hash(spec), "parent": parent, "reason": str(reason).strip(),
                 "evidence": evidence, "registered_with_athanor": __version__}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        self._append_event({"event": "register", "ref": ref, "family": family, "spec_hash": entry["spec_hash"],
                            "parent": parent, "reason": entry["reason"], "athanor_version": __version__})
        return entry

    def record(self, event: str, ref: str, **fields: Any) -> Dict[str, Any]:
        if event not in {"promote", "refine", "reject", "retire"}:
            raise ValueError(f"unknown registry event {event!r}")
        e = self.get(ref)
        row = {"event": event, "ref": ref, "family": e["family"], "spec_hash": e["spec_hash"],
               "athanor_version": __version__}
        row.update(fields)
        return self._append_event(row)

    # ------------------------------------------------------------------ check
    def verify(self) -> Dict[str, Any]:
        errors: List[str] = []
        led = verify_ledger(self.ledger_path) if os.path.exists(self.ledger_path) else None
        if led is not None and not led.ok:
            errors.extend(led.errors)
        registered = {ev["ref"]: ev["spec_hash"] for ev in self.events() if ev.get("event") == "register"}
        for ref in self.refs():
            try:
                e = self.get(ref)
            except (ValueError, KeyError) as exc:
                errors.append(str(exc))
                continue
            h = spec_hash(e["spec"])
            if h != e.get("spec_hash"):
                errors.append(f"{ref}: spec_hash does not match spec (entry edited after registration)")
            if registered.get(ref) != h:
                errors.append(f"{ref}: spec does not match its ledger register event")
            if e.get("parent") and e["parent"] not in registered:
                errors.append(f"{ref}: parent {e['parent']} is not registered")
        for ref in registered:
            if not os.path.exists(self.entry_path(ref)):
                errors.append(f"{ref}: registered in ledger but entry file is missing")
        return {"ok": not errors, "entries": len(self.refs()), "events": len(self.events()),
                "head": led.head if led else GENESIS_HASH, "errors": errors}


def _hash_evidence(evidence: List[Dict[str, Any]], repo: str) -> List[Dict[str, Any]]:
    """Pin each evidence item whose ``source`` is a repo file with that file's SHA-256 (since 2.8.0),
    so promotion can later check it with AgentSearch ``verify_evidence`` and flag stale results."""
    out = []
    for item in evidence:
        item = dict(item) if isinstance(item, dict) else {"note": item}
        src = item.get("source")
        full = os.path.join(repo, src) if isinstance(src, str) else None
        if full and os.path.isfile(full) and "rows" in item and "rows_sha256" not in item:
            # a slice of a JSON log that keeps growing: pin the rows, not the whole file
            item["rows_sha256"] = rows_digest(full, *item["rows"])
            item["path"] = src.replace(os.sep, "/")
        elif full and os.path.isfile(full) and "sha256" not in item and "rows" not in item:
            with open(full, "rb") as f:
                item["sha256"] = hashlib.sha256(f.read()).hexdigest()
            item["path"] = src.replace(os.sep, "/")
        out.append(item)
    return out


def rows_digest(path: str, start: int, end: int) -> str:
    """SHA-256 of rows ``[start, end)`` of a JSON-list log, in canonical JSON."""
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list) or end > len(rows) or start < 0 or start >= end:
        raise ValueError(f"{path}: rows [{start}, {end}) out of range")
    return hashlib.sha256(json.dumps(rows[start:end], sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def check_row_evidence(evidence: List[Dict[str, Any]], repo: str) -> List[Dict[str, Any]]:
    """Re-verify pinned JSON-log row slices (no AgentSearch needed). Statuses: fresh, stale, missing."""
    out = []
    for item in evidence:
        if not (isinstance(item, dict) and item.get("rows_sha256") and item.get("path")):
            continue
        full = os.path.join(repo, item["path"])
        res = {"path": item["path"], "rows": item.get("rows")}
        try:
            cur = rows_digest(full, *item["rows"])
        except (OSError, ValueError) as e:
            out.append({**res, "status": "missing", "detail": str(e)})
            continue
        out.append({**res, "status": "fresh" if cur == item["rows_sha256"] else "stale",
                    "detail": None if cur == item["rows_sha256"] else "cited log rows changed"})
    return out
