"""
Input and feedback: search, rating, progress, stepper.
"""

from __future__ import annotations

from typing import Callable, Optional, Union
from pydrud.widgets.base import Widget
from pydrud.widgets.theme import Colors
from pydrud.widgets.material._common import _clean

class SearchBar(Widget):
    """A rounded search field with leading search icon and clear button."""

    _widget_type = "SearchBar"

    def __init__(
        self,
        value: str = "",
        *,
        hint: str = "Search",
        suggestions: Optional[list[str]] = None,
        autofocus: bool = False,
        on_change: Optional[Callable] = None,
        on_submit: Optional[Callable] = None,
        on_clear: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.value = str(value)
        self.hint = hint
        self.suggestions = list(suggestions or [])
        self.autofocus = autofocus
        if on_change is not None:
            self.event_handlers["change"] = on_change
        if on_submit is not None:
            self.event_handlers["submit"] = on_submit
        if on_clear is not None:
            self.event_handlers["clear"] = on_clear

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "value": self.value,
            "hint": self.hint,
            "suggestions": self.suggestions or None,
            "autofocus": self.autofocus or None,
        }))
        return props


class Rating(Widget):
    """A star rating bar (read-only when ``on_change`` is omitted)."""

    _widget_type = "Rating"

    def __init__(
        self,
        value: float = 0,
        *,
        count: int = 5,
        size: float = 24,
        color: str = Colors.ACCENT,
        half: bool = True,
        on_change: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.count = int(count)
        self.value = max(0.0, min(float(value), float(self.count)))
        self.size = float(size)
        self.color = color
        self.half = half
        self.readonly = on_change is None
        if on_change is not None:
            self.event_handlers["change"] = on_change

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "value": self.value,
            "count": self.count,
            "size": self.size,
            "color": self.color,
            "half": self.half,
            "readonly": self.readonly,
        })
        return props


class CircularProgress(Widget):
    """An indeterminate spinner, or a determinate ring when ``value`` is set."""

    _widget_type = "CircularProgress"

    def __init__(
        self,
        value: Optional[float] = None,
        *,
        size: float = 36,
        stroke: float = 4,
        color: Optional[str] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.value = None if value is None else max(0.0, min(float(value), 1.0))
        self.size = float(size)
        self.stroke = float(stroke)
        self.color = color

    @property
    def indeterminate(self) -> bool:
        return self.value is None

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "value": self.value,
            "size": self.size,
            "stroke": self.stroke,
            "color": self.color,
            "indeterminate": self.indeterminate,
        }))
        return props


class Skeleton(Widget):
    """A shimmering placeholder shown while data loads."""

    _widget_type = "Skeleton"

    def __init__(self, *, width: Union[float, str] = "match", height: float = 16,
                 radius: float = 8, lines: int = 1, key: Optional[str] = None,
                 **kwargs):
        super().__init__(key=key, **kwargs)
        self.width = width
        self.height = float(height)
        self.radius = float(radius)
        self.lines = max(1, int(lines))

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({"width": self.width, "height": self.height,
                      "radius": self.radius, "lines": self.lines})
        return props


class RefreshIndicator(Widget):
    """Pull-to-refresh wrapper (``SwipeRefreshLayout``).

    The handler receives the event and should call ``page.end_refresh()``
    (or set ``refreshing=False`` and update) when the work is done.
    """

    _widget_type = "RefreshIndicator"

    def __init__(self, *, child: Optional[Widget] = None,
                 on_refresh: Optional[Callable] = None,
                 refreshing: bool = False, color: Optional[str] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(key=key, **kwargs)
        self.refreshing = bool(refreshing)
        self.color = color
        if child is not None:
            self.children = [child]
        if on_refresh is not None:
            self.event_handlers["refresh"] = on_refresh

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({"refreshing": self.refreshing, "color": self.color}))
        return props


class Stepper(Widget):
    """A horizontal or vertical step indicator for wizards and checkouts."""

    _widget_type = "Stepper"

    def __init__(
        self,
        steps: Optional[list[str]] = None,
        *,
        current: int = 0,
        orientation: str = "horizontal",
        content: Optional[Widget] = None,
        on_step: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if orientation not in ("horizontal", "vertical"):
            raise ValueError("Stepper orientation must be horizontal or vertical")
        self.steps = [str(s) for s in (steps or [])]
        self.current = max(0, min(int(current), max(0, len(self.steps) - 1)))
        self.orientation = orientation
        if content is not None:
            self.children = [content]
        if on_step is not None:
            self.event_handlers["change"] = on_step

    @property
    def is_last(self) -> bool:
        return self.current >= len(self.steps) - 1

    @property
    def progress(self) -> float:
        if len(self.steps) < 2:
            return 1.0
        return self.current / (len(self.steps) - 1)

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "steps": self.steps,
            "current": self.current,
            "orientation": self.orientation,
            "progress": round(self.progress, 4),
        })
        return props
