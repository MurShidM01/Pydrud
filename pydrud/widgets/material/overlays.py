"""
Declarative modal overlays — dialogs and bottom sheets.

These widgets are the *declarative* face of the modal API: include the widget
in the tree to show the overlay, drop it to dismiss.  They are ideal when the
overlay is part of the screen's state (``if self.confirming: return
AlertDialog(...)``) rather than something you ``await``.

For the imperative, await-a-result form (``page.dialog.confirm(...)``) use
:class:`pydrud.services.native.dialogs.Dialogs` — that API is unchanged.

Events: tapping a dialog action dispatches ``click`` on the widget's key with
``{"action": <value>}``; tapping a sheet option dispatches ``click`` with
``{"index": <i>, "label": <label>}``.  Tapping outside or pressing back
dispatches ``dismiss``.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence, Union

from pydrud.widgets.base import Widget
from pydrud.widgets.material._common import _clean


def _normalise_actions(actions: Optional[Sequence[Union[str, tuple]]]) -> list[dict]:
    """Turn ``["OK"]`` / ``[("Cancel", "cancel")]`` into ``{label, value}``."""
    out: list[dict] = []
    for action in actions or []:
        if isinstance(action, (tuple, list)):
            label = action[0] if len(action) > 0 else ""
            value = action[1] if len(action) > 1 else label
        else:
            label = value = action
        out.append({"label": str(label), "value": str(value)})
    return out


class AlertDialog(Widget):
    """A modal dialog with a title, message and up to three actions.

    ``actions`` is a sequence of ``(label, value)`` pairs (or bare labels).
    They render left-to-right in the order given, so the last one is the
    affirmative button::

        AlertDialog(
            title="Delete this item?",
            message="This cannot be undone.",
            actions=[("Cancel", "cancel"), ("Delete", "delete")],
            on_click=lambda e: self._on_dialog(e.data["action"]),
            on_dismiss=lambda e: self._close_dialog(),
        )

    The dialog stays on screen for as long as the widget is in the tree, so
    the handler above should drop it (and rebuild) to dismiss it.
    """

    _widget_type = "AlertDialog"

    def __init__(
        self,
        *,
        title: str = "",
        message: str = "",
        icon: Optional[str] = None,
        actions: Optional[Sequence[Union[str, tuple]]] = None,
        dismissible: bool = True,
        on_click: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_click=on_click, **kwargs)
        self.title = str(title)
        self.message = str(message)
        self.icon = icon
        self.actions = _normalise_actions(actions)
        self.dismissible = bool(dismissible)
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "title": self.title,
            "message": self.message,
            "icon": self.icon,
            "actions": self.actions or None,
            "dismissible": self.dismissible,
        }))
        return props


class Dialog(AlertDialog):
    """Flutter-style alias for :class:`AlertDialog`."""

    _widget_type = "AlertDialog"


class ModalBottomSheet(Widget):
    """A modal bottom sheet presenting a list of options.

    Tapping an option dispatches ``click`` with ``{"index": i, "label": ...}``
    on the widget's key; the sheet then dismisses itself and Python is
    expected to drop the widget from the tree::

        ModalBottomSheet(
            title="Share via",
            options=["Messages", "Email", "Copy link"],
            icons=[Icons.MESSAGE, Icons.EMAIL, Icons.LINK],
            on_click=lambda e: self._on_share(e.data["index"]),
            on_dismiss=lambda e: self._close_sheet(),
        )
    """

    _widget_type = "ModalBottomSheet"

    def __init__(
        self,
        *,
        title: str = "",
        options: Optional[Sequence[str]] = None,
        icons: Optional[Sequence[str]] = None,
        dismissible: bool = True,
        on_click: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_click=on_click, **kwargs)
        self.title = str(title)
        self.options = [str(o) for o in (options or [])]
        self.icons = [str(i) for i in (icons or [])]
        self.dismissible = bool(dismissible)
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "title": self.title,
            "options": self.options or None,
            "icons": self.icons or None,
            "dismissible": self.dismissible,
        }))
        return props
