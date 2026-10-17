"""A multi-function self-modifying TSP solver.

The agent's "self" is the whole module below: five cooperating functions (a
priority heuristic, a start-city chooser, a greedy constructor, a 2-opt improver
with a pass budget, and the solve() entry point). It mutates its own source with
AST edits anywhere in the module. Real failure modes:

* crashes: IndexError/TypeError/ZeroDivisionError from mutated indices/operators,
* runaway loops: the harness counts loop iterations (instrumented at compile time,
  which the agent cannot edit) and raises TimeoutError past a budget,
* silent wrong answers: e.g. a mutated slice in 2-opt changes the tour length,
  duplicating or dropping cities without any error,
* regressions: valid but longer tours, especially on larger held-out instances.
"""
from __future__ import annotations

import ast
import copy
import math
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

SEED_PROGRAM = '''\
def priority(d, k, n):
    return d


def pick_start(n):
    return 0


def construct(D):
    n = len(D)
    start = int(pick_start(n)) % n
    tour = [start]
    left = set(range(n))
    left.discard(start)
    while len(tour) < n:
        last = tour[-1]
        best = None
        best_s = None
        for j in sorted(left):
            s = priority(D[last][j], len(tour), n)
            if best_s is None or s < best_s:
                best_s = s
                best = j
        tour.append(best)
        left.discard(best)
    return tour


def budget(n):
    return 0


def improve(tour, D, passes):
    n = len(tour)
    for _ in range(passes):
        changed = False
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                a = tour[i - 1]
                b = tour[i]
                c = tour[j]
                e = tour[(j + 1) % n]
                delta = D[a][c] + D[b][e] - D[a][b] - D[c][e]
                if delta < -1e-09:
                    tour[i:j + 1] = tour[i:j + 1][::-1]
                    changed = True
        if not changed:
            break
    return tour


def solve(D):
    tour = construct(D)
    return improve(tour, D, int(budget(len(D))))
'''

HEURISTIC_FUNCS = ("priority", "pick_start", "budget")
SAFE_CALLS = {"int", "len", "set", "range", "sorted", "abs", "min", "max", "float"}
SAFE_METHODS = {"discard", "append"}
MATH_FUNCS = ("sqrt", "log", "exp", "tanh")
BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)
CMPOPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
MAX_NODES = 420
TICK_LIMIT = 60_000


class BrokenProgram(Exception):
    pass


# ------------------------------------------------------------- compile & run
class _Instrument(ast.NodeTransformer):
    """Insert a harness-owned __tick() at the top of every loop body (agent cannot remove it)."""

    def _tick(self, node):
        self.generic_visit(node)
        node.body.insert(0, ast.Expr(ast.Call(ast.Name("__tick", ast.Load()), [], [])))
        return node

    visit_For = _tick
    visit_While = _tick


def validate(tree: ast.Module) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Lambda,
                             ast.ClassDef, ast.With, ast.Try, ast.Delete, ast.AsyncFunctionDef)):
            raise BrokenProgram(f"disallowed node {type(node).__name__}")
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id not in SAFE_CALLS and f.id not in (
                    "priority", "pick_start", "construct", "budget", "improve", "solve"):
                raise BrokenProgram(f"disallowed call {f.id}")
            if isinstance(f, ast.Attribute):
                if not ((isinstance(f.value, ast.Name) and f.value.id == "math" and f.attr in MATH_FUNCS)
                        or f.attr in SAFE_METHODS):
                    raise BrokenProgram(f"disallowed attribute call {f.attr}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise BrokenProgram("dunder access")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise BrokenProgram("dunder name")


class Program:
    def __init__(self, src: str, tick_limit: int = TICK_LIMIT):
        tree = ast.parse(src)
        validate(tree)
        if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
            raise BrokenProgram("program too large")
        inst = _Instrument().visit(copy.deepcopy(tree))
        ast.fix_missing_locations(inst)
        self.src = src
        self.tick_limit = int(tick_limit)
        self._ticks = 0

        def tick():
            self._ticks += 1
            if self._ticks > self.tick_limit:
                raise TimeoutError("loop budget exceeded")

        self.ns: Dict[str, Any] = {"math": math, "__tick": tick, "__builtins__": {
            n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
            for n in SAFE_CALLS | {"None", "True", "False"} if n not in ("None", "True", "False")}}
        exec(compile(inst, "<self>", "exec"), self.ns)
        if "solve" not in self.ns:
            raise BrokenProgram("no solve()")

    def solve(self, D: List[List[float]]) -> List[int]:
        self._ticks = 0
        return self.ns["solve"](D)


def tour_length(tour: List[int], D: List[List[float]]) -> float:
    # math.fsum: exactly rounded, so results are identical across Python versions (3.12 changed sum())
    return float(math.fsum(D[tour[k]][tour[(k + 1) % len(tour)]] for k in range(len(tour))))


def check_tour(tour: Any, n: int) -> None:
    """Silent-wrong-answer detector: the output must be a permutation of range(n)."""
    if not isinstance(tour, list) or len(tour) != n or sorted(tour) != list(range(n)):
        raise ValueError("not a permutation of the cities")


Outcome = Tuple[str, Optional[float]]  # (status, length): ok | crash | timeout | invalid


def _lenient_ok(tour: Any, n: int) -> bool:
    return (isinstance(tour, list) and len(tour) >= 1
            and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c < n for c in tour))


def run_instance(prog: Program, D, strict: bool = True) -> Outcome:
    """Run the agent's solve() on one instance.

    strict=True (harness/held-out): the tour must be a permutation, else "invalid".
    strict=False (the agent's own scoring): any list of city indices is scored as a closed path, so a tour
    that silently drops or repeats cities *looks* fine (often shorter) - the silent-wrong-answer failure.
    """
    try:
        tour = prog.solve([row[:] for row in D])
    except TimeoutError:
        return "timeout", None
    except RecursionError:
        return "crash", None
    except Exception:  # noqa: BLE001 - any crash of the agent's own code is a measured outcome
        return "crash", None
    if not strict:
        return ("ok", tour_length(tour, D)) if _lenient_ok(tour, len(D)) else ("invalid", None)
    try:
        check_tour(tour, len(D))
    except Exception:  # noqa: BLE001
        return "invalid", None
    return "ok", tour_length(tour, D)


# ------------------------------------------------------------- structure
def structure_tokens(src: str) -> Counter:
    toks: Counter = Counter()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Constant):
            toks["const"] += 1
        elif isinstance(n, (ast.BinOp, ast.AugAssign)):
            toks[type(n.op).__name__] += 1
        elif isinstance(n, ast.Compare):
            for op in n.ops:
                toks[type(op).__name__] += 1
        elif isinstance(n, ast.Call):
            toks["call:" + (n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "?"))] += 1
        elif isinstance(n, ast.Name):
            toks["name:" + n.id] += 1
        elif isinstance(n, (ast.Subscript, ast.Slice)):
            toks[type(n).__name__] += 1
    return toks


def structural_distance(a: str, b: str) -> float:
    ta, tb = structure_tokens(a), structure_tokens(b)
    diff = sum(((ta - tb) + (tb - ta)).values())
    tot = sum(ta.values()) + sum(tb.values())
    return float(diff / tot) if tot else 0.0


# ------------------------------------------------------------- mutation
MUTATIONS = ("tweak_const", "swap_binop", "swap_compare", "swap_name", "grow", "wrap", "prune", "shift_index")


def _parents(tree):
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            if isinstance(value, ast.AST):
                yield parent, field, None, value
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    if isinstance(v, ast.AST):
                        yield parent, field, i, v


def _set(parent, field, idx, new):
    if idx is None:
        setattr(parent, field, new)
    else:
        getattr(parent, field)[idx] = new


def _func_of(tree):
    owner = {}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef):
            for n in ast.walk(fn):
                owner[id(n)] = fn
    return owner


def _is_expr_slot(parent, field, value) -> bool:
    """Expression positions whose value we may rewrite (loads only; not call targets or assign targets)."""
    if not isinstance(value, ast.expr) or isinstance(value, (ast.Slice, ast.Starred)):
        return False
    if isinstance(parent, ast.Call) and field == "func":
        return False
    if isinstance(parent, ast.Attribute):
        return False
    if isinstance(parent, (ast.Assign, ast.AugAssign, ast.For, ast.comprehension)) and field == "target":
        return False
    if isinstance(parent, ast.Assign) and field == "targets":
        return False
    if getattr(value, "ctx", None) is not None and not isinstance(value.ctx, ast.Load):
        return False
    return True


def mutate_program(src: str, rng: np.random.Generator, scale: float = 1.0) -> Tuple[str, str]:
    """One random AST edit anywhere in the program. scale < 1: a gentle numeric tweak only (REFINE path)."""
    tree = ast.parse(src)
    owner = _func_of(tree)
    slots = [(p, f, i, v) for p, f, i, v in _parents(tree) if _is_expr_slot(p, f, v)]
    consts = [s for s in slots if isinstance(s[3], ast.Constant) and isinstance(s[3].value, (int, float))
              and not isinstance(s[3].value, bool)]
    heur = [s for s in slots if owner.get(id(s[3])) is not None and owner[id(s[3])].name in HEURISTIC_FUNCS]
    kind = "tweak_const" if scale < 1.0 else MUTATIONS[int(rng.integers(len(MUTATIONS)))]

    def pick(xs):
        return xs[int(rng.integers(len(xs)))] if xs else None

    if kind == "tweak_const":
        s = pick(consts)
        if s is None:
            return src, "noop"
        v = s[3].value
        if isinstance(v, int):
            step = int(rng.choice([-1, 1])) * max(1, int(round(abs(rng.normal(0, 1.5 * scale)))))
            new = ast.Constant(v + step)
        else:
            new = ast.Constant(round(float(v + rng.normal(0, 0.5 * scale * max(1.0, abs(v)))), 4))
        _set(s[0], s[1], s[2], new)
    elif kind == "swap_binop":
        ops = [n for n in ast.walk(tree) if isinstance(n, ast.BinOp)]
        n = pick(ops)
        if n is None:
            return src, "noop"
        n.op = BINOPS[int(rng.integers(len(BINOPS)))]()
    elif kind == "swap_compare":
        cmps = [n for n in ast.walk(tree) if isinstance(n, ast.Compare)
                and all(isinstance(o, CMPOPS) for o in n.ops)]
        n = pick(cmps)
        if n is None:
            return src, "noop"
        k = int(rng.integers(len(n.ops)))
        n.ops[k] = CMPOPS[int(rng.integers(len(CMPOPS)))]()
    elif kind == "swap_name":
        names = [s for s in slots if isinstance(s[3], ast.Name) and s[3].id not in SAFE_CALLS | {"math", "None"}]
        s = pick(names)
        if s is None:
            return src, "noop"
        fn = owner.get(id(s[3]))
        pool = sorted({n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                       and n.id not in SAFE_CALLS | {"math", "None"} and n.id not in
                       ("priority", "pick_start", "construct", "budget", "improve", "solve")}) if fn else []
        if not pool:
            return src, "noop"
        _set(s[0], s[1], s[2], ast.Name(pool[int(rng.integers(len(pool)))], ast.Load()))
    elif kind in ("grow", "wrap"):
        s = pick(heur)
        if s is None:
            return src, "noop"
        fn = owner[id(s[3])]
        args = [a.arg for a in fn.args.args]
        if kind == "grow":
            leaf = ast.Name(pick(args), ast.Load()) if rng.random() < 0.5 else ast.Constant(round(float(rng.normal(0, 1.5)), 4))
            new = ast.BinOp(copy.deepcopy(s[3]), BINOPS[int(rng.integers(4))](), leaf)
        else:
            new = ast.Call(ast.Attribute(ast.Name("math", ast.Load()), MATH_FUNCS[int(rng.integers(len(MATH_FUNCS)))],
                                         ast.Load()), [copy.deepcopy(s[3])], [])
        _set(s[0], s[1], s[2], new)
    elif kind == "prune":
        bins = [s for s in slots if isinstance(s[3], ast.BinOp)]
        s = pick(bins)
        if s is None:
            return src, "noop"
        _set(s[0], s[1], s[2], copy.deepcopy(s[3].left if rng.random() < 0.5 else s[3].right))
    elif kind == "shift_index":
        subs = [n for n in ast.walk(tree) if isinstance(n, ast.Subscript)]
        n = pick(subs)
        if n is None:
            return src, "noop"
        d = int(rng.choice([-1, 1]))
        if isinstance(n.slice, ast.Slice):
            part = "upper" if (n.slice.upper is not None and rng.random() < 0.6) else "lower"
            cur = getattr(n.slice, part)
            setattr(n.slice, part, ast.BinOp(cur, ast.Add(), ast.Constant(d)) if cur is not None else ast.Constant(max(0, d)))
        else:
            n.slice = ast.BinOp(n.slice, ast.Add(), ast.Constant(d))
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n", kind
