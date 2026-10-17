"""ATHANOR: a deterministic coherence governor for recursive, self-modifying systems.

Public API (3.0.0)::

    from athanor import Governor, govern
"""
__version__ = "3.0.0"

from .governor import Decision, Governor, GovernorError, GovernResult, govern  # noqa: E402

__all__ = ["__version__", "Governor", "Decision", "GovernResult", "GovernorError", "govern"]
