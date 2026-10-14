"""
Navigation components — Material 3 bottom app bar, search view, FAB menu.
"""

from __future__ import annotations

from typing import Callable, Optional
from pydrud.widgets.base import Widget
from pydrud.widgets.material._common import _clean


class BottomAppBar(Widget):
    """A Material 3 bottom app bar.

    Contains navigation actions and an optional FAB cutout.
    Different from NavigationBar — BottomAppBar holds actions,
    not destinations.

    ::

        BottomAppBar(
            actions=[
                IconButton(Icons.SEARCH),
                IconButton(Icons.CAMERA),
                IconButton(Icons.DELETE),
            ],
            fab_cutout=True,
        )
    """

    _widget_type = "BottomAppBar"

    def __init__(
        self,
        *,
        actions: Optional[list[Widget]] = None,
        fab_cutout: bool = False,
        bg: Optional[str] = None,
        elevation: Optional[float] = None,
        on_click: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_click=on_click, **kwargs)
        self.actions = list(actions or [])
        self.fab_cutout = bool(fab_cutout)
        self.bg = bg
        self.elevation = elevation
        for i, action in enumerate(self.actions):
            if isinstance(action, Widget) and action._auto_key:
                action.key = f"{self.key}_action{i}"
                action._auto_key = False
        self.children = list(self.actions)

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "fabCutout": self.fab_cutout or None,
            "bg": self.bg,
            "elevation": self.elevation,
        }))
        return props


class FABMenu(Widget):
    """A Material 3 FAB menu — a FAB that expands to show multiple actions.

    ::

        FABMenu(
            icon="plus",
            actions=[
                FABMenuItem("Email", icon="email"),
                FABMenuItem("Chat", icon="chat"),
                FABMenuItem("Phone", icon="call"),
            ],
            on_select=lambda e: print(e.data["index"]),
        )
    """

    _widget_type = "FABMenu"

    def __init__(
        self,
        *,
        icon: str = "plus",
        expanded: bool = False,
        actions: Optional[list] = None,
        on_select: Optional[Callable] = None,
        on_expand: Optional[Callable] = None,
        on_collapse: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.icon = icon
        self.expanded = bool(expanded)
        self.actions = list(actions or [])
        if on_select is not None:
            self.event_handlers["select"] = on_select
        if on_expand is not None:
            self.event_handlers["expand"] = on_expand
        if on_collapse is not None:
            self.event_handlers["collapse"] = on_collapse

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "icon": self.icon,
            "expanded": self.expanded,
            "actions": [
                a.to_dict() if hasattr(a, "to_dict") else {"label": str(a)}
                for a in self.actions
            ] or None,
        }))
        return props


class FABMenuItem:
    """One item in a :class:`FABMenu`."""

    __slots__ = ("label", "icon", "value")

    def __init__(self, label: str = "", *, icon: Optional[str] = None,
                 value: Optional[str] = None):
        self.label = str(label)
        self.icon = icon
        self.value = value if value is not None else self.label

    def to_dict(self) -> dict:
        d = {"label": self.label, "value": self.value}
        if self.icon:
            d["icon"] = self.icon
        return d


class SearchView(Widget):
    """A Material 3 expanded search view.

    Transitions from a search bar into a full-screen search experience
    with suggestions, recent searches, and results.

    ::

        SearchView(
            hint="Search messages",
            suggestions=["Recent search 1", "Recent search 2"],
            on_change=lambda e: filter(e.data["query"]),
            on_submit=lambda e: search(e.data["query"]),
            on_dismiss=lambda e: close_search(),
        )
    """

    _widget_type = "SearchView"

    def __init__(
        self,
        *,
        value: str = "",
        hint: str = "Search",
        suggestions: Optional[list[str]] = None,
        recent: Optional[list[str]] = None,
        autofocus: bool = True,
        on_change: Optional[Callable] = None,
        on_submit: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.value = str(value)
        self.hint = hint
        self.suggestions = list(suggestions or [])
        self.recent = list(recent or [])
        self.autofocus = autofocus
        if on_change is not None:
            self.event_handlers["change"] = on_change
        if on_submit is not None:
            self.event_handlers["submit"] = on_submit
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "value": self.value,
            "hint": self.hint,
            "suggestions": self.suggestions or None,
            "recent": self.recent or None,
            "autofocus": self.autofocus or None,
        }))
        return props