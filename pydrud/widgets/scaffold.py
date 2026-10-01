"""
Scaffold widget for Pydrud — Material-style page layout structure.

Lays out an AppBar at the top, the body in the middle (expand=1), an
optional bottom bar, and an optional floating action button overlay.

Usage::

    from pydrud import Scaffold, AppBar, Text, Column, FloatingActionButton

    Scaffold(
        app_bar=AppBar(title="Home"),
        body=Column(children=[Text("Hello!")]),
        floating_action_button=FloatingActionButton("+", on_click=add),
    )
"""

from __future__ import annotations
from typing import Optional

from pydrud.widgets.base import Widget
from pydrud.widgets.layout import Container, Column, Stack
from pydrud.widgets.app_bar import AppBar


class Scaffold(Widget):
    """Material-style page layout scaffold.

    Serialises to a ``Stack`` containing a vertical ``Column``
    (app bar / body / bottom bar) plus any floating overlay, so the body
    correctly fills the remaining space via LinearLayout weights while the
    FAB floats above everything.
    """

    _widget_type = "Scaffold"

    def __init__(
        self,
        *,
        app_bar: Optional[AppBar] = None,
        body: Optional[Widget] = None,
        bottom_bar: Optional[Widget] = None,
        floating_action_button: Optional[Widget] = None,
        bg_color: Optional[str] = None,
        key: Optional[str] = None,
        expand: Optional[int] = None,
        style: Optional[dict] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)

        self.app_bar = app_bar
        self.body = body
        self.bottom_bar = bottom_bar
        self.floating_action_button = floating_action_button
        self.bg_color = bg_color

        self.children = [self._build()]

    # ── internals ────────────────────────────────────────────────────────

    def _build(self) -> Stack:
        column_children: list[Widget] = []

        if self.app_bar is not None:
            column_children.append(self.app_bar)

        body_container = Container(
            key=f"{self.key}._body",
            expand=1,
            style={"width": "match", "height": 0},
            child=self.body,
        )
        column_children.append(body_container)

        if self.bottom_bar is not None:
            column_children.append(self.bottom_bar)

        column_style: dict = {"width": "match", "height": "match"}
        if self.bg_color:
            column_style["bg"] = self.bg_color

        stack_children: list[Widget] = [
            Column(
                key=f"{self.key}._column",
                style=column_style,
                children=column_children,
            )
        ]
        if self.floating_action_button is not None:
            stack_children.append(self.floating_action_button)

        stack_style: dict = {"width": "match", "height": "match"}
        if self.bg_color:
            stack_style["bg"] = self.bg_color
        stack_style.update(self.style)

        return Stack(
            key=f"{self.key}._stack",
            style=stack_style,
            expand=self.expand if self.expand is not None else 1,
            children=stack_children,
        )

    def rebuild(self) -> None:
        """Re-create the internal layout (after mutating body/app_bar/…)."""
        self.children = [self._build()]

    # ── serialisation ────────────────────────────────────────────────────

    def _serialise_props(self) -> dict:
        return {}

    def unwrap(self) -> Widget:
        self.rebuild()
        return self.children[0]

    def to_dict(self) -> dict:
        """Serialise as the internal Stack so Android renders it correctly."""
        self.rebuild()
        return self.children[0].to_dict()
