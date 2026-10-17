"""Operational commands (3.0.0): ``athanor doctor`` and ``athanor demo``."""
from __future__ import annotations

import importlib
import json
import os
import platform
import sys
import tempfile
import time
from typing import Any, Dict, List

from .. import __version__

DEMO_CONFIG = {"generations": 12, "population": 10, "steps_per_candidate": 18}  # = configs/toy_experiment.yaml


def _find_repo(start: str = ".") -> str | None:
    """The ATHANOR checkout containing ``start``, if any (has configs/registry and evals/cases)."""
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, "configs", "registry")) and os.path.isdir(os.path.join(d, "evals", "cases")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _check(name: str, fn) -> Dict[str, Any]:
    t = time.time()
    try:
        status, detail = fn()
    except Exception as exc:  # noqa: BLE001 - doctor reports, never crashes
        status, detail = "FAIL", f"{type(exc).__name__}: {exc}"
    return {"check": name, "status": status, "detail": detail, "seconds": round(time.time() - t, 2)}


def doctor_checks(repo: str | None = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    py = sys.version_info

    out.append(_check("python", lambda: ("OK" if py >= (3, 10) else "FAIL",
                                         f"{platform.python_version()} ({sys.executable})"
                                         + ("" if py >= (3, 10) else " - ATHANOR needs Python 3.10+"))))
    import athanor
    out.append(_check("athanor", lambda: ("OK", f"{__version__} at {os.path.dirname(athanor.__file__)}")))

    def dep(mod, hint):
        def f():
            try:
                m = importlib.import_module(mod)
            except ImportError:
                return "FAIL", f"not importable - {hint}"
            return "OK", getattr(m, "__version__", "installed")
        return f
    for mod in ("numpy", "yaml", "matplotlib"):
        out.append(_check(mod, dep(mod, "reinstall: pip install --force-reinstall athanor (from GitHub)")))

    def evals():
        from ..evals import bug2eval_available
        if bug2eval_available():
            import bug2eval
            return "OK", f"bug2eval {bug2eval.__version__} ([evals] extra)"
        return "INFO", 'optional [evals] extra not installed: pip install "athanor[evals] @ git+https://github.com/jacksonjp0311-gif/Athanor.git"'
    out.append(_check("extra: evals", evals))

    def search():
        from ..search import search_available
        if search_available():
            import agentsearch
            return "OK", f"agentsearch {agentsearch.__version__} ([search] extra)"
        if py < (3, 11):
            return "INFO", "optional [search] extra needs Python 3.11+"
        return "INFO", 'optional [search] extra not installed: pip install "athanor[search] @ git+https://github.com/jacksonjp0311-gif/Athanor.git"'
    out.append(_check("extra: search", search))

    def gate():
        from ..governor import Governor
        g = Governor(lambda p: [p * x for x in (1.0, 2.0, 3.0)], scale=1.0)
        a, r = g.judge(1.0, 1.05).verdict, g.judge(1.0, 9.0).verdict
        ok = (a, r) == ("APPROVE", "REJECT")
        return ("OK" if ok else "FAIL"), f"small edit {a}, large edit {r} (expected APPROVE, REJECT)"
    out.append(_check("governor self-test", gate))

    def loop():
        from ..evolution.dgm_loop import run as run_loop
        from ..experiments.registry import validate_config
        from ..ledger import verify_ledger
        with tempfile.TemporaryDirectory() as tmp:
            cfg = validate_config({**DEMO_CONFIG, "generations": 3, "run": {"out_dir": tmp, "tag": "doctor"}})
            a = run_loop(cfg)
            cfg2 = validate_config({**DEMO_CONFIG, "generations": 3, "run": {"out_dir": tmp, "tag": "doctor2"}})
            b = run_loop(cfg2)
            v = verify_ledger(os.path.join(a["run_path"], "ledger.jsonl"))
            det = a["run_digest"] == b["run_digest"]
            ok = v.ok and det
            return ("OK" if ok else "FAIL"), (f"3-generation run: ledger {'verified' if v.ok else 'BROKEN'}, "
                                             f"{'deterministic' if det else 'NOT deterministic'} (digest {a['run_digest'][:12]})")
    out.append(_check("run + verify + determinism", loop))

    repo = repo or _find_repo()
    if repo:
        def registry():
            from ..config_registry import Registry
            r = Registry(os.path.join(repo, "configs", "registry")).verify()
            return ("OK" if r["ok"] else "FAIL"), f"{r['entries']} entries, {r['events']} ledger events" + \
                ("" if r["ok"] else f": {r.get('errors')}")
        out.append(_check("repo: config registry", registry))

        def cases():
            n = len([d for d in os.listdir(os.path.join(repo, "evals", "cases")) if not d.startswith(".")])
            return "OK", f"{n} eval cases in evals/cases (run them: athanor evals run)"
        out.append(_check("repo: eval cases", cases))
    else:
        out.append({"check": "repo", "status": "INFO", "detail": "not inside an ATHANOR checkout; repo checks skipped",
                    "seconds": 0.0})
    return out


def cmd_doctor(args) -> int:
    res = doctor_checks()
    if args.json:
        print(json.dumps({"ok": all(r["status"] != "FAIL" for r in res), "checks": res}, indent=2))
    else:
        width = max(len(r["check"]) for r in res)
        for r in res:
            print(f"[{r['status']:>4}] {r['check']:<{width}}  {r['detail']}")
        fails = [r for r in res if r["status"] == "FAIL"]
        print(f"\n{'all good' if not fails else str(len(fails)) + ' problem(s) found'} - athanor {__version__}")
    return 1 if any(r["status"] == "FAIL" for r in res) else 0


def cmd_demo(args) -> int:
    """run → verify → tamper check → replay → (evals run) in one command."""
    from ..evolution.dgm_loop import run as run_loop
    from ..experiments.registry import validate_config
    from ..ledger import verify_ledger
    from .cli import diff_runs
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    steps: List[Dict[str, Any]] = []

    def say(step, ok, detail):
        steps.append({"step": step, "ok": bool(ok), "detail": detail})
        print(f"{'✔' if ok else '✘'} {step:<10} {detail}", flush=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    cfg = validate_config({**DEMO_CONFIG, "run": {"out_dir": out_dir, "tag": f"demo_{stamp}"}})
    t = time.time()
    a = run_loop(cfg)
    vc = a["stats"]["verdict_counts"]
    say("run", True, f"{a['run_path']}  ({vc.get('APPROVE', 0)} APPROVE / {vc.get('REFINE', 0)} REFINE / "
                     f"{vc.get('REJECT', 0)} REJECT, {time.time() - t:.1f}s)")
    v = verify_ledger(os.path.join(a["run_path"], "ledger.jsonl"))
    say("verify", v.ok, f"{v.rows} ledger rows, hash chain intact, head {str(v.head)[:16]}")
    with open(os.path.join(a["run_path"], "config.json"), encoding="utf-8") as f:
        replay_cfg = json.load(f)                     # replay = re-run from the recorded config.json
    replay_cfg.setdefault("run", {}).update({"out_dir": out_dir, "tag": f"demo_{stamp}_replay"})
    replay_cfg = validate_config(replay_cfg)
    b = run_loop(replay_cfg)
    d = diff_runs(a["run_path"], b["run_path"])
    say("replay", d["identical"], f"same config + seed -> {'identical' if d['identical'] else 'DIFFERENT'} digest "
                                  f"{str(d['digest_b'])[:16]}")
    if args.skip_evals:
        say("evals", True, "skipped (--skip-evals)")
    else:
        from ..evals import bug2eval_available
        repo = _find_repo()
        if not bug2eval_available():
            say("evals", True, 'skipped: install the [evals] extra to replay the regression suite')
        elif not repo:
            say("evals", True, "skipped: run inside an ATHANOR checkout to replay evals/cases")
        else:
            from ..evals.suite import run_suite
            kinds = None if args.full_evals else ["bug"]
            t = time.time()
            r = run_suite(cases_root=os.path.join(repo, "evals", "cases"), out_dir=os.path.join(out_dir, "evals"),
                          kinds=kinds)
            say("evals", r["ok"], f"{r['counts']} ({'all cases' if args.full_evals else 'bug cases; --full-evals for all'}, "
                                  f"{time.time() - t:.0f}s), ledger {r['ledger']}")
    ok = all(s["ok"] for s in steps)
    print(f"\n{'demo passed' if ok else 'demo FAILED'} - artifacts in {out_dir}")
    print("next: athanor doctor · python examples/govern_quickstart.py · athanor bench --all")
    return 0 if ok else 1


def add_parsers(sub) -> None:
    p = sub.add_parser("doctor", help="check the install and run a quick self-test")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("demo", help="one-command end-to-end: run -> verify -> replay -> evals run")
    p.add_argument("--out", default="data/demo")
    p.add_argument("--skip-evals", action="store_true")
    p.add_argument("--full-evals", action="store_true", help="replay every eval case, not just the bug cases")
    p.set_defaults(fn=cmd_demo)
