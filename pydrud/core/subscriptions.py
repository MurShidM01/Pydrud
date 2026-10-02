"""Explicit lifetime/disposal primitives for Pydrud subscriptions."""

from __future__ import annotations

import threading
from typing import Callable


class Subscription:
    """Idempotently cancellable subscription handle."""

    __slots__ = ("_cancel", "_lock", "_cancelled")

    def __init__(self, cancel: Callable[[], None]):
        self._cancel = cancel
        self._lock = threading.Lock()
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def cancel(self) -> None:
        with self._lock:
            if self._cancelled:
                return
            self._cancelled = True
        try:
            self._cancel()
        except Exception:
            pass

    dispose = cancel

    def __call__(self) -> None:
        """Backward-compatible alias for legacy ``unsubscribe = subscribe(...)`` patterns."""
        self.cancel()

    def __enter__(self) -> "Subscription":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cancel()
