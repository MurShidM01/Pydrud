"""
Background work, timers and rate limiting.

Pydrud dispatches every UI event on one thread. Anything slow (HTTP, disk,
sleeping) must therefore move off that thread or the UI freezes. This module
provides the three primitives that
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


class PydrudFuture:
    """Future facade that preserves failures while supporting legacy result semantics."""

    def __init__(self, future: Future, *, propagate_exceptions: bool = False):
        self._future = future
        self._propagate_exceptions = bool(propagate_exceptions)

    def result(self, timeout: float | None = None):
        try:
            return self._future.result(timeout=timeout)
        except BaseException:
            if self._propagate_exceptions:
                raise
            return None

    def exception(self, timeout: float | None = None):
        return self._future.exception(timeout=timeout)

    def done(self) -> bool:
        return self._future.done()

    def cancelled(self) -> bool:
        return self._future.cancelled()

    def cancel(self) -> bool:
        return self._future.cancel()

    def add_done_callback(self, fn):
        return self._future.add_done_callback(fn)

    def __getattr__(self, name):
        return getattr(self._future, name)


class TaskRunner:
    """Runs callables (and coroutines) off the UI thread."""

    def __init__(self, max_workers: int = 4, on_error: Optional[Callable] = None,
                 propagate_exceptions: bool = False):
        self._pool: Optional[ThreadPoolExecutor] = None
        self._max_workers = max(1, int(max_workers))
        self._on_error = on_error
        self._propagate_exceptions = bool(propagate_exceptions)
        self._lock = threading.Lock()
        self._timers: list["Timer"] = []
        self._closed = False

    # ── tasks ────────────────────────────────────────────────────────────

    def run(self, fn: Callable, *args, **kwargs) -> PydrudFuture:
        """Run *fn* on a worker thread and return a :class:`Future`.

        Coroutine functions are executed in a private event loop, so
        ``async def`` handlers work without the user managing asyncio.
        """
        pool = self._ensure_pool()
        future = pool.submit(self._invoke, fn, args, kwargs)
        return PydrudFuture(future, propagate_exceptions=self._propagate_exceptions)

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
        except BaseException as exc:  # noqa: BLE001 - report, then preserve Future failure
            self._report(exc)
            raise

    # ── timers ───────────────────────────────────────────────────────────

    def after(self, delay: float, fn: Callable, *args, **kwargs) -> "Timer":
        """Run *fn* once after *delay* seconds."""
        timer = Timer(delay, fn, args, kwargs, repeat=False, runner=self)
        self._track(timer)
        timer.start()
        return timer

    def every(self, interval: float, fn: Callable, *args,
              max_errors: Optional[int] = None, **kwargs) -> "Timer":
        """Run *fn* every *interval* seconds until cancelled.

        ``max_errors`` cancels the timer after that many consecutive
        failures instead of letting a permanently broken tick run forever.
        """
        timer = Timer(interval, fn, args, kwargs, repeat=True, runner=self,
                      max_errors=max_errors)
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
    """A cancellable one-shot or repeating timer.

    A repeating timer is an error boundary: a callback that raises is
    reported and the timer keeps ticking, because one dropped frame must
    not kill a game loop. Identical consecutive failures are collapsed in
    the log, ``max_errors`` cancels a timer that only ever fails, and
    :attr:`errors` / :attr:`consecutive_errors` / :attr:`last_error` say
    what happened::

        Timer(1 / 60, tick, repeat=True, max_errors=120).start()
    """

    #: Identical consecutive failures printed before the log is collapsed.
    ERROR_LOG_LIMIT = 3

    def __init__(self, interval: float, fn: Callable, args: tuple = (),
                 kwargs: Optional[dict] = None, *, repeat: bool = False,
                 runner: Optional[TaskRunner] = None,
                 max_errors: Optional[int] = None):
        self.interval = max(0.0, float(interval))
        self.repeat = bool(repeat)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs or {}
        self._runner = runner
        self._cancelled = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.ticks = 0
        #: Total callback failures since the timer started.
        self.errors = 0
        #: Failures since the last successful tick.
        self.consecutive_errors = 0
        #: The most recent exception raised by the callback.
        self.last_error: Optional[BaseException] = None
        #: Cancel the timer after this many consecutive failures.
        self.max_errors: Optional[int] = (None if max_errors is None
                                          else max(1, int(max_errors)))
        self._last_error_text = ""

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
            # Re-check immediately before invoking: ``cancel()`` may have
            # landed while we were waking up, and a cancelled timer must
            # never fire another tick.
            if self._cancelled.is_set():
                return
            try:
                self._fn(*self._args, **self._kwargs)
                self.ticks += 1
                self.consecutive_errors = 0
                self._last_error_text = ""
            except BaseException as exc:  # noqa: BLE001
                self._record_error(exc)
                if (self.max_errors is not None
                        and self.consecutive_errors >= self.max_errors):
                    print(f"[Pydrud] timer cancelled after "
                          f"{self.consecutive_errors} consecutive errors: "
                          f"{exc}")
                    self.cancel()
                    return
            if not self.repeat:
                return

    def _record_error(self, exc: BaseException) -> None:
        self.errors += 1
        self.consecutive_errors += 1
        self.last_error = exc
        if self._runner is not None:
            self._runner._report(exc)
            return
        text = f"{type(exc).__name__}: {exc}"
        repeated = text == self._last_error_text
        self._last_error_text = text
        if not repeated or self.consecutive_errors <= self.ERROR_LOG_LIMIT:
            print("[Pydrud] timer error:", exc)
        elif self.consecutive_errors == self.ERROR_LOG_LIMIT + 1:
            print(f"[Pydrud] timer error repeated — further identical "
                  f"errors suppressed ({text})")


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


GLOBAL_JOBS: dict[str, Callable] = {}


def job(name_or_fn: Any = None) -> Callable:
    """Decorator registering a background job by name or callable.

    Can be used as ``@job("sync_data")`` or ``@job``.

    Example::

        @job("refresh")
        def refresh_job(inputs):
            ...

        @job
        def daily_sync():
            ...
    """
    if callable(name_or_fn):
        fn = name_or_fn
        name = getattr(fn, "__name__", "job")
        GLOBAL_JOBS[name] = fn
        return fn

    name = str(name_or_fn) if name_or_fn is not None else None

    def decorator(fn: Callable) -> Callable:
        if not callable(fn):
            raise TypeError("background job must be callable")
        job_name = name or getattr(fn, "__name__", "job")
        GLOBAL_JOBS[job_name] = fn
        return fn

    return decorator
