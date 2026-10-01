"""
Gesture and interaction widgets.

Android exposes gestures through ``GestureDetector``/``onTouchEvent``; this
module gives that a declarative face.  Every gesture widget is *transparent*:
it wraps one child, adds no visual box of its own (except :class:`InkWell`,
which draws the Material ripple), and forwards touch data to Python only for
the gestures you actually subscribed to — unsubscribed gestures are never
sent over the bridge, which keeps the socket quiet during a scroll.
"""

from __future__ import annotations

from typing import Callable, Optional

from pydrud.widgets.base import Widget

#: Gestures the Android ``EventDispatcher`` knows how to detect.
GESTURES = (
    "tap",
    "double_tap",
    "long_press",
    "swipe_left",
    "swipe_right",
    "swipe_up",
    "swipe_down",
    "pan_start",
    "pan_update",
    "pan_end",
    "scale",
)


class GestureDetector(Widget):
    """Detect taps, double taps, swipes, drags and pinch on any child.

    ::

        GestureDetector(
            child=photo,
            on_double_tap=lambda e: zoom_in(),
            on_swipe_left=lambda e: next_photo(),
            on_scale=lambda e: set_zoom(e["data"]["scale"]),
        )

    Swipe handlers receive ``data`` with ``dx``, ``dy`` and ``velocity``;
    pan handlers receive ``x``/``y``/``dx``/``dy``; scale receives ``scale``.
    """

    _widget_type = "GestureDetector"

    def __init__(
        self,
        *,
        child: Optional[Widget] = None,
        on_tap: Optional[Callable] = None,
        on_double_tap: Optional[Callable] = None,
        on_long_press: Optional[Callable] = None,
        on_swipe_left: Optional[Callable] = None,
        on_swipe_right: Optional[Callable] = None,
        on_swipe_up: Optional[Callable] = None,
        on_swipe_down: Optional[Callable] = None,
        on_pan_start: Optional[Callable] = None,
        on_pan_update: Optional[Callable] = None,
        on_pan_end: Optional[Callable] = None,
        on_scale: Optional[Callable] = None,
        swipe_threshold: float = 48,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if child is not None:
            self.children = [child]
        self.swipe_threshold = float(swipe_threshold)

        for name, handler in (
            ("tap", on_tap),
            ("double_tap", on_double_tap),
            ("long_press", on_long_press),
            ("swipe_left", on_swipe_left),
            ("swipe_right", on_swipe_right),
            ("swipe_up", on_swipe_up),
            ("swipe_down", on_swipe_down),
            ("pan_start", on_pan_start),
            ("pan_update", on_pan_update),
            ("pan_end", on_pan_end),
            ("scale", on_scale),
        ):
            if handler is not None:
                self.event_handlers[name] = handler

    @property
    def gestures(self) -> list[str]:
        """The gestures Android should actually listen for."""
        return sorted(g for g in self.event_handlers if g in GESTURES)

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "gestures": self.gestures,
            "swipeThreshold": self.swipe_threshold,
        })
        return props


class InkWell(Widget):
    """A tappable area that draws the Material ripple on touch."""

    _widget_type = "InkWell"

    def __init__(
        self,
        *,
        child: Optional[Widget] = None,
        on_click: Optional[Callable] = None,
        on_long_press: Optional[Callable] = None,
        radius: float = 0,
        color: Optional[str] = None,
        borderless: bool = False,
        enabled: bool = True,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_click=on_click,
                         on_long_press=on_long_press, **kwargs)
        if child is not None:
            self.children = [child]
        self.radius = float(radius)
        self.color = color
        self.borderless = borderless
        self.enabled = enabled

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "radius": self.radius,
            "rippleColor": self.color,
            "borderless": self.borderless,
            "enabled": self.enabled,
        })
        return {k: v for k, v in props.items() if v is not None}


class Dismissible(Widget):
    """Swipe-to-dismiss a list row, with an optional coloured background.

    ``direction`` is ``"start"``, ``"end"`` or ``"both"``. The ``dismiss``
    event carries ``{"direction": "start"|"end"}`` so a mail-style UI can
    archive on one side and delete on the other.
    """

    _widget_type = "Dismissible"

    DIRECTIONS = ("start", "end", "both")

    def __init__(
        self,
        *,
        child: Optional[Widget] = None,
        on_dismiss: Optional[Callable] = None,
        direction: str = "both",
        background: Optional[str] = None,
        icon: Optional[str] = None,
        confirm: bool = False,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if direction not in self.DIRECTIONS:
            raise ValueError(
                f"Dismissible direction must be one of {self.DIRECTIONS}")
        if child is not None:
            self.children = [child]
        self.direction = direction
        self.background = background
        self.icon = icon
        self.confirm = confirm
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "direction": self.direction,
            "background": self.background,
            "icon": self.icon,
            "confirm": self.confirm,
        })
        return {k: v for k, v in props.items() if v is not None}


class Draggable(Widget):
    """Makes a child draggable; emits ``drag`` with the live offset."""

    _widget_type = "Draggable"

    def __init__(self, *, child: Optional[Widget] = None,
                 axis: Optional[str] = None,
                 on_drag: Optional[Callable] = None,
                 on_drop: Optional[Callable] = None,
                 data: Optional[str] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(key=key, **kwargs)
        if axis not in (None, "horizontal", "vertical"):
            raise ValueError("Draggable axis must be horizontal or vertical")
        if child is not None:
            self.children = [child]
        self.axis = axis
        self.data = data
        if on_drag is not None:
            self.event_handlers["drag"] = on_drag
        if on_drop is not None:
            self.event_handlers["drop"] = on_drop

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({"axis": self.axis, "data": self.data})
        return {k: v for k, v in props.items() if v is not None}
