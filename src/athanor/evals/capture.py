"""``athanor evals capture``: turn a fixed bug or a failed tuning config into a Bug2Eval case."""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .. import __version__
from ..config_registry import Registry
from . import require_bug2eval
from .cases import DEFAULT_CASES, SIDECAR, SIDECAR_SCHEMA, case_sha, parse_metrics, pinned_case

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "verify_config.py")
LIMIT_OPS = ("<=", ">=", "<", ">")


def _git(repo: str, *args: str) -> str:
    cp = subprocess.run(["git", "-C", repo, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if cp.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {cp.stderr.strip()}")
    return cp.stdout


def _export_tree(repo: str, ref: str, paths: Sequence[str], dest: str) -> None:
    data = subprocess.run(["git", "-C", repo, "archive", "--format=tar", ref, *paths],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if data.returncode != 0:
        raise RuntimeError(f"git archive {ref} failed: {data.stderr.decode(errors='replace').strip()}")
    os.makedirs(dest, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data.stdout)) as tf:
        for m in tf.getmembers():
            if not (m.isfile() or m.isdir()) or m.name.startswith("/") or ".." in m.name.split("/"):
                raise RuntimeError(f"unexpected member in git archive: {m.name}")
        tf.extractall(dest, **({'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}))


def _tail(text: str, n: int = 3) -> str:
    return "\n".join((text or "").strip().splitlines()[-n:])


def _write_sidecar(case_dir: str, side: Dict[str, Any]) -> Dict[str, Any]:
    side = {"schema": SIDECAR_SCHEMA, **side, "case_sha": case_sha(case_dir)}
    with open(os.path.join(case_dir, SIDECAR), "w", encoding="utf-8") as f:
        json.dump(side, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    return side


def _validate_or_discard(case_dir: str, *, force_kind: str) -> Dict[str, Any]:
    from bug2eval.runner import validate_case
    res = validate_case(pinned_case(case_dir))
    problems = list(res["reasons"])
    if force_kind == "tuning" and res["before"]["exit_code"] != 1:
        problems.append(f"bad config must violate a limit (exit 1), got exit {res['before']['exit_code']}: "
                        f"{_tail(res['before']['stdout'] + res['before']['stderr'])}")
    if not res["valid"] or problems:
        shutil.rmtree(case_dir, ignore_errors=True)
        raise ValueError("case does not discriminate, so it was not saved: " + "; ".join(problems))
    return res


def capture_bug(*, case_id: str, title: str, before_ref: str, after_ref: str, verifier: str,
                repo: str = ".", out_root: str = DEFAULT_CASES, paths: Sequence[str] = ("src",),
                prompt: Optional[str] = None, tags: Optional[List[str]] = None, timeout: int = 300,
                force: bool = False, cites: Sequence = (), attach_evidence: Optional[bool] = None) -> Dict[str, Any]:
    """Capture a fixed Athanor bug. Workspaces are ``paths`` at each commit plus the protected verifier."""
    require_bug2eval()
    from bug2eval.capture import capture_directories
    import bug2eval
    repo = os.path.abspath(repo)
    before = _git(repo, "rev-parse", "--verify", f"{before_ref}^{{commit}}").strip()
    after = _git(repo, "rev-parse", "--verify", f"{after_ref}^{{commit}}").strip()
    vname = os.path.basename(verifier)
    changed = [p for p in _git(repo, "diff", "--name-only", before, after, "--", *paths).splitlines() if p]
    subject = _git(repo, "log", "-1", "--format=%s", after).strip()
    out = os.path.join(out_root, case_id)
    with tempfile.TemporaryDirectory(prefix="athanor-capture-") as tmp:
        for which, ref in (("before", before), ("after", after)):
            d = os.path.join(tmp, which)
            _export_tree(repo, ref, paths, d)
            shutil.copy2(verifier, os.path.join(d, vname))
        if os.path.exists(out) and force:
            shutil.rmtree(out)
        capture_directories(
            before_dir=Path(tmp, "before"), after_dir=Path(tmp, "after"), output=Path(out), case_id=case_id,
            title=title, verify_argv=["python", vname], timeout_sec=int(timeout),
            prompt_text=prompt or f"# {title}\n\nThe Athanor package is in `src/athanor`. `{vname}` reproduces the "
                                  "bug. Fix the package so the verifier passes without editing the verifier.\n",
            tags=["athanor", "bug", *(tags or [])], protected_paths=[vname])
    res = _validate_or_discard(out, force_kind="bug")
    side = _write_sidecar(out, {
        "case_id": case_id, "kind": "bug", "inject": "source", "family": None,
        "athanor_version": __version__, "bug2eval_version": bug2eval.__version__,
        "provenance": {"before_ref": before_ref, "before_commit": before, "after_ref": after_ref,
                       "after_commit": after, "fix_subject": subject, "changed_files": changed,
                       "snapshot_paths": list(paths), "verifier": vname},
        "recorded": {"before_exit": res["before"]["exit_code"], "after_exit": res["after"]["exit_code"],
                     "before_output": _tail(res["before"]["stdout"] + res["before"]["stderr"], 2),
                     "after_output": _tail(res["after"]["stdout"], 1)},
    })
    ev = _maybe_evidence(out, cites, repo, attach_evidence)
    return {"case": out, "validation": {"valid": res["valid"], "before": res["before"]["exit_code"],
                                        "after": res["after"]["exit_code"]}, "sidecar": side, "evidence": ev}


def _maybe_evidence(case_dir: str, cites: Sequence, repo: str, evidence: Optional[bool]):
    """Attach AgentSearch citations: always if ``evidence`` is True, if available when it is None."""
    from ..search import search_available
    if evidence is False or (evidence is None and not search_available()):
        return None
    from .evidence import attach
    return attach(case_dir, list(cites), repo=repo)


def parse_limit(text: str) -> Dict[str, Any]:
    for op in LIMIT_OPS:
        if op in text:
            metric, value = text.split(op, 1)
            return {"metric": metric.strip(), "op": op, "value": float(value)}
    raise ValueError(f"bad limit {text!r}; expected e.g. severe_regressions<=10")


DEFAULT_FINGERPRINT = ["broken_commits", "severe_regressions", "commits", "never_reached_1p5",
                       "median_steps_to_1p5", "median_mse_100", "median_mse_final"]
TSP_FINGERPRINT = ["broken_commits", "severe_regressions", "commits", "never_good", "frozen_runs",
                   "median_steps_to_good", "median_held_50", "median_held_1000"]
FINGERPRINTS = {"selfmod": DEFAULT_FINGERPRINT, "tsp": TSP_FINGERPRINT}


def capture_tuning(*, case_id: str, title: str, bad_ref: str, good_ref: str, seeds: Sequence[int], steps: int,
                   limits: Sequence[Dict[str, Any]], registry: Registry, out_root: str = DEFAULT_CASES,
                   evidence: Optional[Dict[str, Any]] = None, prompt: Optional[str] = None,
                   fingerprint_metrics: Optional[Sequence[str]] = None, timeout: int = 900,
                   tags: Optional[List[str]] = None, force: bool = False, cites: Sequence = (),
                   attach_evidence: Optional[bool] = None, repo: str = ".") -> Dict[str, Any]:
    """Capture a tuning failure: ``bad_ref`` violates ``limits`` on ``seeds``; ``good_ref`` satisfies them."""
    require_bug2eval()
    from bug2eval.capture import capture_directories
    import bug2eval
    bad, good = registry.get(bad_ref), registry.get(good_ref)
    if bad["family"] != good["family"]:
        raise ValueError("bad and good configs must be in the same family")
    if not limits:
        raise ValueError("at least one --limit is required")
    if bad["family"] not in FINGERPRINTS:
        raise ValueError(f"family {bad['family']!r} has no experiment runner (supported: {', '.join(FINGERPRINTS)})")
    fingerprint_metrics = list(fingerprint_metrics or FINGERPRINTS[bad["family"]])
    case = {"family": bad["family"], "seeds": [int(s) for s in seeds], "steps": int(steps),
            "limits": list(limits), "fingerprint_metrics": list(fingerprint_metrics),
            "bad": bad_ref, "good": good_ref}
    out = os.path.join(out_root, case_id)
    lim_txt = ", ".join(f"`{l['metric']} {l['op']} {l['value']:g}`" for l in limits)
    with tempfile.TemporaryDirectory(prefix="athanor-capture-") as tmp:
        for which, entry in (("before", bad), ("after", good)):
            d = os.path.join(tmp, which)
            os.makedirs(d)
            shutil.copy2(TEMPLATE, os.path.join(d, "verify_config.py"))
            with open(os.path.join(d, "case.json"), "w", encoding="utf-8") as f:
                json.dump(case, f, indent=2, sort_keys=True)
                f.write("\n")
            with open(os.path.join(d, "config.json"), "w", encoding="utf-8") as f:
                json.dump({"arm": entry["spec"]["arm"], "cfg": entry["spec"]["cfg"]}, f, indent=2, sort_keys=True)
                f.write("\n")
        if os.path.exists(out) and force:
            shutil.rmtree(out)
        capture_directories(
            before_dir=Path(tmp, "before"), after_dir=Path(tmp, "after"), output=Path(out), case_id=case_id,
            title=title, verify_argv=["python", "verify_config.py"], timeout_sec=int(timeout),
            prompt_text=prompt or (f"# {title}\n\nEdit `config.json` (an Athanor `{bad['family']}` arm + cfg) so that, "
                                   f"on seeds {case['seeds'][0]}–{case['seeds'][-1]} for {steps} steps, {lim_txt} "
                                   "all hold. Do not edit `case.json` or `verify_config.py`.\n"),
            tags=["athanor", "tuning", bad["family"], *(tags or [])],
            protected_paths=["verify_config.py", "case.json"])
    res = _validate_or_discard(out, force_kind="tuning")
    mb, ma = parse_metrics(res["before"]["stdout"]), parse_metrics(res["after"]["stdout"])
    side = _write_sidecar(out, {
        "case_id": case_id, "kind": "tuning", "inject": "config", "family": bad["family"],
        "athanor_version": __version__, "bug2eval_version": bug2eval.__version__,
        "provenance": {"bad": bad_ref, "bad_spec_hash": bad["spec_hash"], "good": good_ref,
                       "good_spec_hash": good["spec_hash"], "evidence": evidence or {}},
        "contract": case,
        "recorded": {"before_exit": res["before"]["exit_code"], "after_exit": res["after"]["exit_code"],
                     "before_metrics": mb and mb["metrics"], "before_violations": mb and mb["violations"],
                     "after_metrics": ma and ma["metrics"],
                     "before_fingerprint": mb and mb["fingerprint"], "after_fingerprint": ma and ma["fingerprint"]},
    })
    return {"case": out, "validation": {"valid": res["valid"], "before": res["before"]["exit_code"],
                                        "after": res["after"]["exit_code"]}, "sidecar": side,
            "evidence": _maybe_evidence(out, cites, repo, attach_evidence)}
