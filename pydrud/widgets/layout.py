"""
Layout widgets: Container, Column, Row, Center, Spacer.
"""

from __future__ import annotations
from typing import Optional, Union

from pydrud.widgets.base import Widget
from pydrud.widgets.styling import EdgeInsets, Style


class Container(Widget):
    """A box that wraps a single child with padding, margin, bg, border, etc."""

    _widget_type = "Container"

    def __init__(
        self,
        *,
        child: Optional[Widget] = None,
        content: Optional[Widget] = None,
        padding: Optional[Union[EdgeInsets, float, int, dict]] = None,
        margin: Optional[Union[EdgeInsets, float, int, dict]] = None,
        bg: Optional[str] = None,
        border_radius: Optional[float] = None,
        width: Optional[Union[float, str]] = None,
        height: Optional[Union[float, str]] = None,
        alignment: Optional[str] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)

        # Accept both `child` and `content` for ergonomics.
        actual_child = child if child is not None else content
        if actual_child is not None:
            self.children = [actual_child]

        # Apply inline convenience args into style.
        s = Style()
        if padding is not None:
            s.padding(padding if isinstance(padding, EdgeInsets) else EdgeInsets.all(padding) if isinstance(padding, (int, float)) else EdgeInsets(**padding))
        if margin is not None:
            s.margin(margin if isinstance(margin, EdgeInsets) else EdgeInsets.all(margin) if isinstance(margin, (int, float)) else EdgeInsets(**margin))
        if bg:
            s.bg(bg)
        if border_radius is not None:
            s.border_radius(border_radius)
        if width is not None:
            s.width(width)
        if height is not None:
            s.height(height)
        if alignment is not None:
            s.alignment(alignment)
        self.style = {**s.build(), **self.style}


class Column(Widget):
    """Vertical layout — children are stacked top-to-bottom.

    ``horizontal_alignment`` positions children on the cross axis
    ("start" | "center" | "end") and ``vertical_alignment`` packs them
    along the main axis ("top" | "center" | "bottom")::

        Column(children=[card], vertical_alignment="center", expand=1)
    """

    _widget_type = "Column"

    def __init__(
        self,
        *,
        children: Optional[list[Widget]] = None,
        spacing: float = 0,
        horizontal_alignment: Optional[str] = None,
        vertical_alignment: Optional[str] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        scroll: bool = False,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self.children = list(children) if children else []
        self.style["spacing"] = spacing
        self.style["mainAxis"] = "vertical"
        if horizontal_alignment:
            self.style["crossAxisAlignment"] = horizontal_alignment
        if vertical_alignment:
            self.style["mainAxisAlignment"] = vertical_alignment
        if scroll:
            self.style["scroll"] = True

    def add(self, *widgets: Widget) -> "Column":
        self.children.extend(widgets)
        return self


class Row(Widget):
    """Horizontal layout — children are stacked left-to-right.

    ``vertical_alignment`` positions children on the cross axis
    ("top" | "center" | "bottom") and ``horizontal_alignment`` packs them
    along the main axis ("start" | "center" | "end")::

        Row(children=[reset, tap], horizontal_alignment="center")
    """

    _widget_type = "Row"

    def __init__(
        self,
        *,
        children: Optional[list[Widget]] = None,
        spacing: float = 0,
        vertical_alignment: Optional[str] = None,
        horizontal_alignment: Optional[str] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        scroll: bool = False,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self.children = list(children) if children else []
        self.style["spacing"] = spacing
        self.style["mainAxis"] = "horizontal"
        if vertical_alignment:
            self.style["crossAxisAlignment"] = vertical_alignment
        if horizontal_alignment:
            self.style["mainAxisAlignment"] = horizontal_alignment
        if scroll:
            self.style["scroll"] = True

    def add(self, *widgets: Widget) -> "Row":
        self.children.extend(widgets)
        return self


class Center(Widget):
    """Centres its child both horizontally and vertically."""

    _widget_type = "Center"

    def __init__(
        self,
        *,
        child: Optional[Widget] = None,
        content: Optional[Widget] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        actual_child = child if child is not None else content
        if actual_child is not None:
            self.children = [actual_child]
        self.style["alignment"] = "center"


class Spacer(Widget):
    """Empty space (flexible). Takes up remaining space in a Row/Column."""

    _widget_type = "Spacer"

    def __init__(
        self,
        *,
        expand: int = 1,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)


class Divider(Widget):
    """A hairline rule.

    Defaults to the theme outline colour and a true 1-pixel line, with
    optional ``indent`` so it starts where the text starts (the Material
    inset-divider look)::

        Divider()                  # full width hairline
        Divider(indent=56)         # aligned with list-tile text
    """

    _widget_type = "Divider"

    def __init__(
        self,
        *,
        color: Optional[str] = None,
        thickness: Optional[float] = None,
        indent: float = 0,
        end_indent: float = 0,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, visible=visible, **kwargs)
        from pydrud.widgets.theme import Theme
        from pydrud.widgets.tokens import Tokens

        self.style["color"] = color or Theme.outline
        self.style["thickness"] = (Tokens.divider_thickness
                                   if thickness is None else thickness)
        if indent or end_indent:
            self.style["margin"] = EdgeInsets(
                left=indent, right=end_indent).to_dict()


class Stack(Widget):
    """Overlays children on top of each other (like Flutter's ``Stack``).

    Children are drawn in order; use :class:`Positioned` (or the
    ``alignment`` style) to place them inside the stack.
    """

    _widget_type = "Stack"

    def __init__(
        self,
        *,
        children: Optional[list[Widget]] = None,
        alignment: Optional[str] = None,
        width: Optional[Union[float, str]] = None,
        height: Optional[Union[float, str]] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self.children = list(children) if children else []
        self.style.setdefault("width", width if width is not None else "match")
        self.style.setdefault("height", height if height is not None else "match")
        if alignment:
            self.style["alignment"] = alignment

    def add(self, *widgets: Widget) -> "Stack":
        self.children.extend(widgets)
        return self


class Positioned(Widget):
    """Positions a single child at absolute offsets inside a :class:`Stack`."""

    _widget_type = "Positioned"

    def __init__(
        self,
        *,
        child: Optional[Widget] = None,
        left: Optional[float] = None,
        top: Optional[float] = None,
        right: Optional[float] = None,
        bottom: Optional[float] = None,
        width: Optional[Union[float, str]] = None,
        height: Optional[Union[float, str]] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, visible=visible, **kwargs)
        if child is not None:
            self.children = [child]
        self.style["position"] = "absolute"
        for name, value in (
            ("left", left), ("top", top), ("right", right), ("bottom", bottom),
        ):
            if value is not None:
                self.style[name] = value
        if width is not None:
            self.style["width"] = width
        if height is not None:
            self.style["height"] = height


class SizedBox(Widget):
    """A fixed-size empty box — handy for precise gaps."""

    _widget_type = "SizedBox"

    def __init__(
        self,
        *,
        width: float = 0,
        height: float = 0,
        child: Optional[Widget] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, visible=visible, **kwargs)
        if child is not None:
            self.children = [child]
        self.style["width"] = width
        self.style["height"] = height


class Padding(Widget):
    """Applies padding around a single child."""

    _widget_type = "Padding"

    def __init__(
        self,
        padding: Union[EdgeInsets, float, int, dict] = 0,
        *,
        child: Optional[Widget] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        if child is not None:
            self.children = [child]
        self.style["padding"] = _edge_dict(padding)


class Card(Widget):
    """A rounded surface — Material 3 card.

    Defaults to the *filled/outlined* look modern Material uses (a soft
    hairline instead of a heavy drop shadow).  Pass ``elevation`` for the
    classic raised card, or ``outlined=False`` to drop the hairline::

        Card(child=Text("Hello"))                  # flat, outlined
        Card(child=Text("Hi"), elevation=3)        # raised
    """

    _widget_type = "Card"

    def __init__(
        self,
        *,
        child: Optional[Widget] = None,
        content: Optional[Widget] = None,
        bg: Optional[str] = None,
        elevation: Optional[float] = None,
        border_radius: Optional[float] = None,
        padding: Union[EdgeInsets, float, int, dict, None] = None,
        margin: Union[EdgeInsets, float, int, dict] = 0,
        outlined: Optional[bool] = None,
        on_click=None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        from pydrud.widgets.styling import Border
        from pydrud.widgets.theme import Theme

        from pydrud.widgets.tokens import Tokens

        actual_child = child if child is not None else content
        if actual_child is not None:
            self.children = [actual_child]
        # Defaults come from the design tokens, so Theme.configure(
        # radius_card=…) restyles every card in the app.
        if elevation is None:
            elevation = Tokens.elevation_card
        if border_radius is None:
            border_radius = Tokens.radius_card
        if padding is None:
            padding = Tokens.card_padding
        base = {
            "bg": bg or Theme.surface,
            "elevation": elevation,
            "borderRadius": border_radius,
            "padding": _edge_dict(padding),
            "margin": _edge_dict(margin),
            "width": "match",
        }
        # A hairline reads as "card" without the muddy shadow; skip it
        # when the card is deliberately raised.
        if outlined is None:
            outlined = elevation <= 0
        if outlined:
            base["border"] = Border(Theme.outline, 1).to_dict()
        if on_click is not None:
            self.event_handlers["click"] = on_click
            base.setdefault("feedback", True)
        base.update(self.style)
        self.style = base


class ListView(Widget):
    """A scrollable list of children (vertical by default)."""

    _widget_type = "ListView"

    def __init__(
        self,
        *,
        children: Optional[list[Widget]] = None,
        spacing: float = 0,
        horizontal: bool = False,
        padding: Optional[Union[EdgeInsets, float, int, dict]] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self.children = list(children) if children else []
        self.style["spacing"] = spacing
        self.style["mainAxis"] = "horizontal" if horizontal else "vertical"
        self.style["scroll"] = True
        self.style.setdefault("width", "match")
        if padding is not None:
            self.style["padding"] = _edge_dict(padding)

    def add(self, *widgets: Widget) -> "ListView":
        self.children.extend(widgets)
        return self


class GridView(Widget):
    """A simple fixed-column grid of children."""

    _widget_type = "GridView"

    def __init__(
        self,
        *,
        children: Optional[list[Widget]] = None,
        columns: int = 2,
        spacing: float = 8,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self.children = list(children) if children else []
        self.style["columns"] = max(1, int(columns))
        self.style["spacing"] = spacing
        self.style.setdefault("width", "match")

    def add(self, *widgets: Widget) -> "GridView":
        self.children.extend(widgets)
        return self


def _edge_dict(value: Union[EdgeInsets, float, int, dict]) -> dict:
    """Normalise padding/margin input into a serialisable dict."""
    if isinstance(value, EdgeInsets):
        return value.to_dict()
    if isinstance(value, (int, float)):
        return EdgeInsets.all(value).to_dict()
    if isinstance(value, dict):
        return EdgeInsets(**value).to_dict()
    raise TypeError(f"Unsupported edge value: {value!r}")
