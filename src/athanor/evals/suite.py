"""``athanor evals run``: replay every captured case and write a hash-chained result ledger.

Per case, three checks (all through Bug2Eval's own machinery):

1. **reference** — ``bug2eval`` validation: the captured *before* must still fail and
   the captured *after* must still pass, under the current interpreter and installed
   Athanor. For tuning cases the verifier runs the installed Athanor, so a code change
   that makes a known-good config break its limits shows up here.
2. **current** — the code or config under test is injected into the *before*
   workspace and the protected verifier is run again (verifier tampering is checked):
   bug cases get the working tree's ``src/athanor``; tuning cases get ``--candidate``.
3. **fingerprint** — tuning metrics are hashed and compared with the capture.

Status: PASS · DRIFT (passes, metrics differ from capture) · STALE (before no
longer fails, so the case stopped discriminating) · BLOCKED (the candidate config
violates a captured limit) · REGRESSION (a fix no longer holds) · ERROR.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import __version__
from ..ledger import LedgerWriter
from . import require_bug2eval
from .cases import (DEFAULT_CASES, AthanorCase, case_sha, inject_config, inject_source, load_cases,
                    parse_metrics, pinned_case)

FAILING = ("REGRESSION", "ERROR", "BLOCKED")
WARNING = ("STALE", "DRIFT")


def tree_sha(root: str) -> str:
    h = hashlib.sha256()
    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__" and not d.endswith(".egg-info"))
        for name in sorted(files):
            if name.endswith((".pyc", ".pyo")):
                continue
            p = os.path.join(dirpath, name)
            h.update(os.path.relpath(p, root).replace(os.sep, "/").encode() + b"\0")
            with open(p, "rb") as f:
                h.update(hashlib.sha256(f.read()).digest())
    return h.hexdigest()


def default_src_root() -> str:
    """The ``src`` directory that contains the imported Athanor package."""
    import athanor
    return os.path.dirname(os.path.dirname(os.path.abspath(athanor.__file__)))


def _current_check(case, ac: AthanorCase, inject) -> Dict[str, Any]:
    from bug2eval.archive import safe_extract_tar
    from bug2eval.protection import changed_paths, fingerprint, protected_paths
    from bug2eval.util import run_command
    with tempfile.TemporaryDirectory(prefix=f"athanor-eval-{ac.case_id}-") as tmp:
        ws = Path(tmp) / "workspace"
        safe_extract_tar(case.before_archive, ws)
        prot = protected_paths(case, ws)
        base = fingerprint(ws, prot)
        inject(str(ws))
        tampered = changed_paths(ws, prot, base)
        if tampered:
            return {"exit_code": None, "tampered": tampered, "stdout": "", "stderr": "protected files changed"}
        r = run_command(case.verify_argv, cwd=ws, timeout=case.timeout_sec,
                        env={"BUG2EVAL_CASE_ID": ac.case_id, "BUG2EVAL_PHASE": "athanor-current"})
        tampered = changed_paths(ws, prot, base)
        return {"exit_code": r.exit_code, "timed_out": r.timed_out, "tampered": tampered,
                "stdout": r.stdout, "stderr": r.stderr}


def _tail(s: str, n: int = 2) -> str:
    return "\n".join((s or "").strip().splitlines()[-n:])


def evaluate_case(ac: AthanorCase, *, src_root: str, candidate: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from bug2eval.integrity import verify_integrity
    from bug2eval.runner import validate_case
    t0 = time.monotonic()
    row: Dict[str, Any] = {"type": "case", "case_id": ac.case_id, "kind": ac.kind, "family": ac.family,
                           "case_sha": case_sha(ac.path)}
    notes: List[str] = []
    try:
        if row["case_sha"] != ac.sidecar.get("case_sha"):
            raise ValueError("metadata.json no longer matches the case_sha recorded at capture")
        case = pinned_case(ac.path)
        verify_integrity(case)
        v = validate_case(case)
        row["before_exit"], row["after_exit"] = v["before"]["exit_code"], v["after"]["exit_code"]
        after_m = parse_metrics(v["after"]["stdout"]) if ac.kind == "tuning" else None
        current = None
        if ac.kind == "bug":
            current = _current_check(case, ac, lambda ws: inject_source(ws, src_root))
        elif candidate is not None and candidate.get("family") == ac.family:
            current = _current_check(case, ac, lambda ws: inject_config(ws, candidate["spec"]))
            row["candidate"] = candidate.get("ref")
        row["current_exit"] = current["exit_code"] if current else None
        cur_m = parse_metrics(current["stdout"]) if (current and ac.kind == "tuning") else None
        if ac.kind == "tuning":
            row["after_fingerprint"] = after_m and after_m["fingerprint"]
            row["recorded_fingerprint"] = ac.sidecar.get("recorded", {}).get("after_fingerprint")
            if cur_m:
                row["current_fingerprint"] = cur_m["fingerprint"]
                row["current_metrics"] = cur_m["metrics"]
                row["current_violations"] = cur_m["violations"]
        # ---- classify
        if current and current.get("tampered"):
            status = "ERROR"
            notes.append("protected verifier files changed: " + ", ".join(current["tampered"]))
        elif v["after"]["exit_code"] != 0 or v["after"].get("timed_out"):
            status = "REGRESSION"
            notes.append("reference fix no longer passes: " + _tail(v["after"]["stdout"] + v["after"]["stderr"]))
        elif ac.kind == "bug" and current["exit_code"] != 0:
            status = "REGRESSION"
            notes.append("code under test re-introduces the bug: " + _tail(current["stdout"] + current["stderr"]))
        elif ac.kind == "tuning" and current and current["exit_code"] not in (0, 1):
            status = "ERROR"
            notes.append("candidate verification errored: " + _tail(current["stdout"] + current["stderr"]))
        elif ac.kind == "tuning" and current and current["exit_code"] == 1:
            status = "BLOCKED"
            notes.append("candidate violates: " + "; ".join((cur_m or {}).get("violations") or ["?"]))
        elif v["before"]["exit_code"] == 0:
            status = "STALE"
            notes.append("captured failure no longer reproduces; the case no longer discriminates")
        elif ac.kind == "tuning" and row.get("after_fingerprint") != row.get("recorded_fingerprint"):
            status = "DRIFT"
            notes.append("reference metrics differ from capture (still within limits)")
        else:
            status = "PASS"
    except Exception as exc:  # noqa: BLE001 - every failure is reported, never swallowed
        status = "ERROR"
        notes.append(f"{type(exc).__name__}: {exc}")
    row["status"] = status
    row["notes"] = notes
    return {"row": row, "seconds": round(time.monotonic() - t0, 2)}


def _evidence_checker(repo: Optional[str]):
    """AgentSearch-backed citation checks, or None when the [search] extra is unavailable."""
    from ..search import search_available
    if not search_available():
        return None
    from ..search import EvidenceIndex
    return EvidenceIndex(repo or ".")


def run_suite(*, cases_root: str = DEFAULT_CASES, out_dir: Optional[str] = None, ids: Optional[List[str]] = None,
              kinds: Optional[List[str]] = None, candidate: Optional[Dict[str, Any]] = None,
              src_root: Optional[str] = None, strict: bool = False, repo: Optional[str] = None,
              check_evidence: bool = True) -> Dict[str, Any]:
    b2e = require_bug2eval()
    src_root = os.path.abspath(src_root or default_src_root())
    cases = load_cases(cases_root, ids=ids, kinds=kinds)
    if not cases:
        raise ValueError(f"no eval cases found in {cases_root}")
    out_dir = out_dir or os.path.join("data", "evals", "run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    os.makedirs(out_dir, exist_ok=True)
    writer = LedgerWriter(os.path.join(out_dir, "ledger.jsonl"))
    writer.append({"type": "suite", "athanor_version": __version__, "bug2eval_version": b2e.__version__,
                   "code_sha": tree_sha(os.path.join(src_root, "athanor")),
                   "candidate": candidate.get("ref") if candidate else None,
                   "candidate_spec_hash": candidate.get("spec_hash") if candidate else None,
                   "cases": [c.case_id for c in cases], "strict": bool(strict)})
    results, timings, stale_evidence = [], {}, {}
    repo = repo or os.path.dirname(os.path.dirname(os.path.abspath(cases_root)))
    idx = _evidence_checker(repo) if check_evidence else None
    try:
        from .evidence import check_case
        for ac in cases:
            r = evaluate_case(ac, src_root=src_root, candidate=candidate)
            if idx is not None:
                chk = check_case(ac, idx=idx)
                if chk is not None:
                    r["row"]["evidence"] = {"checked": chk["checked"], "stale": len(chk["stale"]),
                                            "hard": len(chk["hard"])}
                    if chk["stale"]:
                        stale_evidence[ac.case_id] = [{k: x.get(k) for k in ("path", "status", "detail")}
                                                      for x in chk["stale"]]
                        r["row"]["notes"].append(f"{len(chk['stale'])} cited source(s) changed since capture")
            writer.append(r["row"])
            results.append(r["row"])
            timings[ac.case_id] = r["seconds"]
    finally:
        if idx is not None:
            idx.close()
    counts: Dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    bad = [r["case_id"] for r in results if r["status"] in FAILING or (strict and r["status"] in WARNING)]
    summary = {"ok": not bad, "failing": bad, "counts": counts, "cases": len(results),
               "suite_digest": writer.head, "ledger": os.path.join(out_dir, "ledger.jsonl"),
               "out_dir": out_dir, "candidate": candidate.get("ref") if candidate else None,
               "results": [{k: r.get(k) for k in ("case_id", "kind", "status", "notes", "before_exit",
                                                  "after_exit", "current_exit")} for r in results],
               "seconds": timings, "evidence_checked": idx is not None, "stale_evidence": stale_evidence}
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    return summary
