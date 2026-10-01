"""
Background work, timers and rate limiting.

Pydrud dispatches every UI event on one thread, exactly like Android's main
looper.  Anything slow (HTTP, disk, sleeping) must therefore move off that
thread or the UI freezes.  This module provides the three primitives that
cover nearly all real app needs:

* :class:`TaskRunner` — a small daemon thread pool (``page.run_task``) that
  also knows how to run coroutines, and marshals results back to the UI
  thread via ``page.run_on_ui``;
* :class:`Timer` — one-shot and repeating timers that are cancelled cleanly
  when the app stops;
* :func:`debounce` / :func:`throttle` — decorators for search boxes, sliders
  and scroll handlers.
"""

from __future__ import annotations

import inspect
import threading
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Optional


class TaskRunner:
    """Runs callables (and coroutines) off the UI thread."""

    def __init__(self, max_workers: int = 4, on_error: Optional[Callable] = None):
        self._pool: Optional[ThreadPoolExecutor] = None
        self._max_workers = max(1, int(max_workers))
        self._on_error = on_error
        self._lock = threading.Lock()
        self._timers: list["Timer"] = []
        self._closed = False

    # ── tasks ────────────────────────────────────────────────────────────

    def run(self, fn: Callable, *args, **kwargs) -> Future:
        """Run *fn* on a worker thread and return a :class:`Future`.

        Coroutine functions are executed in a private event loop, so
        ``async def`` handlers work without the user managing asyncio.
        """
        pool = self._ensure_pool()
        return pool.submit(self._invoke, fn, args, kwargs)

    def _invoke(self, fn: Callable, args: tuple, kwargs: dict) -> Any:
        try:
            if inspect.iscoroutinefunction(fn):
                import asyncio

                return asyncio.run(fn(*args, **kwargs))
            value = fn(*args, **kwargs)
            if inspect.iscoroutine(value):
                import asyncio

                return asyncio.run(value)
            return value
        except BaseException as exc:  # noqa: BLE001 - reported, never swallowed
            self._report(exc)
            return None

    # ── timers ───────────────────────────────────────────────────────────

    def after(self, delay: float, fn: Callable, *args, **kwargs) -> "Timer":
        """Run *fn* once after *delay* seconds."""
        timer = Timer(delay, fn, args, kwargs, repeat=False, runner=self)
        self._track(timer)
        timer.start()
        return timer

    def every(self, interval: float, fn: Callable, *args, **kwargs) -> "Timer":
        """Run *fn* every *interval* seconds until cancelled."""
        timer = Timer(interval, fn, args, kwargs, repeat=True, runner=self)
        self._track(timer)
        timer.start()
        return timer

    def _track(self, timer: "Timer") -> None:
        with self._lock:
            self._timers = [t for t in self._timers if t.active]
            self._timers.append(timer)

    # ── shutdown ─────────────────────────────────────────────────────────

    def shutdown(self, wait: bool = False) -> None:
        with self._lock:
            self._closed = True
            timers, self._timers = self._timers, []
            pool, self._pool = self._pool, None
        for timer in timers:
            timer.cancel()
        if pool is not None:
            pool.shutdown(wait=wait)

    def _ensure_pool(self) -> ThreadPoolExecutor:
        with self._lock:
            if self._closed:
                raise RuntimeError("TaskRunner has been shut down")
            if self._pool is None:
                self._pool = ThreadPoolExecutor(
                    max_workers=self._max_workers,
                    thread_name_prefix="pydrud-task",
                )
            return self._pool

    def _report(self, exc: BaseException) -> None:
        if self._on_error is not None:
            try:
                self._on_error(exc)
                return
            except Exception:
                pass
        print("[Pydrud] task error:", exc)
        traceback.print_exc()


class Timer:
    """A cancellable one-shot or repeating timer."""

    def __init__(self, interval: float, fn: Callable, args: tuple = (),
                 kwargs: Optional[dict] = None, *, repeat: bool = False,
                 runner: Optional[TaskRunner] = None):
        self.interval = max(0.0, float(interval))
        self.repeat = bool(repeat)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs or {}
        self._runner = runner
        self._cancelled = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.ticks = 0

    @property
    def active(self) -> bool:
        return self._thread is not None and self._thread.is_alive() \
            and not self._cancelled.is_set()

    def start(self) -> "Timer":
        if self._thread is not None:
            return self
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="pydrud-timer")
        self._thread.start()
        return self

    def cancel(self) -> None:
        self._cancelled.set()

    def _loop(self) -> None:
        while not self._cancelled.is_set():
            if self._cancelled.wait(self.interval):
                return
            try:
                self._fn(*self._args, **self._kwargs)
                self.ticks += 1
            except BaseException as exc:  # noqa: BLE001
                if self._runner is not None:
                    self._runner._report(exc)
                else:
                    print("[Pydrud] timer error:", exc)
            if not self.repeat:
                return


def debounce(seconds: float):
    """Delay a call until *seconds* have passed without another call.

    Perfect for search-as-you-type:: ``@debounce(0.3)`` on an ``on_change``
    handler turns 20 keystrokes into one query.
    """

    def decorator(fn: Callable) -> Callable:
        state: dict[str, Any] = {"timer": None}
        lock = threading.Lock()

        def wrapper(*args, **kwargs):
            with lock:
                timer = state.get("timer")
                if timer is not None:
                    timer.cancel()
                new_timer = threading.Timer(seconds, fn, args, kwargs)
                new_timer.daemon = True
                state["timer"] = new_timer
                new_timer.start()

        wrapper.cancel = lambda: state["timer"] and state["timer"].cancel()  # type: ignore[attr-defined]
        wrapper.__name__ = getattr(fn, "__name__", "debounced")
        wrapper.__doc__ = fn.__doc__
        return wrapper

    return decorator


def throttle(seconds: float):
    """Allow at most one call per *seconds* (leading edge)."""

    def decorator(fn: Callable) -> Callable:
        state = {"last": 0.0}
        lock = threading.Lock()

        def wrapper(*args, **kwargs):
            now = time.monotonic()
            with lock:
                if now - state["last"] < seconds:
                    return None
                state["last"] = now
            return fn(*args, **kwargs)

        wrapper.__name__ = getattr(fn, "__name__", "throttled")
        wrapper.__doc__ = fn.__doc__
        return wrapper

    return decorator
