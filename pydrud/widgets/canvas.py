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

import math
from typing import Any, Callable, Optional, Sequence

from pydrud.widgets.base import Widget
from pydrud.widgets.theme import Colors

CAPS = ("butt", "round", "square")
JOINS = ("miter", "round", "bevel")
ALIGNS = ("left", "center", "right")


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
        #: Optional ``on_draw(canvas, size)`` hook, re-run on every rebuild.
        self.on_draw = on_draw
        if on_draw is not None and not callable(on_draw):
            raise TypeError("on_draw must be callable")

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
             weight: int = 400, rotate: float = 0.0) -> "Canvas":
        if align not in ALIGNS:
            raise ValueError(f"align must be one of {ALIGNS}")
        self.ops.append({"op": "text", "value": str(value), "x": float(x),
                         "y": float(y), "size": float(size), "color": color,
                         "align": align, "weight": int(weight),
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

    # ── serialisation ────────────────────────────────────────────────────

    def _serialise_props(self) -> dict:
        if self.on_draw is not None:
            self.ops.clear()
            self.on_draw(self)
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
