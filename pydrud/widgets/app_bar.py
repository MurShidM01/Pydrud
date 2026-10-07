"""
AppBar widget for Pydrud — a Material-style top app bar.

Provides a consistent header with an optional leading widget (e.g. a back
button), a title, and trailing action widgets.

Usage::

    from pydrud import AppBar, Text, Icon

    AppBar(
        title="Home",
        leading=Icon("arrow_left").on_click(lambda e: router.pop()),
        actions=[Icon("magnify").on_click(on_search)],
    )

Colours follow :class:`pydrud.Theme` unless you override them, so the bar
always matches the rest of the app (including dark mode).  The bar is a
flat Material 3 surface by default; pass ``elevation`` for a shadow or
``bg_color=Colors.PRIMARY`` for the classic coloured bar.
"""

from __future__ import annotations
from typing import Optional, Union

from pydrud.widgets.base import Widget
from pydrud.widgets.layout import Container, Row
from pydrud.widgets.styling import Border, EdgeInsets
from pydrud.widgets.basic import Text
from pydrud.widgets.tokens import Tokens
from pydrud.widgets.theme import Colors, Theme


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
        bg_color: Optional[str] = None,
        color: Optional[str] = None,
        elevation: float = 0,
        center_title: bool = False,
        height: Optional[int] = None,
        density: str = "normal",
        safe_area: bool = True,
        divider: bool = True,
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
        self.bg_color = bg_color or Theme.surface
        self.color = color or (Colors.on(self.bg_color)
                               if bg_color else Theme.text)
        self.elevation = elevation
        self.center_title = center_title
        if density not in ("compact", "normal", "comfortable"):
            raise ValueError("density must be compact, normal or comfortable")
        self.density = density
        self.safe_area = bool(safe_area)
        self.height = height
        self.divider = divider
        if isinstance(padding, EdgeInsets):
            self.padding = padding.to_dict()
        else:
            # Leading/action controls retain a 48dp target; density changes
            # the bar's breathing room instead of making them hard to tap.
            left = 6 if isinstance(leading, Widget) else 16
            vertical = {"compact": 4, "normal": 8, "comfortable": 12}[density]
            self.padding = padding or EdgeInsets(
                left=left, top=vertical, right=6, bottom=vertical).to_dict()

        self.children = [self._build()]

    # ── internals ────────────────────────────────────────────────────────

    def _title_widget(self) -> Optional[Widget]:
        if isinstance(self.title, str):
            return Text(
                self.title,
                size=20,
                weight=600,
                color=self.color,
                text_align="center" if self.center_title else None,
                max_lines=1,
                overflow="ellipsis",
                key=f"{self.key}._title",
                style={"font": {"letterSpacing": 0.0}},
            )
        return self.title if isinstance(self.title, Widget) else None

    def _build(self) -> Container:
        row_children: list[Widget] = []

        if isinstance(self.leading, Widget):
            row_children.append(self._action_slot(self.leading, "_leading"))

        title_widget = self._title_widget()
        title_pad = EdgeInsets(left=10 if isinstance(self.leading, Widget) else 4,
                               right=4)
        if title_widget is not None:
            row_children.append(
                Container(key=f"{self.key}._titlebox", expand=1,
                          padding=title_pad, child=title_widget)
            )
        else:
            row_children.append(Container(key=f"{self.key}._titlebox", expand=1))

        for index, action in enumerate(self.actions):
            if isinstance(action, Widget):
                row_children.append(self._action_slot(action, f"_action{index}"))

        density_height = {
            "compact": max(48, Tokens.app_bar_height - 8),
            "normal": Tokens.app_bar_height,
            "comfortable": max(64, Tokens.app_bar_height + 8),
        }[self.density]
        bar_style = {
            "bg": self.bg_color,
            "elevation": self.elevation,
            "padding": self.padding,
            "width": "match",
            # Each instance can opt into a density without changing the
            # global token used by every other screen.
            "minHeight": self.height if self.height is not None else density_height,
            # Stand-alone app bars are edge-to-edge safe by default. Scaffold
            # uses setdefault, so this also composes without wrapper widgets.
            "safeAreaTop": self.safe_area,
        }
        if self.divider and not self.elevation:
            # Hairline separator instead of a shadow — the modern look.
            bar_style["border"] = Border.only(
                bottom=True, color=Theme.outline, width=1).to_dict()
        bar_style.update(self._effective_style())

        return Container(
            key=f"{self.key}._bar",
            style=bar_style,
            child=Row(
                key=f"{self.key}._row",
                vertical_alignment="center",
                children=row_children,
            ),
        )

    def _action_slot(self, child: Widget, suffix: str) -> Container:
        """Wrap an icon/button in a 48dp circular, ripple-backed target."""
        return Container(
            key=f"{self.key}.{suffix}",
            padding=EdgeInsets.all(12),
            style={"borderRadius": 24, "feedback": True},
            child=child,
        )

    # ── serialisation ────────────────────────────────────────────────────

    def rebuild(self) -> None:
        """Re-create the internal layout (after mutating title/actions)."""
        self.children = [self._build()]

    def unwrap(self) -> Widget:
        self.rebuild()
        return self.children[0]

    def _serialise_props(self) -> dict:
        return {}
