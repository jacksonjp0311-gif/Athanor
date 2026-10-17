"""Discovery, provenance sidecars and workspace preparation for Athanor eval cases."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..ledger import canonical_json

SIDECAR = "athanor.json"
SIDECAR_SCHEMA = "athanor.eval/1"
DEFAULT_CASES = os.path.join("evals", "cases")
METRICS_PREFIX = "ATHANOR_EVAL_METRICS "
KINDS = ("bug", "tuning")


@dataclass
class AthanorCase:
    path: str
    meta: Dict[str, Any]      # bug2eval metadata.json
    sidecar: Dict[str, Any]   # athanor.json

    @property
    def case_id(self) -> str:
        return self.meta["case_id"]

    @property
    def kind(self) -> str:
        return self.sidecar["kind"]

    @property
    def family(self) -> Optional[str]:
        return self.sidecar.get("family")


def case_sha(path: str) -> str:
    """Identity of a case: hash of its bug2eval metadata (which pins every artifact's SHA-256)."""
    with open(os.path.join(path, "metadata.json"), "rb") as f:
        meta = json.load(f)
    core = {k: meta[k] for k in ("case_id", "verification", "expected", "artifacts")}
    return hashlib.sha256(canonical_json(core).encode("utf-8")).hexdigest()


def load_cases(root: str = DEFAULT_CASES, ids: Optional[List[str]] = None,
               kinds: Optional[List[str]] = None) -> List[AthanorCase]:
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if not (os.path.isfile(os.path.join(p, "metadata.json")) and os.path.isfile(os.path.join(p, SIDECAR))):
            continue
        with open(os.path.join(p, "metadata.json"), encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(p, SIDECAR), encoding="utf-8") as f:
            side = json.load(f)
        if side.get("schema") != SIDECAR_SCHEMA:
            raise ValueError(f"{p}: unsupported sidecar schema {side.get('schema')!r}")
        c = AthanorCase(p, meta, side)
        if ids and c.case_id not in ids:
            continue
        if kinds and c.kind not in kinds:
            continue
        out.append(c)
    if ids:
        missing = set(ids) - {c.case_id for c in out}
        if missing:
            raise KeyError(f"unknown eval case(s): {', '.join(sorted(missing))}")
    return out


def pinned_case(case_path: str):
    """Load a bug2eval case, pinning a bare ``python`` verifier to this interpreter.

    Cases store ``python`` so they stay portable; pinning makes the suite run
    under the same interpreter (and installed Athanor) as the caller.
    """
    from bug2eval.models import EvalCase, load_case
    case = load_case(__import__("pathlib").Path(case_path))
    data = json.loads(json.dumps(case.data))
    argv = data["verification"]["argv"]
    if argv and argv[0] in ("python", "python3"):
        argv[0] = sys.executable
    return EvalCase(case.root, data)


def parse_metrics(stdout: str) -> Optional[Dict[str, Any]]:
    for line in (stdout or "").splitlines():
        if line.startswith(METRICS_PREFIX):
            try:
                return json.loads(line[len(METRICS_PREFIX):])
            except ValueError:
                return None
    return None


def inject_source(workspace: str, src_root: str) -> None:
    """Replace the workspace's ``src/athanor`` with the code under test (a working tree)."""
    target = os.path.join(workspace, "src", "athanor")
    if os.path.isdir(target):
        shutil.rmtree(target)
    shutil.copytree(os.path.join(src_root, "athanor") if os.path.isdir(os.path.join(src_root, "athanor")) else src_root,
                    target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"))


def inject_config(workspace: str, spec: Dict[str, Any]) -> None:
    with open(os.path.join(workspace, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"arm": spec["arm"], "cfg": spec["cfg"]}, f, indent=2, sort_keys=True)
        f.write("\n")
