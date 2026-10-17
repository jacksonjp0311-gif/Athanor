"""Athanor ⇄ Bug2Eval integration (``athanor evals`` / ``athanor registry``).

Every bug fixed in Athanor and every tuning failure (a config that broke a safety
limit, overfit, or regressed on held-out seeds) is captured as a portable,
deterministic `Bug2Eval <https://github.com/jacksonjp0311-gif/bug2eval>`_ case
under ``evals/cases/``. The suite replays them and writes a hash-chained ledger;
the config registry only promotes a config that passes the suite *and* gets an
Athanor verdict against the incumbent. See ``docs/EVALS.md``.

Install with ``pip install "athanor[evals]"`` (pulls bug2eval from GitHub).
"""
from __future__ import annotations

BUG2EVAL_HINT = ('bug2eval is not installed. Install the extra: '
                 'pip install "athanor[evals] @ git+https://github.com/jacksonjp0311-gif/Athanor.git" '
                 'or pip install "bug2eval @ git+https://github.com/jacksonjp0311-gif/bug2eval.git@v0.1.3"')


class EvalsUnavailable(RuntimeError):
    pass


def require_bug2eval():
    try:
        import bug2eval  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise EvalsUnavailable(BUG2EVAL_HINT) from exc
    return bug2eval


def bug2eval_available() -> bool:
    try:
        require_bug2eval()
        return True
    except EvalsUnavailable:
        return False
