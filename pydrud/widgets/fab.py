"""
FloatingActionButton widget for Pydrud — a Material 3 action button.

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
    """A floating action button (Material 3).

    ``variant`` is one of ``"small"``, ``"regular"``, ``"large"`` or
    ``"extended"``. Extended buttons render their icon and label side by
    side; the others are square. Positioned via
    ``style.position = "absolute"`` plus ``bottom``/``right`` offsets, which
    the Android ``ViewFactory`` maps onto FrameLayout gravity and margins.
    """

    _widget_type = "FAB"

    VARIANTS = ("small", "regular", "large", "extended")
    # Material 3 defaults: 40 / 56 / 96dp squares, extended is 56dp tall.
    _SIZES = {"small": 40, "large": 96, "extended": 56}
    _RADII = {"small": 12, "regular": 16, "large": 28, "extended": 16}

    def render_type(self) -> str:
        """The FAB serialises as a ``Container`` (see :meth:`_serialise_self`)."""
        return "Container"

    def __init__(
        self,
        text: str = "",
        *,
        icon: Optional[str] = None,
        variant: str = "regular",
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

        if variant not in self.VARIANTS:
            raise ValueError(
                f"FAB variant must be one of {self.VARIANTS}, got {variant!r}")
        self._variant = variant
        if size is None:
            size = Tokens.fab_size if variant == "regular" else self._SIZES[variant]
        if elevation is None:
            elevation = Tokens.elevation_fab
        self._text = text
        self._icon = icon
        bg_color = bg_color or Theme.primary
        self._text_color = text_color or Colors.on(bg_color)

        base = {
            "bg": bg_color,
            "borderRadius": self._RADII[variant],
            "alignment": "center",
            "elevation": elevation,
            "position": "absolute",
        }
        if variant == "extended":
            base["height"] = size
            base["padding"] = {"left": 20, "right": 20}
        else:
            base["width"] = size
            base["height"] = size
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
        return {"text": self._text, "icon": self._icon or "", "variant": self._variant}

    def rebuild(self) -> None:
        """(Re)build the internal label/icon child widget(s)."""
        from pydrud.widgets.basic import Icon, Text

        base_font = dict(self.style.get("font") or {})
        base_font.setdefault("color", self._text_color)
        base_font.setdefault("weight", 500)

        if self._variant == "extended":
            from pydrud.widgets.layout import Row

            row_children = []
            if self._icon:
                row_children.append(Icon(
                    self._icon, key=f"{self.key}._icon",
                    style={"font": dict(base_font, size=20)}))
            if self._text:
                row_children.append(Text(
                    self._text, key=f"{self.key}._label",
                    style={"font": dict(base_font, size=16)}))
            self.children = [Row(
                children=row_children,
                spacing=10,
                vertical_alignment="center",
                main_axis_size="min",
                cross_axis_size="min",
                key=f"{self.key}._row",
            )]
            return

        # An explicit ``style={"font": {"size": …}}`` wins; otherwise the
        # Material default (24dp for a label, 22dp for an icon).
        icon_font = dict(base_font)
        icon_font.setdefault("size", 24 if not self._icon else 22)
        if self._icon:
            child: Widget = Icon(self._icon, key=f"{self.key}._icon",
                                 style={"font": icon_font})
        else:
            child = Text(
                self._text,
                key=f"{self.key}._label",
                style={"font": icon_font, "textAlign": "center"},
            )
        self.children = [child]

    def _serialise_self(self) -> dict:
        """Serialise the FAB as a Container with a centred label/icon.

        Uses the depth-safe ``_serialise_self`` hook (PB-001) rather than
        overriding ``to_dict``, so a FAB nested in a deep tree stays
        iterative.
        """
        self.rebuild()
        return {
            "type": "Container",
            "key": self.key,
            "style": self._serialise_style(),
            "expand": self.expand,
            "visible": self.visible,
            "tooltip": self.tooltip,
            "semantics": self.semantics,
            "has_events": bool(self.event_handlers),
            "events": sorted(self.event_handlers.keys()),
            "props": {"_fab": True},
            "children": [],
        }
