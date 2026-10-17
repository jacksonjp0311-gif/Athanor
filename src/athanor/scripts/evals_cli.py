"""``athanor evals ...`` and ``athanor registry ...`` subcommands (Bug2Eval integration)."""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from ..config_registry import DEFAULT_ROOT, Registry, parse_ref


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def _seeds(text: str):
    from .cli import _parse_seeds
    return _parse_seeds(text)


def _candidate(reg: Registry, ref: str) -> Dict[str, Any]:
    e = reg.get(ref)
    return {"ref": ref, "family": e["family"], "spec": e["spec"], "spec_hash": e["spec_hash"]}


# ----------------------------------------------------------------- evals
def _evals_list(a) -> int:
    from ..evals.cases import load_cases
    rows = []
    for c in load_cases(a.cases):
        p = c.sidecar.get("provenance", {})
        rows.append({"case_id": c.case_id, "kind": c.kind, "family": c.family, "title": c.meta["title"],
                     "captured_with": c.sidecar.get("athanor_version"),
                     "source": p.get("after_commit", "")[:10] if c.kind == "bug" else f"{p.get('bad')} -> {p.get('good')}"})
    _print(rows)
    return 0


def _evals_capture_bug(a) -> int:
    from ..evals.capture import capture_bug
    out = capture_bug(case_id=a.case_id, title=a.title, before_ref=a.before_ref, after_ref=a.after_ref,
                      verifier=a.verifier, repo=a.repo, out_root=a.cases, paths=a.path or ["src"],
                      prompt=a.prompt, timeout=a.timeout, force=a.force, cites=_cites(a),
                      attach_evidence=False if a.no_evidence else None)
    _print({"case": out["case"], "validation": out["validation"], "evidence": out.get("evidence")})
    return 0


def _evals_capture_tuning(a) -> int:
    from ..evals.capture import capture_tuning, parse_limit
    ev = json.loads(a.evidence) if a.evidence else {}
    out = capture_tuning(case_id=a.case_id, title=a.title, bad_ref=a.bad, good_ref=a.good, seeds=_seeds(a.seeds),
                         steps=a.steps, limits=[parse_limit(x) for x in a.limit], registry=Registry(a.registry),
                         out_root=a.cases, evidence=ev, prompt=a.prompt, timeout=a.timeout, force=a.force,
                         cites=_cites(a), attach_evidence=False if a.no_evidence else None)
    _print({"case": out["case"], "validation": out["validation"], "recorded": out["sidecar"]["recorded"],
            "evidence": out.get("evidence")})
    return 0


def _cites(a):
    from ..evals.evidence import parse_cite
    return [parse_cite(c) for c in (getattr(a, "cite", None) or [])]


def _evals_evidence(a) -> int:
    from ..evals.cases import load_cases
    from ..evals.evidence import attach, check_case
    cases = load_cases(a.cases, ids=a.case or None)
    out = []
    for ac in cases:
        if a.check:
            chk = check_case(ac)
            out.append({"case_id": ac.case_id, "checked": chk and chk["checked"],
                        "stale": chk and [{k: x.get(k) for k in ("path", "status", "detail")} for x in chk["stale"]]})
        else:
            out.append(attach(ac, _cites(a), refresh=not a.no_refresh))
    _print(out)
    if a.check and any(r["stale"] for r in out):
        return 1
    return 0


def _evals_run(a) -> int:
    from ..evals.suite import run_suite
    reg = Registry(a.registry)
    cand = _candidate(reg, a.candidate) if a.candidate else None
    res = run_suite(cases_root=a.cases, out_dir=a.out, ids=a.case or None, kinds=a.kind or None,
                    candidate=cand, src_root=a.src, strict=a.strict)
    _print(res)
    return 0 if res["ok"] else 1


# -------------------------------------------------------------- registry
def _reg_list(a) -> int:
    reg = Registry(a.registry)
    fams = {}
    out = []
    for ref in reg.refs(a.family):
        e = reg.get(ref)
        fam = e["family"]
        fams.setdefault(fam, reg.incumbent(fam))
        out.append({"ref": ref, "status": reg.status(ref), "spec_hash": e["spec_hash"][:12],
                    "parent": e.get("parent"), "reason": e["reason"]})
    _print({"incumbents": fams, "configs": out})
    return 0


def _reg_show(a) -> int:
    reg = Registry(a.registry)
    e = reg.get(a.ref)
    _print({**e, "status": reg.status(a.ref),
            "events": [ev for ev in reg.events() if ev.get("ref") == a.ref]})
    return 0


def _reg_lineage(a) -> int:
    _print(Registry(a.registry).lineage(a.ref))
    return 0


def _reg_register(a) -> int:
    from .._cfgset import apply_sets
    reg = Registry(a.registry)
    if a.spec:
        with open(a.spec, encoding="utf-8") as f:
            spec = json.load(f)
    elif a.parent:
        spec = json.loads(json.dumps(reg.get(a.parent)["spec"]))
    else:
        raise SystemExit("give --spec FILE or --parent REF (with --set key=value overrides)")
    spec = apply_sets(spec, a.set or [])
    ev = json.loads(a.evidence) if a.evidence else []
    entry = reg.register(a.ref, spec, parent=a.parent, reason=a.reason, evidence=ev if isinstance(ev, list) else [ev])
    _print(entry)
    return 0


def _reg_promote(a) -> int:
    from ..evals.promotion import GATE_SEEDS, promote
    rep = promote(Registry(a.registry), a.ref, cases_root=a.cases, out_dir=a.out,
                  seeds=_seeds(a.gate_seeds) if a.gate_seeds else GATE_SEEDS, steps=a.steps,
                  allow_refine=a.allow_refine, dry_run=a.dry_run, src_root=a.src, bootstrap=a.bootstrap,
                  require_fresh_evidence=a.require_fresh_evidence)
    _print(rep)
    return 0 if rep["decision"] == "promote" else 1


def _reg_verify(a) -> int:
    res = Registry(a.registry).verify()
    _print(res)
    return 0 if res["ok"] else 1


def _guard(fn):
    def wrapped(a) -> int:
        from ..evals import EvalsUnavailable
        from ..search import SearchUnavailable
        try:
            return fn(a)
        except (EvalsUnavailable, SearchUnavailable, ValueError, KeyError, FileExistsError, FileNotFoundError, RuntimeError) as exc:
            _print({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            return 2
    return wrapped


def add_parsers(sub) -> None:
    common_cases = dict(default=os.path.join("evals", "cases"), help="case directory (default: evals/cases)")
    common_reg = dict(default=DEFAULT_ROOT, help="config registry (default: configs/registry)")

    ev = sub.add_parser("evals", help="Bug2Eval regression suite: capture, list and run eval cases")
    es = ev.add_subparsers(dest="evals_cmd", required=True)

    p = es.add_parser("list", help="list captured eval cases")
    p.add_argument("--cases", **common_cases)
    p.set_defaults(fn=_g_evals_list)

    cap = es.add_parser("capture", help="capture a fixed bug or a failed tuning config as an eval case")
    cs = cap.add_subparsers(dest="capture_kind", required=True)
    p = cs.add_parser("bug", help="a fixed bug: before/after commits plus a verifier script")
    p.add_argument("--id", dest="case_id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--before-ref", required=True, help="commit with the bug")
    p.add_argument("--after-ref", required=True, help="commit with the fix")
    p.add_argument("--verifier", required=True, help="script that exits non-zero on the bug, 0 when fixed")
    p.add_argument("--path", action="append", help="repo paths to snapshot (default: src); repeatable")
    p.add_argument("--repo", default=".")
    p.add_argument("--prompt", default=None)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--cite", action="append", help="evidence to attach: PATH or PATH:literal text (needs athanor[search])")
    p.add_argument("--no-evidence", action="store_true", help="do not attach AgentSearch citations")
    p.add_argument("--force", action="store_true")
    p.add_argument("--cases", **common_cases)
    p.set_defaults(fn=_g_evals_capture_bug)
    p = cs.add_parser("tuning", help="a tuning failure: a registered bad config, a good one, seeds and limits")
    p.add_argument("--id", dest="case_id", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--bad", required=True, help="registry ref that violates the limits, e.g. selfmod/adaptive@1.0.0")
    p.add_argument("--good", required=True, help="registry ref that satisfies them")
    p.add_argument("--seeds", required=True, help="e.g. 0-15")
    p.add_argument("--steps", type=int, default=1000)
    p.add_argument("--limit", action="append", required=True, help="e.g. severe_regressions<=10; repeatable")
    p.add_argument("--evidence", default=None, help="JSON object: where the failure was measured")
    p.add_argument("--prompt", default=None)
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--cite", action="append", help="evidence to attach: PATH or PATH:literal text (needs athanor[search])")
    p.add_argument("--no-evidence", action="store_true", help="do not attach AgentSearch citations")
    p.add_argument("--force", action="store_true")
    p.add_argument("--cases", **common_cases)
    p.add_argument("--registry", **common_reg)
    p.set_defaults(fn=_g_evals_capture_tuning)

    p = es.add_parser("evidence", help="attach (default) or --check AgentSearch citations of cases (athanor[search])")
    p.add_argument("--case", action="append", help="case id; repeatable (default: all)")
    p.add_argument("--cite", action="append", help="extra citation PATH or PATH:literal text")
    p.add_argument("--check", action="store_true", help="re-verify citations; exit 1 if any are stale")
    p.add_argument("--no-refresh", action="store_true", help="do not rescan the index first")
    p.add_argument("--cases", **common_cases)
    p.set_defaults(fn=_g_evals_evidence)

    p = es.add_parser("run", help="run the suite and write a hash-chained ledger (exit 1 on failure)")
    p.add_argument("--case", action="append", help="only this case id; repeatable")
    p.add_argument("--kind", action="append", choices=["bug", "tuning"])
    p.add_argument("--candidate", default=None, help="registry ref to inject into tuning cases")
    p.add_argument("--src", default=None, help="src dir whose athanor package is injected into bug cases "
                                               "(default: the imported package)")
    p.add_argument("--out", default=None, help="output dir (default: data/evals/run_<UTC>)")
    p.add_argument("--strict", action="store_true", help="also fail on STALE and DRIFT")
    p.add_argument("--cases", **common_cases)
    p.add_argument("--registry", **common_reg)
    p.set_defaults(fn=_g_evals_run)

    rg = sub.add_parser("registry", help="versioned config registry with eval-gated promotion")
    rs = rg.add_subparsers(dest="registry_cmd", required=True)
    p = rs.add_parser("list", help="configs, statuses and incumbents")
    p.add_argument("--family", default=None)
    p.add_argument("--registry", **common_reg)
    p.set_defaults(fn=_g_reg_list)
    p = rs.add_parser("show", help="one config with its events")
    p.add_argument("ref")
    p.add_argument("--registry", **common_reg)
    p.set_defaults(fn=_g_reg_show)
    p = rs.add_parser("lineage", help="parent chain of a config")
    p.add_argument("ref")
    p.add_argument("--registry", **common_reg)
    p.set_defaults(fn=_g_reg_lineage)
    p = rs.add_parser("register", help="add an immutable, versioned config (semver bump rules enforced)")
    p.add_argument("ref", help="family/name@MAJOR.MINOR.PATCH")
    p.add_argument("--parent", default=None)
    p.add_argument("--spec", default=None, help='JSON file {"arm": {...}, "cfg": {...}}')
    p.add_argument("--set", action="append", help="override, e.g. cfg.threshold_h7=0.75 or arm.gamma=6")
    p.add_argument("--reason", required=True)
    p.add_argument("--evidence", default=None, help="JSON object or list")
    p.add_argument("--registry", **common_reg)
    p.set_defaults(fn=_g_reg_register)
    p = rs.add_parser("promote", help="eval suite + Athanor verdict vs the incumbent; records the decision")
    p.add_argument("ref")
    p.add_argument("--gate-seeds", default=None, help="default 200-215 (fresh seeds)")
    p.add_argument("--steps", type=int, default=1000)
    p.add_argument("--allow-refine", action="store_true")
    p.add_argument("--bootstrap", action="store_true", help="first promotion in a family (no incumbent)")
    p.add_argument("--dry-run", action="store_true", help="evaluate but do not record")
    p.add_argument("--require-fresh-evidence", action="store_true",
                   help="hold (refine) if a cited source is stale or missing (athanor[search])")
    p.add_argument("--out", default=None)
    p.add_argument("--src", default=None)
    p.add_argument("--cases", **common_cases)
    p.add_argument("--registry", **common_reg)
    p.set_defaults(fn=_g_reg_promote)
    p = rs.add_parser("verify", help="check the registry ledger chain and every entry's content hash")
    p.add_argument("--registry", **common_reg)
    p.set_defaults(fn=_g_reg_verify)


_g_evals_capture_bug = _guard(_evals_capture_bug)
_g_evals_capture_tuning = _guard(_evals_capture_tuning)
_g_evals_list = _guard(_evals_list)
_g_evals_evidence = _guard(_evals_evidence)
_g_evals_run = _guard(_evals_run)
_g_reg_lineage = _guard(_reg_lineage)
_g_reg_list = _guard(_reg_list)
_g_reg_promote = _guard(_reg_promote)
_g_reg_register = _guard(_reg_register)
_g_reg_show = _guard(_reg_show)
_g_reg_verify = _guard(_reg_verify)
