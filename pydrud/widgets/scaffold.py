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
        bottom_navigation: Optional[Widget] = None,
        navigation_rail: Optional[Widget] = None,
        drawer: Optional[Widget] = None,
        end_drawer: Optional[Widget] = None,
        banner: Optional[Widget] = None,
        floating_action_button: Optional[Widget] = None,
        fab_position: str = "bottom_end",
        bg_color: Optional[str] = None,
        safe_area: bool = True,
        resize_to_avoid_keyboard: bool = True,
        adaptive: bool = False,
        content_max_width: Optional[float] = None,
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
        self.bottom_navigation = bottom_navigation
        self.navigation_rail = navigation_rail
        self.drawer = drawer
        self.end_drawer = end_drawer
        self.banner = banner
        self.floating_action_button = floating_action_button
        if fab_position not in ("bottom_end", "bottom_start", "bottom_center"):
            raise ValueError(
                "fab_position must be bottom_end, bottom_start or bottom_center")
        self.fab_position = fab_position
        self.bg_color = bg_color
        self.safe_area = safe_area
        self.resize_to_avoid_keyboard = resize_to_avoid_keyboard
        self.adaptive = adaptive
        self.content_max_width = content_max_width

        self.children = [self._build()]

    # ── internals ────────────────────────────────────────────────────────

    def _adapt(self) -> None:
        """On wide windows, move the bottom destinations into a side rail.

        Material's own guidance: a bottom bar on a 900dp tablet wastes the
        width and puts the targets miles from the user's thumbs. Opt in
        with ``Scaffold(adaptive=True)``.
        """
        if not self.adaptive or self.navigation_rail is not None:
            return
        bar = self.bottom_navigation
        if bar is None or not hasattr(bar, "items"):
            return

        from pydrud.core.responsive import MediaQuery

        if not MediaQuery.at_least("medium"):
            return

        from pydrud.widgets.material import NavigationRail

        self.navigation_rail = NavigationRail(
            bar.items,
            key=f"{bar.key}._rail",
            selected=bar.selected,
            extended=MediaQuery.at_least("expanded"),
            on_change=bar.event_handlers.get("change"),
        )
        self.bottom_navigation = None

    def _build(self) -> Stack:
        self._adapt()
        column_children: list[Widget] = []

        if self.app_bar is not None:
            column_children.append(self.app_bar)

        if self.banner is not None:
            column_children.append(self.banner)

        body_style: dict = {"width": "match", "height": 0}
        if self.content_max_width:
            # Caps and centres the content column on tablets and desktops,
            # so text lines stay readable instead of spanning the window.
            body_style["maxWidth"] = self.content_max_width
            body_style["alignment"] = "topCenter"
        body_container = Container(
            key=f"{self.key}._body",
            expand=1,
            style=body_style,
            child=self.body,
        )
        if self.navigation_rail is not None:
            # Rail sits beside the body, so wrap them in a Row.
            from pydrud.widgets.layout import Row

            column_children.append(Row(
                key=f"{self.key}._railrow",
                expand=1,
                style={"width": "match", "height": 0},
                children=[self.navigation_rail, body_container],
            ))
        else:
            column_children.append(body_container)

        if self.bottom_bar is not None:
            column_children.append(self.bottom_bar)

        if self.bottom_navigation is not None:
            column_children.append(self.bottom_navigation)

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
            fab = self.floating_action_button
            fab.style.setdefault("fabPosition", self.fab_position)
            # Lift the FAB above a bottom bar instead of letting it sit on
            # top of the navigation items.
            bar = self.bottom_navigation or self.bottom_bar
            if bar is not None and not fab.style.get("_fabLifted"):
                from pydrud.widgets.tokens import Tokens

                base = fab.style.get("bottom", 24)
                bar_height = getattr(bar, "effective_height", None)
                fab.style["bottom"] = base + (bar_height or Tokens.nav_height)
                fab.style["_fabLifted"] = True
                # The bar already clears the gesture inset.
                fab.style.setdefault("safeAreaBottom", False)
            stack_children.append(fab)

        for drawer, side in ((self.drawer, "start"), (self.end_drawer, "end")):
            if drawer is not None:
                drawer.style["drawerSide"] = side
                stack_children.append(drawer)

        if self.safe_area:
            self._absorb_insets(column_children, body_container)

        stack_style: dict = {"width": "match", "height": "match",
                             "safeArea": self.safe_area,
                             "resizeForKeyboard": self.resize_to_avoid_keyboard}
        if self.bg_color:
            stack_style["bg"] = self.bg_color
        stack_style.update(self.style)

        return Stack(
            key=f"{self.key}._stack",
            style=stack_style,
            expand=self.expand if self.expand is not None else 1,
            children=stack_children,
        )

    def _absorb_insets(self, column_children: list, body_container) -> None:
        """Let the widgets at the screen edges pad themselves.

        Pydrud draws edge to edge, so instead of inseting the whole page
        (which leaves grey strips behind the system bars) the top-most and
        bottom-most widgets extend their own background under the bars.
        """
        top = column_children[0] if column_children else body_container
        bottom = (self.bottom_navigation or self.bottom_bar
                  or (body_container if top is not body_container else None)
                  or body_container)
        top.style.setdefault("safeAreaTop", True)
        # A widget that already draws its own inset (bottom navigation) sets
        # safeAreaBottom=False, so setdefault leaves that decision alone.
        bottom.style.setdefault("safeAreaBottom", True)

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
