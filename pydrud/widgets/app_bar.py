"""
AppBar widget for Pydrud — a Material-style top app bar.

Provides a consistent header with an optional leading widget (e.g. a back
button), a title, and trailing action widgets.

Usage::

    from pydrud import AppBar, Text, Icon

    AppBar(
        title="Home",
        leading=Icon("back").on_click(lambda e: router.pop()),
        actions=[Icon("search").on_click(on_search)],
        bg_color="#FF7C3AED",
        elevation=4,
    )
"""

from __future__ import annotations
from typing import Optional, Union

from pydrud.widgets.base import Widget
from pydrud.widgets.layout import Container, Row
from pydrud.widgets.styling import EdgeInsets
from pydrud.widgets.basic import Text


class AppBar(Widget):
    """Material-style top app bar.

    Internally composes ``Container(Row(leading, title, *actions))`` and
    serialises to plain Container/Row JSON that the Android ViewFactory
    already understands.
    """

    _widget_type = "AppBar"

    def __init__(
        self,
        title: Union[Widget, str, None] = None,
        *,
        leading: Optional[Widget] = None,
        actions: Optional[list[Widget]] = None,
        bg_color: str = "#FF7C3AED",
        color: str = "#FFFFFFFF",
        elevation: float = 4,
        center_title: bool = False,
        padding: Optional[Union[EdgeInsets, dict]] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, visible=visible, **kwargs)

        self.title = title
        self.leading = leading
        self.actions = list(actions or [])
        self.bg_color = bg_color
        self.color = color
        self.elevation = elevation
        self.center_title = center_title
        if isinstance(padding, EdgeInsets):
            self.padding = padding.to_dict()
        else:
            self.padding = padding or EdgeInsets(left=16, top=12, right=16, bottom=12).to_dict()

        self.children = [self._build()]

    # ── internals ────────────────────────────────────────────────────────

    def _title_widget(self) -> Optional[Widget]:
        if isinstance(self.title, str):
            return Text(
                self.title,
                size=20,
                weight=700,
                color=self.color,
                text_align="center" if self.center_title else None,
                key=f"{self.key}._title",
            )
        return self.title if isinstance(self.title, Widget) else None

    def _build(self) -> Container:
        row_children: list[Widget] = []

        if isinstance(self.leading, Widget):
            row_children.append(
                Container(
                    key=f"{self.key}._leading",
                    padding=EdgeInsets.all(8),
                    child=self.leading,
                )
            )

        title_widget = self._title_widget()
        if title_widget is not None:
            row_children.append(
                Container(key=f"{self.key}._titlebox", expand=1, child=title_widget)
            )
        else:
            row_children.append(Container(key=f"{self.key}._titlebox", expand=1))

        for index, action in enumerate(self.actions):
            if isinstance(action, Widget):
                row_children.append(
                    Container(
                        key=f"{self.key}._action{index}",
                        padding=EdgeInsets.all(8),
                        child=action,
                    )
                )

        bar_style = {
            "bg": self.bg_color,
            "elevation": self.elevation,
            "padding": self.padding,
            "width": "match",
        }
        bar_style.update(self.style)

        return Container(
            key=f"{self.key}._bar",
            style=bar_style,
            child=Row(
                key=f"{self.key}._row",
                vertical_alignment="center",
                children=row_children,
            ),
        )

    # ── serialisation ────────────────────────────────────────────────────

    def rebuild(self) -> None:
        """Re-create the internal layout (after mutating title/actions)."""
        self.children = [self._build()]

    def unwrap(self) -> Widget:
        self.rebuild()
        return self.children[0]

    def to_dict(self) -> dict:
        """Delegate to the internal Container so Android renders it correctly."""
        self.rebuild()
        return self.children[0].to_dict()

    def _serialise_props(self) -> dict:
        return {}
