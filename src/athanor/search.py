"""Evidence layer on AgentSearch (``athanor search``, optional extra ``athanor[search]``, Python 3.11+).

`AgentSearch <https://github.com/jacksonjp0311-gif/AgentSearch>`_ is a local, read-only
SQLite-FTS5 index with five tools: ``file_search``, ``content_search``, ``read_file``,
``verify_evidence`` and ``index_status``. Athanor uses it for three things:

1. **Citations.** When a case is captured, the source lines and run records it rests
   on are cited with ``read_file`` and stored with their SHA-256 (whole file and the
   cited lines) in ``evidence.json``.
2. **Search** over run ledgers, decision records, configs, the registry, eval cases
   and the tuning logs (``athanor search ...``).
3. **Stale-evidence checks.** Before promotion relies on a past result, each citation
   is re-verified with ``verify_evidence``. Anything that changed is flagged:

   ``fresh``               file bytes identical
   ``changed-lines-intact`` file changed, but the cited lines are byte-identical
   ``moved``               the cited lines are intact at a different line range
   ``stale``               the cited lines changed or are gone
   ``missing``             the file is gone or unreadable

Every status other than ``fresh`` is reported as stale. ``stale`` and ``missing``
are *hard*: ``--require-fresh-evidence`` blocks a promotion on them.

The index is derived state in ``.athanor/search/index.sqlite3`` (git-ignored). Core
Athanor never imports this module unless asked.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional

SEARCH_HINT = ('AgentSearch is not installed (needs Python 3.11+). Install the extra: '
               'pip install "athanor[search] @ git+https://github.com/jacksonjp0311-gif/Athanor.git@v2.8.0"')
EXCLUDES = (".git", ".venv", "venv", "__pycache__", ".athanor", ".pytest_cache", "node_modules",
            "dist", "build", ".mypy_cache", ".ruff_cache")
SCOPES = {
    "runs": "data", "configs": "configs", "registry": os.path.join("configs", "registry"),
    "tuning": os.path.join("docs", "tuning"), "evals": "evals", "docs": "docs", "src": "src",
}
HARD = ("stale", "missing")
EVIDENCE_FILE = "evidence.json"
EVIDENCE_SCHEMA = "athanor.evidence/1"


class SearchUnavailable(RuntimeError):
    pass


def search_available() -> bool:
    if sys.version_info < (3, 11):
        return False
    try:
        import agentsearch  # noqa: F401
        return True
    except ImportError:
        return False


def require_agentsearch():
    if not search_available():
        raise SearchUnavailable(SEARCH_HINT)
    import agentsearch
    return agentsearch


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EvidenceIndex:
    """A repo-scoped AgentSearch index. All file access goes through the five tools."""

    def __init__(self, repo: str = ".", db: Optional[str] = None):
        agentsearch = require_agentsearch()
        from agentsearch.adapter import AgentSearchAdapter
        self.repo = os.path.realpath(repo)
        self.db = os.path.abspath(db or os.path.join(self.repo, ".athanor", "search", "index.sqlite3"))
        cfg = agentsearch.SearchConfig((self.repo,), exclude_dirs=EXCLUDES)
        self.engine = agentsearch.SearchEngine(self.db, cfg)
        self.tools = AgentSearchAdapter(self.engine)
        self.version = agentsearch.__version__

    # ------------------------------------------------------------ lifecycle
    def __enter__(self) -> "EvidenceIndex":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.engine.close()

    def refresh(self) -> Dict[str, Any]:
        """Explicit operator action (not a model tool): rescan the repo into the derived index."""
        return self.engine.index()

    def ensure(self) -> None:
        st = self.tools.dispatch("index_status", {})
        if not st.get("ok") or not st.get("files"):
            self.refresh()

    # ------------------------------------------------------------- the 5 tools
    def call(self, tool: str, **args: Any) -> Dict[str, Any]:
        return self.tools.dispatch(tool, args)

    def abspath(self, rel: str) -> str:
        p = rel if os.path.isabs(rel) else os.path.join(self.repo, rel)
        return os.path.realpath(p)

    def rel(self, path: str) -> str:
        return os.path.relpath(self.abspath(path), self.repo).replace(os.sep, "/")

    def scope(self, name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        sub = SCOPES.get(name, name)
        path = self.abspath(sub)
        if not os.path.isdir(path):
            raise ValueError(f"scope {name!r} -> {sub} is not a directory in {self.repo}")
        return path

    def find(self, query: str, scope: Optional[str] = None, limit: int = 20, ext: Optional[str] = None):
        args: Dict[str, Any] = {"query": query, "limit": limit}
        if scope:
            args["scope"] = self.scope(scope)
        if ext:
            args["ext"] = ext
        return self.call("file_search", **args)

    def grep(self, pattern: str, scope: Optional[str] = None, limit: int = 20, ext: Optional[str] = None,
             per_file: int = 3, fresh: bool = False):
        args: Dict[str, Any] = {"pattern": pattern, "limit": limit, "per_file": per_file, "fresh": fresh}
        if scope:
            args["scope"] = self.scope(scope)
        if ext:
            args["ext"] = ext
        return self.call("content_search", **args)

    def read(self, path: str, start_line: int = 1, max_lines: int = 40):
        return self.call("read_file", path=self.abspath(path), start_line=int(start_line), max_lines=int(max_lines))

    def status(self):
        return self.call("index_status")

    # ------------------------------------------------------------- citations
    def _locate(self, path: str, pattern: str) -> Optional[int]:
        target = self.abspath(path)
        res = self.grep(pattern, scope=None, limit=200, per_file=1, fresh=False)
        for f in res.get("files", []) if res.get("ok") else []:
            if os.path.realpath(f["path"]) == target and f.get("matches"):
                return int(f["matches"][0]["line"])
        # the index may predate the file; fall back to reading it through read_file
        r = self.read(path, 1, 500)
        start = 1
        while r.get("ok"):
            for i, line in enumerate(r["text"].split("\n")):
                if pattern.casefold() in line.casefold():
                    return start + i
            if not r.get("truncated") or r["end_line"] >= r["total_lines"]:
                break
            start = r["end_line"] + 1
            r = self.read(path, start, 500)
        return None

    def cite(self, path: str, *, pattern: Optional[str] = None, start_line: Optional[int] = None,
             lines: int = 1, context: int = 0, note: Optional[str] = None) -> Dict[str, Any]:
        """Cite lines of a repo file. ``pattern`` (literal) locates them; else ``start_line``; else the whole file."""
        whole = pattern is None and start_line is None
        if pattern is not None:
            line = self._locate(path, pattern)
            if line is None:
                raise ValueError(f"cannot cite {path}: pattern {pattern!r} not found")
            start_line = max(1, line - context)
            lines = lines + 2 * context
        if whole:
            r = self.read(path, 1, 1)
            if not r.get("ok"):
                raise ValueError(f"cannot cite {path}: {r.get('error')}")
            return {"path": self.rel(path), "sha256": r["content_sha256"], "whole_file": True,
                    "total_lines": r["total_lines"], "note": note}
        r = self.read(path, start_line, lines)
        if not r.get("ok"):
            raise ValueError(f"cannot cite {path}: {r.get('error')}")
        text = r["text"]
        return {"path": self.rel(path), "sha256": r["content_sha256"], "start_line": r["start_line"],
                "end_line": r["end_line"], "lines_sha256": _sha(text), "excerpt": text[:2000],
                "pattern": pattern, "note": note}

    def verify(self, cite: Dict[str, Any]) -> Dict[str, Any]:
        path = self.abspath(cite["path"])
        out = {"path": cite["path"], "recorded_sha256": cite["sha256"]}
        if not os.path.isfile(path):
            return {**out, "status": "missing", "detail": "file not found"}
        v = self.call("verify_evidence", path=path, sha256=cite["sha256"])
        if not v.get("ok"):
            return {**out, "status": "missing", "detail": str(v.get("error"))}
        out["current_sha256"] = v["evidence"]["sha256"]
        if v.get("verified"):
            return {**out, "status": "fresh"}
        if cite.get("whole_file"):
            return {**out, "status": "stale", "detail": "file content changed"}
        n = int(cite["end_line"]) - int(cite["start_line"]) + 1
        r = self.read(path, cite["start_line"], n)
        if r.get("ok") and _sha(r["text"]) == cite["lines_sha256"]:
            return {**out, "status": "changed-lines-intact", "detail": "file changed; cited lines identical"}
        if cite.get("pattern"):
            line = self._locate(path, cite["pattern"])
            if line is not None:
                ctx = None
                # recover the original offset of the pattern line inside the excerpt
                for i, l in enumerate(cite.get("excerpt", "").split("\n")):
                    if cite["pattern"].casefold() in l.casefold():
                        ctx = i
                        break
                start = max(1, line - (ctx or 0))
                r2 = self.read(path, start, n)
                if r2.get("ok") and _sha(r2["text"]) == cite["lines_sha256"]:
                    return {**out, "status": "moved", "detail": f"cited lines now at {start}-{start + n - 1}"}
        return {**out, "status": "stale", "detail": "cited lines changed or removed"}

    def check(self, cites: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = [self.verify(c) for c in cites]
        stale = [r for r in results if r["status"] != "fresh"]
        return {"checked": len(results), "fresh": len(results) - len(stale),
                "stale": stale, "hard": [r for r in stale if r["status"] in HARD], "results": results}


# ------------------------------------------------------------------ helpers
def write_evidence(case_dir: str, cites: List[Dict[str, Any]], *, agentsearch_version: str,
                   athanor_version: str) -> str:
    path = os.path.join(case_dir, EVIDENCE_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"schema": EVIDENCE_SCHEMA, "agentsearch_version": agentsearch_version,
                   "athanor_version": athanor_version, "citations": cites}, f, indent=2, sort_keys=True,
                  ensure_ascii=False)
        f.write("\n")
    return path


def read_evidence(case_dir: str) -> List[Dict[str, Any]]:
    path = os.path.join(case_dir, EVIDENCE_FILE)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema") != EVIDENCE_SCHEMA:
        raise ValueError(f"{path}: unsupported evidence schema {data.get('schema')!r}")
    return list(data.get("citations", []))


def file_citation(path: str, repo: str = ".", note: Optional[str] = None) -> Dict[str, Any]:
    """Whole-file citation with plain hashlib, usable without AgentSearch (verified later with it)."""
    full = path if os.path.isabs(path) else os.path.join(repo, path)
    with open(full, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    return {"path": os.path.relpath(os.path.realpath(full), os.path.realpath(repo)).replace(os.sep, "/"),
            "sha256": digest, "whole_file": True, "note": note}
