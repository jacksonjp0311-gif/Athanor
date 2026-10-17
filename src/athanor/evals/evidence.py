"""Attach and check AgentSearch citations for eval cases (optional; needs ``athanor[search]``)."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import __version__
from .cases import AthanorCase

Cite = Tuple[str, Optional[str]]  # (repo path, literal pattern or None for the whole file)


def parse_cite(text: str) -> Cite:
    """``path`` (whole file) or ``path:literal pattern``."""
    if ":" in text and not (len(text) > 1 and text[1] == ":" and text[0].isalpha() and "\\" in text[:3]):
        path, pattern = text.split(":", 1)
        return path, (pattern or None)
    return text, None


def default_cites(ac: AthanorCase, repo: str) -> List[Cite]:
    side = ac.sidecar
    out: List[Cite] = []
    if ac.kind == "bug":
        v = side.get("provenance", {}).get("verifier")
        if v and os.path.exists(os.path.join(repo, "evals", "verifiers", v)):
            out.append((f"evals/verifiers/{v}", None))
        # The fixed lines themselves are cited explicitly (path:pattern); whole current source files
        # change for unrelated reasons and would make every bug case look stale.
    else:
        from ..config_registry import Registry
        reg = Registry(os.path.join(repo, "configs", "registry"))
        for key in ("bad", "good"):
            ref = side.get("provenance", {}).get(key)
            if ref:
                out.append((os.path.relpath(reg.entry_path(ref), repo), None))
    return out


def attach(ac_or_dir, cites: Sequence[Cite], *, repo: str = ".", include_defaults: bool = True,
           refresh: bool = True) -> Dict[str, Any]:
    from ..search import EvidenceIndex, write_evidence
    from .cases import load_cases
    if isinstance(ac_or_dir, str):
        root, cid = os.path.split(os.path.normpath(ac_or_dir))
        ac = load_cases(root, ids=[cid])[0]
    else:
        ac = ac_or_dir
    wanted = (default_cites(ac, repo) if include_defaults else []) + list(cites)
    seen, uniq = set(), []
    for c in wanted:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    with EvidenceIndex(repo) as idx:
        if refresh:
            idx.refresh()
        out = [idx.cite(path, pattern=pat, lines=1, context=2 if pat else 0) for path, pat in uniq]
        version = idx.version
    path = write_evidence(ac.path, out, agentsearch_version=version, athanor_version=__version__)
    return {"case_id": ac.case_id, "evidence": path, "citations": len(out)}


def check_case(ac: AthanorCase, repo: str = ".", idx=None) -> Optional[Dict[str, Any]]:
    """Re-verify a case's citations. ``None`` when it has none."""
    from ..search import EvidenceIndex, read_evidence
    cites = read_evidence(ac.path)
    if not cites:
        return None
    if idx is not None:
        return idx.check(cites)
    with EvidenceIndex(repo) as own:
        return own.check(cites)
