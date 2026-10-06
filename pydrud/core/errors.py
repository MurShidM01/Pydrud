"""Structured exceptions raised by Pydrud.

Framework errors are subclasses of :class:`PydrudError` so an application can
catch everything Pydrud raises in one place while still distinguishing the
cases it cares about. They also carry an actionable message — the whole point
of a framework error is to tell the developer what to do next.
"""

from __future__ import annotations


class PydrudError(Exception):
    """Base class for every error Pydrud raises deliberately."""


class MaxDepthError(PydrudError, RecursionError):
    """A widget tree was nested deeper than :data:`MAX_TREE_DEPTH`.

    Subclasses :class:`RecursionError` so code that already caught the old
    ``RecursionError`` (raised by the recursive 2.0.2 algorithms) keeps
    working, but the message now says exactly what happened and how to fix
    it. The tree walkers are iterative, so this is a *deliberate* guard
    protecting the native view hierarchy rather than a stack limit.
    """


class FrameTooLargeError(PydrudError, ValueError):
    """A single widget subtree cannot fit in one transport frame.

    Raised when even the smallest chunked snapshot frame exceeds the bridge
    frame limit — i.e. one widget (usually a ``Canvas`` with an enormous
    ``ops`` list) is larger than the protocol allows.
    """


__all__ = ["PydrudError", "MaxDepthError", "FrameTooLargeError"]
