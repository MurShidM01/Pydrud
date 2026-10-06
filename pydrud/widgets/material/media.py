"""
Embedded media: WebView, video and charts.
"""

from __future__ import annotations

from typing import Callable, Optional
from pydrud.widgets.base import Widget
from pydrud.widgets.theme import Colors
from pydrud.widgets.material._common import _clean

class WebView(Widget):
    """An embedded browser view.

    ``on_message`` receives ``postMessage`` calls from the page, so you can
    host a chart library or a rich editor and still drive it from Python.
    """

    _widget_type = "WebView"

    def __init__(
        self,
        url: Optional[str] = None,
        *,
        html: Optional[str] = None,
        javascript: bool = False,
        zoom: bool = False,
        allowed_origins: Optional[list[str]] = None,
        on_load: Optional[Callable] = None,
        on_message: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if not url and not html:
            raise ValueError("WebView needs either url= or html=")
        self.url = url
        self.html = html
        self.javascript = bool(javascript)
        self.zoom = zoom
        self.allowed_origins = [str(origin).strip() for origin in (allowed_origins or []) if str(origin).strip()]
        if on_load is not None:
            self.event_handlers["load"] = on_load
        if on_message is not None:
            self.event_handlers["message"] = on_message

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "url": self.url,
            "html": self.html,
            "javascript": self.javascript,
            "allowedOrigins": self.allowed_origins or None,
            "allowNativeBridge": bool(self.javascript and self.allowed_origins),
            "zoom": self.zoom or None,
        }))
        return props


class VideoPlayer(Widget):
    """A native video surface with the standard media controls."""

    _widget_type = "VideoPlayer"

    def __init__(self, source: str = "", *, autoplay: bool = False,
                 loop: bool = False, muted: bool = False, controls: bool = True,
                 aspect_ratio: float = 16 / 9, on_complete: Optional[Callable] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(key=key, **kwargs)
        self.source = str(source)
        self.autoplay = autoplay
        self.loop = loop
        self.muted = muted
        self.controls = controls
        self.aspect_ratio = float(aspect_ratio)
        if on_complete is not None:
            self.event_handlers["complete"] = on_complete

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "source": self.source,
            "autoplay": self.autoplay,
            "loop": self.loop,
            "muted": self.muted,
            "controls": self.controls,
            "aspectRatio": round(self.aspect_ratio, 4),
        })
        return props


class Chart(Widget):
    """A lightweight line/bar/pie chart drawn natively on a Canvas.

    ``series`` is a list of numbers, or a list of ``{"label", "value"}`` dicts.
    """

    _widget_type = "Chart"
    KINDS = ("line", "bar", "pie", "area")

    def __init__(
        self,
        series: Optional[list] = None,
        *,
        kind: str = "line",
        labels: Optional[list[str]] = None,
        colors: Optional[list[str]] = None,
        height: float = 180,
        show_grid: bool = True,
        show_values: bool = False,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if kind not in self.KINDS:
            raise ValueError(f"Chart kind must be one of {self.KINDS}")
        self.kind = kind
        self.height = float(height)
        self.show_grid = show_grid
        self.show_values = show_values
        self.colors = list(colors or [Colors.PRIMARY, Colors.TEAL, Colors.ACCENT,
                                      Colors.PINK, Colors.GREEN])
        raw = list(series or [])
        self.values: list[float] = []
        self.labels: list[str] = list(labels or [])
        for index, point in enumerate(raw):
            if isinstance(point, dict):
                self.values.append(float(point.get("value", 0)))
                if not labels:
                    self.labels.append(str(point.get("label", index)))
            elif isinstance(point, (list, tuple)) and len(point) == 2:
                self.values.append(float(point[1]))
                if not labels:
                    self.labels.append(str(point[0]))
            else:
                self.values.append(float(point))

    @property
    def max_value(self) -> float:
        return max(self.values) if self.values else 0.0

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "kind": self.kind,
            "values": self.values,
            "labels": self.labels,
            "colors": self.colors,
            "height": self.height,
            "showGrid": self.show_grid,
            "showValues": self.show_values,
            "max": self.max_value,
        })
        return props
