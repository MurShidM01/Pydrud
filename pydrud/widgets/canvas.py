"""
Custom painting — the Pydrud equivalent of Flutter's ``CustomPaint``.

A :class:`Canvas` records drawing commands in Python and ships them to a
real Android ``View.onDraw`` implementation, so there is no bitmap transfer
and no WebView: signatures, sparklines, gauges and game boards are drawn by
the GPU-accelerated Skia canvas Android already uses.

::

    def gauge(value):
        canvas = Canvas(height=160, on_click=reset)
        canvas.circle(0.5, 0.5, 0.45, color=Colors.SURFACE_VARIANT)
        canvas.arc(0.5, 0.5, 0.45, start=135, sweep=270 * value,
                   color=Colors.PRIMARY, width=14, cap="round")
        canvas.text(f"{value:.0%}", 0.5, 0.55, size=28, align="center")
        return canvas

Coordinates are *fractions of the canvas* (0.0 - 1.0) by default, so a
drawing scales to any screen; pass ``units="px"`` for device-independent
pixels instead.
"""

from __future__ import annotations

import inspect
import math
from typing import Any, Callable, NamedTuple, Optional, Sequence

from pydrud.core.responsive import MediaQuery
from pydrud.widgets.base import Widget
from pydrud.widgets.theme import Colors

CAPS = ("butt", "round", "square")
JOINS = ("miter", "round", "bevel")
ALIGNS = ("left", "center", "right")

#: CSS/Flutter font-weight names accepted by :meth:`Canvas.text`.
WEIGHTS = {"thin": 100, "extralight": 200, "ultralight": 200, "light": 300,
           "normal": 400, "regular": 400, "medium": 500, "semibold": 600,
           "demibold": 600, "bold": 700, "extrabold": 800, "black": 900,
           "heavy": 900}


class Size(NamedTuple):
    """The canvas size in dp — also unpacks as ``(width, height)``."""

    width: float
    height: float


# Accept 700, "700" or "bold" and return the int weight the renderer wants.
def _font_weight(weight: Any) -> int:
    if isinstance(weight, bool):
        return 700 if weight else 400
    if isinstance(weight, (int, float)):
        return int(weight)
    text = str(weight).strip().lower().replace("-", "").replace("_", "")
    if text in WEIGHTS:
        return WEIGHTS[text]
    if text.isdigit():
        return int(text)
    raise ValueError(f"weight must be a number or one of "
                     f"{sorted(WEIGHTS)}, got {weight!r}")


# Best-effort dp size for a style width/height value ("match", 40, "50%").
def _resolve_dimension(value: Any, available: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if value is None or isinstance(value, bool):
        return float(available)
    text = str(value).strip().lower()
    if text.endswith("%"):
        text = text[:-1]
        try:
            return float(available) * float(text) / 100.0
        except ValueError:
            return float(available)
    try:
        return float(text)
    except ValueError:
        return float(available)


class Paint:
    """Reusable stroke/fill settings.

    ``Paint(color=Colors.PRIMARY, width=3, dash=[6, 4])`` can be handed to
    any drawing call instead of repeating keyword arguments.
    """

    __slots__ = ("color", "width", "fill", "cap", "join", "alpha", "dash",
                 "shadow", "gradient")

    def __init__(self, *, color: str = Colors.PRIMARY, width: float = 2.0,
                 fill: bool = False, cap: str = "butt", join: str = "miter",
                 alpha: float = 1.0, dash: Optional[Sequence[float]] = None,
                 shadow: float = 0.0,
                 gradient: Optional[Sequence[str]] = None):
        if cap not in CAPS:
            raise ValueError(f"cap must be one of {CAPS}")
        if join not in JOINS:
            raise ValueError(f"join must be one of {JOINS}")
        if not 0.0 <= float(alpha) <= 1.0:
            raise ValueError("alpha must be between 0 and 1")
        self.color = color
        self.width = float(width)
        self.fill = bool(fill)
        self.cap = cap
        self.join = join
        self.alpha = float(alpha)
        self.dash = list(dash) if dash else None
        self.shadow = float(shadow)
        self.gradient = list(gradient) if gradient else None

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"color": self.color, "width": self.width,
                               "fill": self.fill}
        if self.cap != "butt":
            out["cap"] = self.cap
        if self.join != "miter":
            out["join"] = self.join
        if self.alpha != 1.0:
            out["alpha"] = self.alpha
        if self.dash:
            out["dash"] = self.dash
        if self.shadow:
            out["shadow"] = self.shadow
        if self.gradient:
            out["gradient"] = self.gradient
        return out

    def copy(self, **overrides) -> "Paint":
        current = {k: getattr(self, k) for k in self.__slots__}
        current.update(overrides)
        return Paint(**current)

    def __repr__(self) -> str:
        return f"Paint({self.color}, width={self.width}, fill={self.fill})"


class Path:
    """A sequence of move/line/curve segments, drawn with ``canvas.path()``."""

    def __init__(self):
        self.ops: list[dict] = []

    def move_to(self, x: float, y: float) -> "Path":
        self.ops.append({"op": "move", "x": float(x), "y": float(y)})
        return self

    def line_to(self, x: float, y: float) -> "Path":
        self.ops.append({"op": "line", "x": float(x), "y": float(y)})
        return self

    def quad_to(self, cx: float, cy: float, x: float, y: float) -> "Path":
        self.ops.append({"op": "quad", "cx": float(cx), "cy": float(cy),
                         "x": float(x), "y": float(y)})
        return self

    def cubic_to(self, c1x: float, c1y: float, c2x: float, c2y: float,
                 x: float, y: float) -> "Path":
        self.ops.append({"op": "cubic", "c1x": float(c1x), "c1y": float(c1y),
                         "c2x": float(c2x), "c2y": float(c2y),
                         "x": float(x), "y": float(y)})
        return self

    def arc_to(self, x: float, y: float, radius: float, start: float,
               sweep: float) -> "Path":
        self.ops.append({"op": "arc", "x": float(x), "y": float(y),
                         "r": float(radius), "start": float(start),
                         "sweep": float(sweep)})
        return self

    def close(self) -> "Path":
        self.ops.append({"op": "close"})
        return self

    def polyline(self, points: Sequence[Sequence[float]]) -> "Path":
        """Convenience: move to the first point and line through the rest."""
        for index, (x, y) in enumerate(points):
            self.move_to(x, y) if index == 0 else self.line_to(x, y)
        return self

    def smooth(self, points: Sequence[Sequence[float]],
               tension: float = 0.4) -> "Path":
        """A Catmull-Rom-ish smoothed curve through *points*."""
        pts = [(float(x), float(y)) for x, y in points]
        if len(pts) < 2:
            return self.polyline(pts)
        self.move_to(*pts[0])
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            dx = (x1 - x0) * tension
            self.cubic_to(x0 + dx, y0, x1 - dx, y1, x1, y1)
        return self

    def to_list(self) -> list[dict]:
        return list(self.ops)

    def __len__(self) -> int:
        return len(self.ops)

    def __repr__(self) -> str:
        return f"Path({len(self.ops)} ops)"


class Canvas(Widget):
    """A view you draw on with Python calls.

    Every method returns ``self``, so drawing reads as a chain. Drawing
    commands are replayed on the device in the order they were issued.

    ``on_draw`` is re-run on every rebuild with as many arguments as it
    declares — ``(canvas)``, ``(canvas, size)`` or ``(canvas, w, h)``::

        Canvas(on_draw=lambda c, w, h: c.line(0, 0, w, h), units="px")

    ``size``/``w``/``h`` are dp (see :attr:`size`), so pixel-accurate
    drawing no longer means guessing the layout size.

    Painter contract
    ----------------
    ``on_draw`` runs once per build and its recorded commands are *frozen*
    for that build, so a painter may safely read shared mutable state (the
    game-loop pattern) — the diff compares the frozen frame against the next
    frame and emits an update when it changes::

        scene = {"x": 0.1}
        Canvas(on_draw=lambda c: c.circle(scene["x"], 0.5, 0.05))
        scene["x"] = 0.9        # next rebuild repaints at the new position

    A painter that raises is logged, keeps whatever it drew and leaves the
    exception on :attr:`last_draw_error`; it never takes down the rebuild.
    """

    _widget_type = "Canvas"

    def __init__(
        self,
        *,
        width: Any = "match",
        height: Any = 200,
        bg: Optional[str] = None,
        units: str = "fraction",
        antialias: bool = True,
        on_click: Optional[Callable] = None,
        on_draw: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        if units not in ("fraction", "px"):
            raise ValueError("units must be 'fraction' or 'px'")
        super().__init__(key=key, on_click=on_click, **kwargs)
        self.ops: list[dict] = []
        self.units = units
        self.antialias = bool(antialias)
        self.bg = bg
        self.style.setdefault("width", width)
        self.style.setdefault("height", height)
        if bg:
            self.style.setdefault("bg", bg)
        #: Optional ``on_draw`` hook, re-run on every rebuild. It may take
        #: ``(canvas)``, ``(canvas, size)`` or ``(canvas, width, height)``.
        self.on_draw = on_draw
        if on_draw is not None and not callable(on_draw):
            raise TypeError("on_draw must be callable")
        #: Size pinned by :meth:`measure` (dp), or ``None`` to estimate it.
        self._measured: Optional[Size] = None
        #: The exception raised by the last ``on_draw``, if any.
        self.last_draw_error: Optional[BaseException] = None

    # ── dimensions ───────────────────────────────────────────────────────

    @property
    def size(self) -> Size:
        """The canvas size in dp, as a ``(width, height)`` named tuple.

        Fixed sizes come from the style; ``"match"`` and percentages are
        resolved against the live :class:`MediaQuery` metrics (a 360x640
        phone when nothing is connected). :meth:`measure` pins exact
        values when the real laid-out size is known.
        """
        if self._measured is not None:
            return self._measured
        available_w, available_h = MediaQuery.viewport()
        width = _resolve_dimension(self.style.get("width"), available_w)
        height = _resolve_dimension(self.style.get("height"), available_h)
        return Size(max(width, 0.0), max(height, 0.0))

    @property
    def width(self) -> float:
        """Canvas width in dp (see :attr:`size`)."""
        return self.size.width

    @property
    def height(self) -> float:
        """Canvas height in dp (see :attr:`size`)."""
        return self.size.height

    def measure(self, width: Optional[float] = None,
                height: Optional[float] = None) -> "Canvas":
        """Pin the size (dp); pass nothing to go back to estimating."""
        if width is None and height is None:
            self._measured = None
        else:
            current = self.size
            self._measured = Size(
                float(current.width if width is None else width),
                float(current.height if height is None else height))
        return self

    # ── primitives ───────────────────────────────────────────────────────

    def _paint(self, paint: Optional[Paint], kwargs: dict) -> dict:
        if paint is not None:
            return paint.to_dict()
        return Paint(**kwargs).to_dict() if kwargs else Paint().to_dict()

    def line(self, x1: float, y1: float, x2: float, y2: float, *,
             paint: Optional[Paint] = None, **style) -> "Canvas":
        self.ops.append({"op": "line", "x1": float(x1), "y1": float(y1),
                         "x2": float(x2), "y2": float(y2),
                         "paint": self._paint(paint, style)})
        return self

    def rect(self, x: float, y: float, w: float, h: float, *,
             radius: float = 0.0, paint: Optional[Paint] = None,
             **style) -> "Canvas":
        self.ops.append({"op": "rect", "x": float(x), "y": float(y),
                         "w": float(w), "h": float(h),
                         "radius": float(radius),
                         "paint": self._paint(paint, style)})
        return self

    def circle(self, x: float, y: float, radius: float, *,
               paint: Optional[Paint] = None, **style) -> "Canvas":
        style.setdefault("fill", True)
        self.ops.append({"op": "circle", "x": float(x), "y": float(y),
                         "r": float(radius),
                         "paint": self._paint(paint, style)})
        return self

    def oval(self, x: float, y: float, w: float, h: Optional[float] = None, *,
             paint: Optional[Paint] = None, **style) -> "Canvas":
        """Draw an oval, or a circle when only one size is supplied.

        The four-argument form keeps the original top-left ``x, y, w, h``
        semantics. For convenience, ``oval(x, y, radius)`` is accepted as a
        circle with centre ``x, y``; this mirrors :meth:`circle` and prevents
        a missing optional height from taking down an entire widget render.
        """
        if h is None:
            return self.circle(x, y, w, paint=paint, **style)
        self.ops.append({"op": "oval", "x": float(x), "y": float(y),
                         "w": float(w), "h": float(h),
                         "paint": self._paint(paint, style)})
        return self

    def arc(self, x: float, y: float, radius: float, *, start: float = 0.0,
            sweep: float = 90.0, pie: bool = False,
            paint: Optional[Paint] = None, **style) -> "Canvas":
        self.ops.append({"op": "arc", "x": float(x), "y": float(y),
                         "r": float(radius), "start": float(start),
                         "sweep": float(sweep), "pie": bool(pie),
                         "paint": self._paint(paint, style)})
        return self

    def path(self, path: Path, *, paint: Optional[Paint] = None,
             **style) -> "Canvas":
        if not isinstance(path, Path):
            raise TypeError("path() expects a Path instance")
        self.ops.append({"op": "path", "ops": path.to_list(),
                         "paint": self._paint(paint, style)})
        return self

    def polygon(self, points: Sequence[Sequence[float]], *,
                paint: Optional[Paint] = None, **style) -> "Canvas":
        return self.path(Path().polyline(points).close(), paint=paint, **style)

    def text(self, value: str, x: float, y: float, *, size: float = 14,
             color: str = Colors.TEXT, align: str = "left",
             weight: Any = 400, rotate: float = 0.0) -> "Canvas":
        """Draw a string — ``weight`` takes ``400``/``700`` or ``"bold"``."""
        if align not in ALIGNS:
            raise ValueError(f"align must be one of {ALIGNS}")
        self.ops.append({"op": "text", "value": str(value), "x": float(x),
                         "y": float(y), "size": float(size), "color": color,
                         "align": align, "weight": _font_weight(weight),
                         "rotate": float(rotate)})
        return self

    def image(self, source: str, x: float, y: float, w: float, h: float, *,
              fit: str = "cover") -> "Canvas":
        self.ops.append({"op": "image", "src": str(source), "x": float(x),
                         "y": float(y), "w": float(w), "h": float(h),
                         "fit": fit})
        return self

    # ── transforms & state ───────────────────────────────────────────────

    def save(self) -> "Canvas":
        self.ops.append({"op": "save"})
        return self

    def restore(self) -> "Canvas":
        self.ops.append({"op": "restore"})
        return self

    def translate(self, dx: float, dy: float) -> "Canvas":
        self.ops.append({"op": "translate", "dx": float(dx), "dy": float(dy)})
        return self

    def rotate(self, degrees: float, *, x: float = 0.5,
               y: float = 0.5) -> "Canvas":
        self.ops.append({"op": "rotate", "deg": float(degrees),
                         "x": float(x), "y": float(y)})
        return self

    def scale(self, sx: float, sy: Optional[float] = None) -> "Canvas":
        self.ops.append({"op": "scale", "sx": float(sx),
                         "sy": float(sy if sy is not None else sx)})
        return self

    def clip_rect(self, x: float, y: float, w: float, h: float, *,
                  radius: float = 0.0) -> "Canvas":
        self.ops.append({"op": "clip", "x": float(x), "y": float(y),
                         "w": float(w), "h": float(h),
                         "radius": float(radius)})
        return self

    def clear(self) -> "Canvas":
        """Drop every recorded command (useful inside ``on_draw``)."""
        self.ops.clear()
        return self

    # ── higher-level helpers ─────────────────────────────────────────────

    def sparkline(self, values: Sequence[float], *, color: str = Colors.PRIMARY,
                  width: float = 2.0, fill: bool = False,
                  smooth: bool = True) -> "Canvas":
        """Draw a normalised line chart across the whole canvas."""
        data = [float(v) for v in values]
        if len(data) < 2:
            return self
        low, high = min(data), max(data)
        span = (high - low) or 1.0
        points = [(i / (len(data) - 1), 1.0 - (v - low) / span * 0.9 - 0.05)
                  for i, v in enumerate(data)]
        line = Path().smooth(points) if smooth else Path().polyline(points)
        self.path(line, color=color, width=width)
        if fill:
            area = (Path().smooth(points) if smooth else Path().polyline(points))
            area.line_to(1.0, 1.0).line_to(0.0, 1.0).close()
            self.path(area, color=color, fill=True, alpha=0.18, width=0)
        return self

    def grid(self, rows: int = 4, columns: int = 4, *,
             color: str = Colors.BORDER, width: float = 1.0) -> "Canvas":
        for r in range(1, max(1, rows)):
            y = r / rows
            self.line(0, y, 1, y, color=color, width=width)
        for c in range(1, max(1, columns)):
            x = c / columns
            self.line(x, 0, x, 1, color=color, width=width)
        return self

    def pie(self, values: Sequence[float], *,
            colors: Optional[Sequence[str]] = None,
            hole: float = 0.0) -> "Canvas":
        data = [max(0.0, float(v)) for v in values]
        total = sum(data) or 1.0
        palette = list(colors or Colors.CHART_PALETTE)
        angle = -90.0
        for index, value in enumerate(data):
            sweep = value / total * 360.0
            self.arc(0.5, 0.5, 0.45, start=angle, sweep=sweep, pie=True,
                     color=palette[index % len(palette)], fill=True)
            angle += sweep
        if hole > 0:
            self.circle(0.5, 0.5, 0.45 * float(hole),
                        color=self.bg or Colors.SURFACE, fill=True)
        return self

    # ── draw_* aliases ───────────────────────────────────────────────────
    draw_line = line
    draw_rect = rect
    draw_circle = circle
    draw_oval = oval
    draw_arc = arc
    draw_path = path
    draw_polygon = polygon
    draw_text = text
    draw_image = image
    draw_grid = grid
    draw_pie = pie
    draw_sparkline = sparkline

    # ── serialisation ────────────────────────────────────────────────────

    # Painters are written f(canvas), f(canvas, size) or f(canvas, w, h) —
    # match whichever one this is instead of raising TypeError at render time.
    def _draw_arguments(self) -> tuple:
        try:
            params = list(inspect.signature(self.on_draw).parameters.values())
        except (TypeError, ValueError):       # builtins / C callables
            return (self,)
        positional = [p for p in params
                      if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        if any(p.kind is p.VAR_POSITIONAL for p in params):
            accepted = 3
        else:
            accepted = min(len(positional), 3)
        required = sum(1 for p in positional if p.default is p.empty)
        count = max(accepted, min(required, 3))
        if count <= 1:
            return (self,)
        size = self.size
        if count == 2:
            return (self, size)
        return (self, size.width, size.height)

    def draw(self) -> "Canvas":
        """Re-run ``on_draw``, replacing the recorded commands.

        Called automatically before serialisation. A painter that raises
        is logged and keeps whatever it recorded — one bad frame cannot
        take down the rebuild cycle — and the exception stays on
        :attr:`last_draw_error`.
        """
        if self.on_draw is None:
            return self
        self.ops.clear()
        self.last_draw_error = None
        try:
            self.on_draw(*self._draw_arguments())
        except Exception as exc:              # pragma: no cover - defensive
            self.last_draw_error = exc
            print(f"[Pydrud] canvas on_draw error ({self.key}): "
                  f"{type(exc).__name__}: {exc}")
        return self

    def _serialise_props(self) -> dict:
        self.draw()
        props = dict(self._extra)
        props.update({"ops": list(self.ops), "units": self.units,
                      "antialias": self.antialias})
        return props

    def __repr__(self) -> str:
        return f"Canvas(key={self.key!r}, ops={len(self.ops)})"


def radial_point(cx: float, cy: float, radius: float,
                 degrees: float) -> tuple[float, float]:
    """Polar helper for building dials and radar charts."""
    rad = math.radians(degrees)
    return cx + radius * math.cos(rad), cy + radius * math.sin(rad)
