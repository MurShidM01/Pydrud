"""
Snackbar — Material 3 transient message.

The primary M3 feedback widget for brief messages about an action.
Supports action buttons, swipe-to-dismiss, and positioning above
FAB/navigation bar.
"""

from __future__ import annotations

from typing import Callable, Optional
from pydrud.widgets.base import Widget
from pydrud.widgets.material._common import _clean


class Snackbar(Widget):
    """A Material 3 snackbar for brief messages.

    Unlike a Banner (persistent, at top), a Snackbar appears temporarily
    at the bottom and auto-dismisses after a duration.

    ::

        Snackbar("Item deleted", action="Undo", on_action=undo_delete)
        Snackbar("Connection lost", duration=0)  # indefinite
    """

    _widget_type = "Snackbar"

    def __init__(
        self,
        message: str = "",
        *,
        action: Optional[str] = None,
        icon: Optional[str] = None,
        duration: int = 4000,
        dismissible: bool = True,
        two_line: bool = False,
        on_action: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.message = str(message)
        self.action = action
        self.icon = icon
        self.duration = int(duration)
        self.dismissible = bool(dismissible)
        self.two_line = bool(two_line)
        if on_action is not None:
            self.event_handlers["action"] = on_action
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "message": self.message,
            "action": self.action,
            "icon": self.icon,
            "duration": self.duration,
            "dismissible": self.dismissible,
            "twoLine": self.two_line or None,
        }))
        return props