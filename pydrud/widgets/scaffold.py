"""
Scaffold widget for Pydrud — Material-style page layout structure.

Positions an AppBar at the top and a body widget in the middle (expand=1).
The Scaffold serialises as a Column (LinearLayout VERTICAL) on Android,
which correctly handles the expand/weight property for the body.

Usage::

    from pydrud import Scaffold, AppBar, Text

    Scaffold(
        app_bar=AppBar(title="Home"),
        body=Column(children=[Text("Hello!")]),
    )
"""

from __future__ import annotations
from typing import Optional

from pydrud.widgets.base import Widget
from pydrud.widgets.layout import Container, Column
from pydrud.widgets.app_bar import AppBar


class Scaffold(Widget):
    """Material-style page layout scaffold.

    Lays out an AppBar at the top and body content in the centre (expand=1).
    Uses a Column (LinearLayout VERTICAL on Android) so the body correctly
    fills remaining space via expand/weight.

    For a floating action button, add it separately via ``page.add()``
    or position it with absolute style positioning.
    """

    _widget_type = "Scaffold"

    def __init__(
        self,
        *,
        app_bar: Optional[AppBar] = None,
        body: Optional[Widget] = None,
        bg_color: Optional[str] = None,
        key: Optional[str] = None,
        expand: Optional[int] = None,
        style: Optional[dict] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(
            key=key,
            style=style,
            expand=expand,
            visible=visible,
            **kwargs,
        )

        sc_children: list[Widget] = []

        # 1. AppBar at top (wrap_content height).
        if app_bar is not None:
            sc_children.append(app_bar)

        # 2. Body in the middle (fills remaining space via expand=1).
        if body is not None:
            body_container = Container(
                key=f"_scaffold_body_{self.key}",
                expand=1,
                child=body,
            )
            sc_children.append(body_container)
        else:
            sc_children.append(
                Container(key=f"_scaffold_body_{self.key}", expand=1)
            )

        # Build the root as a Column (LinearLayout VERTICAL on Android)
        # which correctly handles expand/weight for children.
        root_style = {"width": "match", "height": "match"}
        if bg_color:
            root_style["bg"] = bg_color
        if self.style:
            root_style.update(self.style)

        # Serialise as a Column rather than a Container, because
        # Container -> FrameLayout does NOT support expand/weight,
        # but Column -> LinearLayout VERTICAL DOES.
        root = Column(
            expand=1,
            children=sc_children,
        )
        self.style = root_style
        self.children = [root]

    def _serialise_props(self) -> dict:
        return {}

    def to_dict(self) -> dict:
        """Serialize as a Column for proper expand/weight support."""
        d: dict = {
            "type": "Column",
            "key": f"_scaffold_{self.key}",
            "style": dict(self.style),
            "expand": self.expand or 1,
            "visible": self.visible,
            "has_events": bool(self.event_handlers),
            "props": {"_scaffold": True},
        }
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d
