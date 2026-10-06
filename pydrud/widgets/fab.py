"""
FloatingActionButton widget for Pydrud — a circular action button.

Rendered as an absolutely positioned, rounded Container inside the root
FrameLayout (bottom-right by default), exactly like Material's FAB.

Usage::

    from pydrud import FloatingActionButton

    FloatingActionButton(
        icon="plus",
        on_click=lambda e: print("FAB tapped"),
    )

The colour follows :class:`pydrud.Theme` unless overridden, and the
native layer adds the Material press/elevation response.
"""

from __future__ import annotations
from typing import Callable, Optional

from pydrud.widgets.base import Widget
from pydrud.widgets.theme import Colors, Theme


class FloatingActionButton(Widget):
    """A circular floating action button.

    Positioned via ``style.position = "absolute"`` plus ``bottom``/``right``
    offsets, which the Android ``ViewFactory`` maps onto FrameLayout gravity
    and margins.
    """

    _widget_type = "FAB"

    def __init__(
        self,
        text: str = "",
        *,
        icon: Optional[str] = None,
        on_click: Optional[Callable] = None,
        bg_color: Optional[str] = None,
        text_color: Optional[str] = None,
        size: Optional[float] = None,
        elevation: Optional[float] = None,
        bottom: float = 24,
        right: float = 24,
        left: Optional[float] = None,
        top: Optional[float] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, visible=visible, **kwargs)
        from pydrud.widgets.tokens import Tokens

        if size is None:
            size = Tokens.fab_size
        if elevation is None:
            elevation = Tokens.elevation_fab
        self._text = text
        self._icon = icon
        bg_color = bg_color or Theme.primary
        self._text_color = text_color or Colors.on(bg_color)

        base = {
            "bg": bg_color,
            "width": size,
            "height": size,
            "borderRadius": size / 2,
            "alignment": "center",
            "elevation": elevation,
            "position": "absolute",
        }
        if left is not None:
            base["left"] = left
        else:
            base["right"] = right
        if top is not None:
            base["top"] = top
        else:
            base["bottom"] = bottom
        base.update(self.style)
        self.style = base

        if on_click is not None:
            self.event_handlers["click"] = on_click

        self.rebuild()

    @property
    def text(self) -> str:
        return self._icon or self._text

    def _serialise_props(self) -> dict:
        return {"text": self._text, "icon": self._icon or ""}

    def rebuild(self) -> None:
        """(Re)build the internal label/icon child widget."""
        from pydrud.widgets.basic import Icon, Text

        label_font = dict(self.style.get("font") or {})
        label_font.setdefault("color", self._text_color)
        label_font.setdefault("size", 24 if not self._icon else 22)
        label_font.setdefault("weight", 500)

        if self._icon:
            child: Widget = Icon(self._icon, key=f"{self.key}._icon", style={"font": label_font})
        else:
            child = Text(
                self._text,
                key=f"{self.key}._label",
                style={"font": label_font, "textAlign": "center"},
            )
        self.children = [child]

    def _serialise_self(self) -> dict:
        """Serialise the FAB as a Container with a centred label/icon.

        Uses the depth-safe ``_serialise_self`` hook (PB-001) rather than
        overriding ``to_dict``, so a FAB nested in a deep tree stays
        iterative.
        """
        from pydrud.widgets.base import _serialise_value

        self.rebuild()
        return {
            "type": "Container",
            "key": self.key,
            "style": _serialise_value(self.style),
            "expand": self.expand,
            "visible": self.visible,
            "tooltip": self.tooltip,
            "has_events": bool(self.event_handlers),
            "events": sorted(self.event_handlers.keys()),
            "props": {"_fab": True},
            "children": [],
        }
