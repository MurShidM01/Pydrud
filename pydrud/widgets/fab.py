"""
FloatingActionButton widget for Pydrud — a circular action button.

Positioned at the bottom-right of a Scaffold using FrameLayout gravity.
Can display an icon or text label.

Usage::

    from pydrud import FloatingActionButton

    FloatingActionButton(
        text="+",
        on_click=lambda _: print("FAB tapped"),
        bg_color="#7C3AED",
    )
"""

from __future__ import annotations
from typing import Callable, Optional

from pydrud.widgets.base import Widget
from pydrud.widgets.basic import Text


class FloatingActionButton(Widget):
    """A circular floating action button positioned bottom-right.

    The FAB uses absolute positioning via FrameLayout gravity
    (bottom | right), which the Android ViewFactory already supports
    via the ``style.position = "absolute"`` handling in ``applyStyle()``.
    """

    _widget_type = "FAB"

    def __init__(
        self,
        text: str = "",
        *,
        icon: Optional[str] = None,
        on_click: Optional[Callable] = None,
        bg_color: str = "#7C3AED",
        text_color: str = "#FFFFFF",
        size: float = 56,
        elevation: float = 6,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        **kwargs,
    ):
        super().__init__(key=key, style=style, **kwargs)

        self._text = text
        self._icon = icon
        self._on_click = on_click

        # Build the internal style dict with absolute bottom-right positioning.
        self.style["bg"] = bg_color
        self.style["width"] = size
        self.style["height"] = size
        self.style["borderRadius"] = size / 2
        self.style["alignment"] = "center"
        self.style["elevation"] = elevation
        self.style["position"] = "absolute"
        self.style["bottom"] = 24
        self.style["right"] = 24

        if on_click is not None:
            self.event_handlers["click"] = on_click

    def _serialise_props(self) -> dict:
        return {"text": self._text}

    def to_dict(self) -> dict:
        """Serialize the FAB as a Container view for Android rendering."""
        display_text = self._icon or self._text
        from pydrud.widgets.layout import Container
        from pydrud.widgets.styling import Alignment

        child_style = {}
        if self.style.get("font"):
            child_style["font"] = self.style["font"]

        d: dict = {
            "type": "Container",
            "key": self.key,
            "style": dict(self.style),
            "expand": self.expand,
            "visible": self.visible,
            "has_events": bool(self.event_handlers),
            "props": {},
            "children": [
                {
                    "type": "Container",
                    "key": f"_fab_content_{self.key}",
                    "style": child_style,
                    "children": [
                        {
                            "type": "Text",
                            "key": f"_fab_label_{self.key}",
                            "style": {},
                            "props": {"value": display_text},
                        }
                    ],
                }
            ],
        }
        return d
