"""A small, real self-modifying program.

The agent's "self" is the Python source of a function ``f(x)``. Each step it
parses its own source with :mod:`ast`, applies one mutation, unparses it back
to source, compiles it and runs it. Edits can genuinely break the program:
``math.log``/``math.sqrt`` of negatives, division by zero, and overflow raise or
produce non-finite values on some inputs.
"""
from __future__ import annotations

import ast
import copy
import math
from collections import Counter
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

UNARY = ("sin", "cos", "tanh", "exp", "log", "sqrt")
BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
MAX_NODES = 40
SEED_SOURCE = "def f(x):\n    return x\n"

_ALLOWED = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Expr,
            ast.BinOp, ast.UnaryOp, ast.USub, ast.Call, ast.Attribute, ast.Name, ast.Load,
            ast.Constant) + BINOPS


class BrokenProgram(Exception):
    pass


def _body_expr(tree: ast.Module) -> ast.expr:
    return tree.body[0].body[0].value


def validate(tree: ast.Module) -> None:
    """Whitelist the grammar the mutator can emit (only x, constants, + - * /, math.<UNARY>)."""
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise BrokenProgram(f"disallowed node {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in ("x", "math"):
            raise BrokenProgram(f"disallowed name {node.id}")
        if isinstance(node, ast.Attribute) and node.attr not in UNARY:
            raise BrokenProgram(f"disallowed attribute {node.attr}")


def compile_source(src: str) -> Callable[[float], float]:
    tree = ast.parse(src)
    validate(tree)
    ns: dict = {"math": math}
    exec(compile(tree, "<self>", "exec"), ns)  # grammar is whitelisted above
    return ns["f"]


def evaluate(fn: Callable[[float], float], xs: Sequence[float]) -> Tuple[np.ndarray, int]:
    """Return outputs (NaN where the program raised or was non-finite) and the failure count."""
    out = np.empty(len(xs), dtype=np.float64)
    bad = 0
    for k, x in enumerate(xs):
        try:
            v = float(fn(float(x)))
            if not math.isfinite(v):
                raise OverflowError
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            v, bad = math.nan, bad + 1
        out[k] = v
    return out, bad


def node_count(src: str) -> int:
    return sum(1 for _ in ast.walk(_body_expr(ast.parse(src))))


def structure_tokens(src: str) -> Counter:
    toks: Counter = Counter()
    for n in ast.walk(_body_expr(ast.parse(src))):
        if isinstance(n, ast.Constant):
            toks["const"] += 1
        elif isinstance(n, ast.BinOp):
            toks[type(n.op).__name__] += 1
        elif isinstance(n, ast.Call):
            toks[n.func.attr] += 1
        elif isinstance(n, ast.Name) and n.id == "x":
            toks["x"] += 1
        elif isinstance(n, ast.UnaryOp):
            toks["neg"] += 1
    return toks


def structural_distance(a: str, b: str) -> float:
    """Normalised multiset distance between the two programs' AST token bags, in [0, 1]."""
    ta, tb = structure_tokens(a), structure_tokens(b)
    diff = sum(((ta - tb) + (tb - ta)).values())
    tot = sum(ta.values()) + sum(tb.values())
    return float(diff / tot) if tot else 0.0


# ---------------------------------------------------------------- mutation
def _const(v: float) -> ast.Constant:
    return ast.Constant(value=round(float(v), 4))


def _leaf(rng: np.random.Generator) -> ast.expr:
    return ast.Name(id="x", ctx=ast.Load()) if rng.random() < 0.5 else _const(rng.normal(0, 1.5))


def _call(name: str, arg: ast.expr) -> ast.Call:
    return ast.Call(func=ast.Attribute(value=ast.Name(id="math", ctx=ast.Load()), attr=name, ctx=ast.Load()),
                    args=[arg], keywords=[])


def _slots(expr_holder: ast.Return) -> List[Tuple[ast.AST, str, Optional[int]]]:
    """All (parent, field, index) slots that hold an expression in the return value."""
    slots = [(expr_holder, "value", None)]
    for node in ast.walk(expr_holder.value):
        if isinstance(node, ast.BinOp):
            slots += [(node, "left", None), (node, "right", None)]
        elif isinstance(node, ast.UnaryOp):
            slots.append((node, "operand", None))
        elif isinstance(node, ast.Call):
            slots.append((node, "args", 0))
    return slots


def _get(slot):
    p, f, i = slot
    return getattr(p, f)[i] if i is not None else getattr(p, f)


def _set(slot, v):
    p, f, i = slot
    if i is not None:
        getattr(p, f)[i] = v
    else:
        setattr(p, f, v)


MUTATIONS = ("tweak_const", "swap_op", "wrap_unary", "replace_leaf", "grow", "prune")


def mutate(src: str, rng: np.random.Generator, scale: float = 1.0) -> Tuple[str, str]:
    """Apply one random mutation to the program's own source. Returns (new_source, mutation_kind).

    ``scale`` < 1 restricts the edit to a gentler constant tweak of size ``scale``;
    the governor's REFINE path uses this.
    """
    tree = ast.parse(src)
    ret = tree.body[0].body[0]
    slots = _slots(ret)
    consts = [s for s in slots if isinstance(_get(s), ast.Constant)]
    if scale < 1.0:
        kind = "tweak_const" if consts else "grow"
    else:
        kind = MUTATIONS[int(rng.integers(len(MUTATIONS)))]

    if kind == "tweak_const" and consts:
        s = consts[int(rng.integers(len(consts)))]
        c = float(_get(s).value)
        _set(s, _const(c + rng.normal(0.0, 0.5 * scale * max(1.0, abs(c)))))
    elif kind == "swap_op":
        ops = [n for n in ast.walk(ret) if isinstance(n, ast.BinOp)]
        if not ops:
            return mutate(src, rng, scale) if consts else (src, "noop")
        n = ops[int(rng.integers(len(ops)))]
        n.op = BINOPS[int(rng.integers(len(BINOPS)))]()
    elif kind == "wrap_unary":
        s = slots[int(rng.integers(len(slots)))]
        _set(s, _call(UNARY[int(rng.integers(len(UNARY)))], _get(s)))
    elif kind == "replace_leaf":
        leaves = [s for s in slots if isinstance(_get(s), (ast.Constant, ast.Name))]
        s = leaves[int(rng.integers(len(leaves)))]
        _set(s, _leaf(rng))
    elif kind == "grow" or (kind == "tweak_const" and not consts):
        kind = "grow"
        s = slots[int(rng.integers(len(slots)))]
        op = BINOPS[int(rng.integers(len(BINOPS)))]()
        new_leaf = _const(rng.normal(0, 0.5 * scale)) if scale < 1.0 else _leaf(rng)
        _set(s, ast.BinOp(left=_get(s), op=op, right=new_leaf))
    elif kind == "prune":
        inner = [s for s in slots if isinstance(_get(s), (ast.BinOp, ast.UnaryOp, ast.Call))]
        if not inner:
            kind = "grow"
            _set(slots[0], ast.BinOp(left=_get(slots[0]), op=ast.Add(), right=_leaf(rng)))
        else:
            s = inner[int(rng.integers(len(inner)))]
            n = _get(s)
            kids = [n.left, n.right] if isinstance(n, ast.BinOp) else [n.operand] if isinstance(n, ast.UnaryOp) else list(n.args)
            _set(s, copy.deepcopy(kids[int(rng.integers(len(kids)))]))
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n", kind
