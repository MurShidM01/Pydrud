"""
Explicit animation controllers — the imperative half of Pydrud's animation
story (``AnimatedContainer`` and friends are the declarative half).

A controller owns a value that travels from 0 to 1 over a duration, ticking
on the page's task runner and calling your listener on every frame::

    controller = page.animation(600, curve="ease_out")
    controller.on_tick(lambda t: (setattr(progress, "value", t), page.update()))
    controller.forward()

    controller.repeat(reverse=True)      # ping-pong forever
    controller.stop()

:class:`Tween` maps that 0-1 value onto whatever you are animating — a
number, a colour, an offset — so ``Tween(0, 240).at(controller.value)``
gives the current height.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Any, Callable, Optional, Sequence

#: Easing functions, matching the names used by the Android renderer.
CURVES: dict[str, Callable[[float], float]] = {
    "linear": lambda t: t,
    "ease_in": lambda t: t * t,
    "ease_out": lambda t: 1 - (1 - t) ** 2,
    "ease_in_out": lambda t: 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2,
    "accelerate": lambda t: t ** 3,
    "decelerate": lambda t: 1 - (1 - t) ** 3,
    "overshoot": lambda t: 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2,
    "anticipate": lambda t: t * t * (2.70158 * t - 1.70158),
    "bounce": lambda t: _bounce(t),
    "elastic": lambda t: (0.0 if t == 0 else 1.0 if t == 1 else
                          2 ** (-10 * t) * math.sin((t * 10 - 0.75)
                                                    * (2 * math.pi / 3)) + 1),
}


def _bounce(t: float) -> float:
    n, d = 7.5625, 2.75
    if t < 1 / d:
        return n * t * t
    if t < 2 / d:
        t -= 1.5 / d
        return n * t * t + 0.75
    if t < 2.5 / d:
        t -= 2.25 / d
        return n * t * t + 0.9375
    t -= 2.625 / d
    return n * t * t + 0.984375


def curve(name: str) -> Callable[[float], float]:
    """Look up an easing function by name."""
    if name not in CURVES:
        raise ValueError(f"Unknown curve {name!r}. Available: "
                         f"{', '.join(sorted(CURVES))}")
    return CURVES[name]


class AnimationController:
    """A ticking 0 → 1 value with listeners, driven off the UI thread.

    The controller never touches widgets itself: it calls your listeners,
    and *you* decide what to mutate and when to call ``page.update()``.
    """

    def __init__(self, duration: float = 0.3, *, curve: str = "ease_in_out",
                 fps: int = 60, runner: Any = None,
                 on_ui: Optional[Callable] = None,
                 lower: float = 0.0, upper: float = 1.0):
        if duration <= 0:
            raise ValueError("duration must be positive")
        if not 1 <= int(fps) <= 120:
            raise ValueError("fps must be between 1 and 120")
        self.duration = float(duration)
        self.curve_name = curve
        self._curve = globals()["curve"](curve)
        self.fps = int(fps)
        self.lower = float(lower)
        self.upper = float(upper)
        self._runner = runner
        self._on_ui = on_ui
        self._value = self.lower
        self._direction = 1
        self._repeat = False
        self._ping_pong = False
        self._running = False
        self._timer: Any = None
        self._started = 0.0
        self._listeners: list[Callable[[float], None]] = []
        self._completers: list[Callable[[], None]] = []
        self._lock = threading.RLock()

    # ── state ────────────────────────────────────────────────────────────

    @property
    def value(self) -> float:
        """The current eased value."""
        return self._value

    @property
    def progress(self) -> float:
        """Linear 0-1 progress, before easing."""
        span = (self.upper - self.lower) or 1.0
        return (self._value - self.lower) / span

    @property
    def running(self) -> bool:
        return self._running

    @property
    def completed(self) -> bool:
        return not self._running and self._value >= self.upper

    # ── listeners ────────────────────────────────────────────────────────

    def on_tick(self, callback: Callable[[float], None]) -> "AnimationController":
        if not callable(callback):
            raise TypeError("tick listener must be callable")
        self._listeners.append(callback)
        return self

    def on_complete(self, callback: Callable[[], None]) -> "AnimationController":
        if not callable(callback):
            raise TypeError("completion listener must be callable")
        self._completers.append(callback)
        return self

    # ── driving ──────────────────────────────────────────────────────────

    def forward(self, *, from_: Optional[float] = None) -> "AnimationController":
        """Animate towards 1."""
        if from_ is not None:
            self._value = float(from_)
        self._direction = 1
        return self._start()

    def reverse(self, *, from_: Optional[float] = None) -> "AnimationController":
        """Animate back towards 0."""
        if from_ is not None:
            self._value = float(from_)
        self._direction = -1
        return self._start()

    def toggle(self) -> "AnimationController":
        """Reverse when at (or heading to) the end, otherwise go forward."""
        return self.reverse() if self._direction > 0 and self._value > 0 \
            else self.forward()

    def repeat(self, *, reverse: bool = False) -> "AnimationController":
        """Loop forever; with *reverse* it ping-pongs."""
        self._repeat = True
        self._ping_pong = bool(reverse)
        self._direction = 1
        return self._start()

    def animate_to(self, target: float,
                   duration: Optional[float] = None) -> "AnimationController":
        """Animate towards an arbitrary value in the controller's range."""
        target = max(self.lower, min(self.upper, float(target)))
        if duration:
            self.duration = float(duration)
        self._direction = 1 if target >= self._value else -1
        self.upper = target if self._direction > 0 else self.upper
        return self._start()

    def stop(self) -> "AnimationController":
        """Freeze at the current value."""
        with self._lock:
            self._running = False
            self._repeat = False
            if self._timer is not None:
                try:
                    self._timer.cancel()
                except Exception:
                    pass
                self._timer = None
        return self

    def reset(self, value: Optional[float] = None) -> "AnimationController":
        self.stop()
        self._value = self.lower if value is None else float(value)
        self._emit()
        return self

    def dispose(self) -> None:
        self.stop()
        self._listeners.clear()
        self._completers.clear()

    # ── the tick loop ────────────────────────────────────────────────────

    def _start(self) -> "AnimationController":
        with self._lock:
            if self._running:
                return self
            self._running = True
            self._started = time.monotonic()
        interval = 1.0 / self.fps
        if self._runner is not None and hasattr(self._runner, "every"):
            self._timer = self._runner.every(interval, self._tick)
        else:                                    # no runner: own thread
            self._timer = _ThreadTicker(interval, self._tick)
            self._timer.start()
        return self

    def _tick(self) -> None:
        if not self._running:
            return
        step = (1.0 / self.fps) / self.duration
        span = self.upper - self.lower
        progress = self.progress + step * self._direction
        if progress >= 1.0:
            progress, finished = 1.0, True
        elif progress <= 0.0:
            progress, finished = 0.0, True
        else:
            finished = False

        self._value = self.lower + self._curve(progress) * span
        self._emit()

        if not finished:
            return
        if self._repeat:
            if self._ping_pong:
                self._direction *= -1
            else:
                self._value = self.lower
            return
        self.stop()
        for callback in list(self._completers):
            self._dispatch(callback)

    def _emit(self) -> None:
        for listener in list(self._listeners):
            self._dispatch(listener, self._value)

    def _dispatch(self, fn: Callable, *args) -> None:
        if self._on_ui is not None:
            self._on_ui(fn, *args)
        else:
            fn(*args)

    def __repr__(self) -> str:
        return (f"AnimationController(value={self._value:.3f}, "
                f"running={self._running}, curve={self.curve_name!r})")


class _ThreadTicker:
    """Fallback ticker used when no task runner is available (tests, CLI)."""

    def __init__(self, interval: float, fn: Callable):
        self.interval = interval
        self._fn = fn
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self._fn()

    def cancel(self) -> None:
        self._stop.set()


class Tween:
    """Maps a controller's 0-1 value onto a real value.

    Numbers, colours (``"#FF6366F1"``) and sequences all interpolate::

        height = Tween(80, 240).at(controller.value)
        tint = Tween(Colors.PRIMARY, Colors.ERROR).at(t)
        x, y = Tween((0, 0), (1, 0.5)).at(t)
    """

    def __init__(self, begin: Any, end: Any, *, curve: Optional[str] = None):
        self.begin = begin
        self.end = end
        self._curve = globals()["curve"](curve) if curve else None

    def at(self, t: float) -> Any:
        t = max(0.0, min(1.0, float(t)))
        if self._curve is not None:
            t = self._curve(t)
        return _lerp(self.begin, self.end, t)

    __call__ = at

    def chain(self, controller: AnimationController,
              setter: Callable[[Any], None]) -> AnimationController:
        """Push interpolated values into *setter* on every tick."""
        controller.on_tick(lambda value: setter(self.at(value)))
        return controller

    def __repr__(self) -> str:
        return f"Tween({self.begin!r} → {self.end!r})"


def _lerp(a: Any, b: Any, t: float) -> Any:
    if isinstance(a, str) and a.startswith("#"):
        return _lerp_color(a, b, t)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        value = a + (b - a) * t
        return type(a)(value) if isinstance(a, int) and isinstance(b, int) \
            else value
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        values = [_lerp(x, y, t) for x, y in zip(a, b)]
        return type(a)(values) if isinstance(a, list) else tuple(values)
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: _lerp(v, b.get(k, v), t) for k, v in a.items()}
    return b if t >= 0.5 else a


def _lerp_color(a: str, b: str, t: float) -> str:
    def parts(color: str) -> tuple[int, int, int, int]:
        value = color.lstrip("#")
        if len(value) == 6:
            value = "FF" + value
        return (int(value[0:2], 16), int(value[2:4], 16),
                int(value[4:6], 16), int(value[6:8], 16))

    ca, cb = parts(a), parts(b)
    mixed = [round(x + (y - x) * t) for x, y in zip(ca, cb)]
    return "#" + "".join(f"{c:02X}" for c in mixed)


class Sequence_:
    """Run controllers one after another (a storyboard)."""

    def __init__(self, *steps: AnimationController):
        self.steps = list(steps)

    def play(self) -> "Sequence_":
        chain = list(self.steps)

        def run(index: int) -> None:
            if index >= len(chain):
                return
            controller = chain[index]
            controller.on_complete(lambda: run(index + 1))
            controller.forward()

        run(0)
        return self

    def stop(self) -> None:
        for step in self.steps:
            step.stop()
