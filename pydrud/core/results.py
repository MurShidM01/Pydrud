"""
Request/response plumbing for native calls.

Most of the bridge is fire-and-forget: Python pushes render commands, Android
pushes events.  Native *services* (dialogs, pickers, permissions, storage,
location, …) need the opposite: Python asks a question and Android answers
later, possibly seconds later and possibly never (the user may background the
app while a date picker is open).

:class:`Result` is a tiny future tailored to that reality:

* ``then()`` registers a callback — this is the safe, idiomatic way to consume
  a result, because event callbacks run on the app's single event-loop thread;
* ``wait()`` blocks, and is only safe from a worker thread (``page.run_task``);
* results always complete exactly once, and a late answer for a result that was
  already cancelled is discarded.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Optional


class ResultError(RuntimeError):
    """Raised when a native call fails (or times out) and the value is read."""


class Result:
    """A one-shot, thread-safe holder for the answer to a native call."""

    __slots__ = ("_id", "_cmd", "_event", "_value", "_error", "_done",
                 "_callbacks", "_errbacks", "_lock", "_cancelled")

    def __init__(self, request_id: str, cmd: str = ""):
        self._id = request_id
        self._cmd = cmd
        self._event = threading.Event()
        self._value: Any = None
        self._error: Optional[str] = None
        self._done = False
        self._cancelled = False
        self._callbacks: list[Callable[[Any], Any]] = []
        self._errbacks: list[Callable[[str], Any]] = []
        self._lock = threading.Lock()

    # ── identity ─────────────────────────────────────────────────────────

    @property
    def request_id(self) -> str:
        return self._id

    @property
    def cmd(self) -> str:
        return self._cmd

    @property
    def done(self) -> bool:
        return self._done

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def error(self) -> Optional[str]:
        return self._error

    # ── completion (called by the bridge) ────────────────────────────────

    def complete(self, value: Any) -> bool:
        """Resolve successfully. Returns False if already settled."""
        with self._lock:
            if self._done:
                return False
            self._value = value
            self._done = True
            callbacks = list(self._callbacks)
        self._event.set()
        for cb in callbacks:
            _safe(cb, value)
        return True

    def fail(self, message: str) -> bool:
        """Resolve with an error. Returns False if already settled."""
        with self._lock:
            if self._done:
                return False
            self._error = str(message)
            self._done = True
            errbacks = list(self._errbacks)
        self._event.set()
        for cb in errbacks:
            _safe(cb, self._error)
        return True

    def cancel(self) -> bool:
        """Mark as cancelled; a later answer from Android will be ignored."""
        with self._lock:
            if self._done:
                return False
            self._cancelled = True
        return self.fail("cancelled")

    # ── consumption ──────────────────────────────────────────────────────

    def then(self, callback: Callable[[Any], Any]) -> "Result":
        """Run *callback(value)* when the call succeeds (immediately if done)."""
        fire = False
        with self._lock:
            if self._done and self._error is None:
                fire = True
            elif not self._done:
                self._callbacks.append(callback)
        if fire:
            _safe(callback, self._value)
        return self

    def catch(self, callback: Callable[[str], Any]) -> "Result":
        """Run *callback(message)* when the call fails."""
        fire = False
        with self._lock:
            if self._done and self._error is not None:
                fire = True
            elif not self._done:
                self._errbacks.append(callback)
        if fire:
            _safe(callback, self._error)
        return self

    def wait(self, timeout: Optional[float] = 30.0, default: Any = None) -> Any:
        """Block until the answer arrives.

        Never call this from an event handler — handlers run on the event-loop
        thread that also delivers the answer, so it would deadlock. Use it from
        ``page.run_task()`` workers, or use :meth:`then`.
        """
        if not self._event.wait(timeout):
            self.fail("timeout")
            return default
        if self._error is not None:
            return default
        return self._value

    def result(self, timeout: Optional[float] = 30.0) -> Any:
        """Like :meth:`wait` but raises :class:`ResultError` on failure."""
        if not self._event.wait(timeout):
            self.fail("timeout")
            raise ResultError(f"{self._cmd or 'call'} timed out")
        if self._error is not None:
            raise ResultError(f"{self._cmd or 'call'} failed: {self._error}")
        return self._value

    def __await__(self):
        """Await this native response from an ``async def`` handler.

        Bridge responses are delivered by Pydrud's UI thread while asyncio
        handlers may run on a worker-loop.  A plain ``threading.Event`` can't
        be awaited, so completion is forwarded safely to the caller's loop.
        The callback path remains available for existing applications.

        ::

            granted = await page.permissions.request("camera")
            accepted = await page.dialog.confirm("Delete this item?")
        """
        return self._await_result().__await__()

    async def _await_result(self) -> Any:
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def resolve(value: Any) -> None:
            def set_value() -> None:
                if not future.done():
                    future.set_result(value)
            loop.call_soon_threadsafe(set_value)

        def reject(message: str) -> None:
            def set_error() -> None:
                if not future.done():
                    future.set_exception(ResultError(
                        f"{self._cmd or 'call'} failed: {message}"))
            loop.call_soon_threadsafe(set_error)

        self.then(resolve).catch(reject)
        return await future

    def __repr__(self) -> str:
        state = "pending"
        if self._error:
            state = f"error={self._error!r}"
        elif self._done:
            state = f"value={self._value!r}"
        return f"<Result {self._cmd or '?'} {state}>"


def _safe(callback: Callable, arg: Any) -> None:
    try:
        callback(arg)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[Pydrud] result callback error: {exc}")
