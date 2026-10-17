"""``athanor search ...``: AgentSearch over ledgers, decision records, configs, registry, evals, tuning logs."""
from __future__ import annotations

import json

from ..search import SCOPES, SearchUnavailable


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str, ensure_ascii=False))


def _idx(a):
    from ..search import EvidenceIndex
    return EvidenceIndex(a.repo, a.db)


def _run(fn):
    def wrapped(a) -> int:
        try:
            return fn(a)
        except (SearchUnavailable, ValueError, OSError) as exc:
            _print({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            return 2
    return wrapped


@_run
def _index(a) -> int:
    with _idx(a) as i:
        r = i.refresh()
    _print({k: v for k, v in r.items() if k != "errors"} | {"errors": len(r.get("errors", []))})
    return 0 if r.get("ok") else 1


@_run
def _status(a) -> int:
    with _idx(a) as i:
        r = i.status()
    _print(r)
    return 0 if r.get("ok") else 1


def _brief_hits(r, key):
    return r


@_run
def _find(a) -> int:
    with _idx(a) as i:
        i.ensure()
        r = i.find(a.query, scope=a.scope, limit=a.limit, ext=a.ext)
    if r.get("ok"):
        r["hits"] = [{"path": i.rel(h["path"]), "score": h.get("score"), "match": h.get("match")} for h in r["hits"]]
    _print(r if a.full else {k: r.get(k) for k in ("ok", "complete", "hits", "warnings", "error")})
    return 0 if r.get("ok") else 1


@_run
def _grep(a) -> int:
    with _idx(a) as i:
        i.ensure()
        r = i.grep(a.pattern, scope=a.scope, limit=a.limit, ext=a.ext, fresh=a.fresh)
    if r.get("ok") and not a.full:
        r = {"ok": True, "complete": r.get("complete"), "warnings": r.get("warnings"),
             "files": [{"path": i.rel(f["path"]), "sha256": f.get("content_sha256"),
                        "matches": [{"line": m["line"], "text": m["text"][:240]} for m in f.get("matches", [])]}
                       for f in r.get("files", [])]}
    _print(r)
    return 0 if r.get("ok") else 1


@_run
def _read(a) -> int:
    with _idx(a) as i:
        r = i.read(a.path, a.start, a.lines)
    _print(r)
    return 0 if r.get("ok") else 1


@_run
def _verify(a) -> int:
    with _idx(a) as i:
        r = i.call("verify_evidence", path=i.abspath(a.path), sha256=a.sha256)
    _print(r)
    return 0 if r.get("ok") and r.get("verified") else 1


@_run
def _cite(a) -> int:
    with _idx(a) as i:
        i.ensure()
        r = i.cite(a.path, pattern=a.pattern, start_line=a.start, lines=a.lines, context=a.context)
    _print(r)
    return 0


def add_parsers(sub) -> None:
    sp = sub.add_parser("search", help="AgentSearch evidence layer over runs, configs, registry, evals, tuning logs "
                                       "(pip install \"athanor[search]\", Python 3.11+)")
    ss = sp.add_subparsers(dest="search_cmd", required=True)

    def common(p):
        p.add_argument("--repo", default=".", help="repository root (default: .)")
        p.add_argument("--db", default=None, help="index path (default: REPO/.athanor/search/index.sqlite3)")

    scopes = ", ".join(f"{k}={v}" for k, v in SCOPES.items())
    p = ss.add_parser("index", help="(re)scan the repo into the local index")
    common(p); p.set_defaults(fn=_index)
    p = ss.add_parser("status", help="index_status: roots, coverage, freshness")
    common(p); p.set_defaults(fn=_status)
    p = ss.add_parser("find", help="file_search: files by name/path (typo-tolerant)")
    p.add_argument("query"); p.add_argument("--scope", help=f"one of: {scopes}, or a repo-relative dir")
    p.add_argument("--ext"); p.add_argument("--limit", type=int, default=20); p.add_argument("--full", action="store_true")
    common(p); p.set_defaults(fn=_find)
    p = ss.add_parser("grep", help="content_search: literal text, with line numbers and file SHA-256")
    p.add_argument("pattern"); p.add_argument("--scope", help=f"one of: {scopes}, or a repo-relative dir")
    p.add_argument("--ext"); p.add_argument("--limit", type=int, default=20)
    p.add_argument("--fresh", action="store_true", help="refresh the index first")
    p.add_argument("--full", action="store_true", help="raw AgentSearch result")
    common(p); p.set_defaults(fn=_grep)
    p = ss.add_parser("read", help="read_file: a bounded excerpt with the file's SHA-256")
    p.add_argument("path"); p.add_argument("--start", type=int, default=1); p.add_argument("--lines", type=int, default=40)
    common(p); p.set_defaults(fn=_read)
    p = ss.add_parser("verify", help="verify_evidence: rehash a file and compare with a SHA-256")
    p.add_argument("path"); p.add_argument("sha256")
    common(p); p.set_defaults(fn=_verify)
    p = ss.add_parser("cite", help="make a citation (path, lines, file + line SHA-256) for evidence")
    p.add_argument("path"); p.add_argument("--pattern"); p.add_argument("--start", type=int)
    p.add_argument("--lines", type=int, default=1); p.add_argument("--context", type=int, default=0)
    common(p); p.set_defaults(fn=_cite)
