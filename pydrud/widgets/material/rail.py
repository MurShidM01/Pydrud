"""
Navigation rail, drawer and segmented buttons.
"""

from __future__ import annotations

from typing import Callable, Optional, Union
from pydrud.widgets.base import Widget
from pydrud.widgets.material._common import _clean
from pydrud.widgets.material.bottom_nav import NavItem

class NavigationRail(Widget):
    """A vertical navigation bar for tablets and landscape layouts."""

    _widget_type = "NavigationRail"

    def __init__(
        self,
        items: Optional[list[NavItem]] = None,
        *,
        selected: int = 0,
        extended: bool = False,
        leading: Optional[Widget] = None,
        on_change: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.items = list(items or [])
        self.selected = max(0, min(int(selected), max(0, len(self.items) - 1)))
        self.extended = extended
        if leading is not None:
            self.children = [leading]
        if on_change is not None:
            self.event_handlers["change"] = on_change

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "items": [i.to_dict() for i in self.items],
            "selected": self.selected,
            "extended": self.extended,
        })
        return props


class Drawer(Widget):
    """A navigation drawer that slides in from the start edge.

    Pass it to ``Scaffold(drawer=...)``; open it with ``page.open_drawer()``
    or by tapping the AppBar's hamburger icon.
    """

    _widget_type = "Drawer"

    def __init__(
        self,
        *,
        children: Optional[list[Widget]] = None,
        header: Optional[Widget] = None,
        width: float = 300,
        bg: Optional[str] = None,
        side: str = "start",
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if side not in ("start", "end"):
            raise ValueError("Drawer side must be 'start' or 'end'")
        self.width = float(width)
        self.bg = bg
        self.side = side
        self.children = []
        if header is not None:
            if header._auto_key:
                header.key = f"{self.key}_header"
                header._auto_key = False
            self.children.append(header)
        self.children.extend(children or [])

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({"width": self.width, "bg": self.bg,
                             "side": self.side}))
        return props


class SegmentedButton(Widget):
    """A row of connected buttons behaving like a single/multi choice group."""

    _widget_type = "SegmentedButton"

    def __init__(
        self,
        options: Optional[list[str]] = None,
        *,
        selected: Optional[Union[int, list[int]]] = 0,
        multi: bool = False,
        icons: Optional[list[str]] = None,
        on_change: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.options = [str(o) for o in (options or [])]
        self.multi = multi
        if multi:
            self.selected = list(selected) if isinstance(selected, (list, tuple)) \
                else ([selected] if isinstance(selected, int) else [])
        else:
            self.selected = selected if isinstance(selected, int) else 0
        self.icons = list(icons or [])
        if on_change is not None:
            self.event_handlers["change"] = on_change

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "options": self.options,
            "selected": self.selected,
            "multi": self.multi or None,
            "icons": self.icons or None,
        }))
        return props
