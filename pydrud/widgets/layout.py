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
    """Vertical layout — children are stacked top-to-bottom."""

    _widget_type = "Column"

    def __init__(
        self,
        *,
        children: Optional[list[Widget]] = None,
        spacing: float = 0,
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
        self.style["mainAxis"] = "vertical"
        if horizontal_alignment:
            self.style["crossAxisAlignment"] = horizontal_alignment
        if scroll:
            self.style["scroll"] = True

    def add(self, *widgets: Widget) -> "Column":
        self.children.extend(widgets)
        return self


class Row(Widget):
    """Horizontal layout — children are stacked left-to-right."""

    _widget_type = "Row"

    def __init__(
        self,
        *,
        children: Optional[list[Widget]] = None,
        spacing: float = 0,
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
        self.style["mainAxis"] = "horizontal"
        if vertical_alignment:
            self.style["crossAxisAlignment"] = vertical_alignment
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
    """A horizontal or vertical dividing line."""

    _widget_type = "Divider"

    def __init__(
        self,
        *,
        color: str = "#FFCCCCCC",
        thickness: float = 1.0,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, visible=visible, **kwargs)
        self.style["color"] = color
        self.style["thickness"] = thickness
