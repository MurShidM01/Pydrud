"""
Sheet components — Material 3 bottom and side sheets.

Provides standard (persistent/expandable) bottom sheets, side sheets,
and full-screen dialogs.
"""

from __future__ import annotations

from typing import Callable, Optional
from pydrud.widgets.base import Widget
from pydrud.widgets.material._common import _clean


class StandardBottomSheet(Widget):
    """A Material 3 standard (persistent) bottom sheet.

    Unlike ModalBottomSheet (which is modal with a scrim), a standard
    bottom sheet coexists with the main content and can be expanded/collapsed.

    ::

        StandardBottomSheet(
            child=Column(children=[Text("Details"), ...]),
            expanded=False,
            on_expand=lambda e: toggle_sheet(),
        )
    """

    _widget_type = "StandardBottomSheet"

    def __init__(
        self,
        *,
        child: Optional[Widget] = None,
        expanded: bool = False,
        drag_handle: bool = True,
        on_expand: Optional[Callable] = None,
        on_collapse: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.expanded = bool(expanded)
        self.drag_handle = bool(drag_handle)
        if child is not None:
            self.children = [child]
        if on_expand is not None:
            self.event_handlers["expand"] = on_expand
        if on_collapse is not None:
            self.event_handlers["collapse"] = on_collapse

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "expanded": self.expanded,
            "dragHandle": self.drag_handle or None,
        }))
        return props


class SideSheet(Widget):
    """A Material 3 side sheet for expanded window classes.

    Anchored to the side of the screen on medium+ breakpoints.
    Replaces bottom sheets on larger screens.

    ::

        SideSheet(
            title="Filters",
            child=Column(children=[...]),
            side="end",
            width=360,
            on_dismiss=lambda e: close_sheet(),
        )
    """

    _widget_type = "SideSheet"

    def __init__(
        self,
        *,
        title: str = "",
        child: Optional[Widget] = None,
        side: str = "end",
        width: float = 360,
        dismissible: bool = True,
        on_dismiss: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if side not in ("start", "end"):
            raise ValueError("SideSheet side must be 'start' or 'end'")
        self.title = str(title)
        self.side = side
        self.width = float(width)
        self.dismissible = bool(dismissible)
        if child is not None:
            self.children = [child]
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "title": self.title,
            "side": self.side,
            "width": self.width,
            "dismissible": self.dismissible or None,
        }))
        return props


class FullScreenDialog(Widget):
    """A Material 3 full-screen dialog for complex forms.

    Used on compact window classes for complex tasks that need
    the entire screen (date range selection, multi-step forms, etc.).

    ::

        FullScreenDialog(
            title="New Event",
            body=Column(children=[...]),
            action="Save",
            on_action=lambda e: save_event(),
            on_dismiss=lambda e: close(),
        )
    """

    _widget_type = "FullScreenDialog"

    def __init__(
        self,
        *,
        title: str = "",
        body: Optional[Widget] = None,
        action: Optional[str] = None,
        icon: Optional[str] = None,
        on_action: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.title = str(title)
        self.action = action
        self.icon = icon
        if body is not None:
            self.children = [body]
        if on_action is not None:
            self.event_handlers["action"] = on_action
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "title": self.title,
            "action": self.action,
            "icon": self.icon,
        }))
        return props