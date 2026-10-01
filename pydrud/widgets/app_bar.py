"""
AppBar widget for Pydrud — a Material-style top app bar.

Provides a consistent header with an optional leading widget (e.g. back
button), a title, and trailing action widgets.

Usage::

    from pydrud import AppBar, Text, Icon

    AppBar(
        title=Text("Home", size=20, weight=700, color="#FFFFFF"),
        leading=Icon("back").on_click(lambda _: router.pop()),
        actions=[
            Icon("search").on_click(lambda _: ...),
            Icon("settings").on_click(lambda _: ...),
        ],
        bg_color="#7C3AED",
        elevation=4,
    )
"""

from __future__ import annotations
from typing import Callable, Optional

from pydrud.widgets.base import Widget
from pydrud.widgets.layout import Container, Row
from pydrud.widgets.styling import EdgeInsets
from pydrud.widgets.basic import Text


class AppBar(Widget):
    """Material-style top app bar.

    Composes a Row widget with leading / title / actions children
    and a background Container. Serializes to standard Container+Row
    JSON that the Android ViewFactory already understands.
    """

    _widget_type = "AppBar"

    def __init__(
        self,
        title: Widget | str | None = None,
        *,
        leading: Optional[Widget] = None,
        actions: Optional[list[Widget]] = None,
        bg_color: str = "#7C3AED",
        elevation: float = 4,
        padding: Optional[dict] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        **kwargs,
    ):
        super().__init__(key=key, style=style, **kwargs)

        # Resolve title (string → Text widget).
        title_widget: Widget | None = None
        if isinstance(title, str):
            title_widget = Text(
                title,
                size=20,
                weight=700,
                color="#FFFFFF",
            )
        elif isinstance(title, Widget):
            title_widget = title

        # Build row children: [leading, title (expand=1), *actions]
        row_children: list[Widget] = []

        if leading is not None:
            if isinstance(leading, Widget):
                row_children.append(
                    Container(
                        padding=EdgeInsets.all(8),
                        child=leading,
                    )
                )

        if title_widget is not None:
            row_children.append(
                Container(
                    expand=1,
                    child=title_widget,
                )
            )

        if actions:
            for action in actions:
                if isinstance(action, Widget):
                    row_children.append(
                        Container(
                            padding=EdgeInsets.all(8),
                            child=action,
                        )
                    )

        # Build the internal children: a single Row inside a Container.
        padding = padding or {"left": 16, "top": 12, "right": 16, "bottom": 12}
        internal_style = {
            "bg": bg_color,
            "elevation": elevation,
            "padding": padding,
        }
        if self.style:
            internal_style.update(self.style)

        bar_row = Row(children=row_children)
        bar_container = Container(
            key=f"_appbar_{self.key}",
            style=internal_style,
            child=bar_row,
        )

        self.children = [bar_container]

    def to_dict(self) -> dict:
        """Delegates to the internal Container so Android renders it correctly."""
        if self.children:
            return self.children[0].to_dict()
        return super().to_dict()

    def _serialise_props(self) -> dict:
        return {}
