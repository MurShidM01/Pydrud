"""
Chips, badges, avatars, banners and tooltips.
"""

from __future__ import annotations

from typing import Callable, Optional, Union
from pydrud.widgets.base import Widget
from pydrud.widgets.theme import Colors
from pydrud.widgets.material._common import _clean

class Chip(Widget):
    """A compact element for tags, filters and choices.

    ``variant`` is one of ``"assist"``, ``"filter"``, ``"input"``, ``"suggestion"``.
    Filter chips are selectable and emit ``change`` with ``{"selected": bool}``.
    """

    _widget_type = "Chip"

    VARIANTS = ("assist", "filter", "input", "suggestion")

    def __init__(
        self,
        label: str = "",
        *,
        icon: Optional[str] = None,
        variant: str = "assist",
        selected: bool = False,
        deletable: bool = False,
        color: Optional[str] = None,
        on_click: Optional[Callable] = None,
        on_change: Optional[Callable] = None,
        on_delete: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_click=on_click, **kwargs)
        if variant not in self.VARIANTS:
            raise ValueError(
                f"Chip variant must be one of {self.VARIANTS}, got {variant!r}")
        self.label = str(label)
        self.icon = icon
        self.variant = variant
        self.selected = bool(selected)
        self.deletable = bool(deletable)
        self.color = color
        if on_change is not None:
            self.event_handlers["change"] = on_change
        if on_delete is not None:
            self.event_handlers["delete"] = on_delete

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "label": self.label,
            "icon": self.icon,
            "variant": self.variant,
            "selected": self.selected,
            "deletable": self.deletable or None,
            "color": self.color,
        }))
        return props


class AssistChip(Chip):
    """Convenience chip for lightweight actions."""

    def __init__(self, label: str = "", **kwargs):
        kwargs.setdefault("variant", "assist")
        super().__init__(label, **kwargs)


class FilterChip(Chip):
    """Selectable chip that emits ``change`` when toggled."""

    def __init__(self, label: str = "", **kwargs):
        kwargs.setdefault("variant", "filter")
        super().__init__(label, **kwargs)


class InputChip(Chip):
    """Chip used for chosen user input, optionally deletable."""

    def __init__(self, label: str = "", **kwargs):
        kwargs.setdefault("variant", "input")
        super().__init__(label, **kwargs)


class SuggestionChip(Chip):
    """Suggestion chip preset."""

    def __init__(self, label: str = "", **kwargs):
        kwargs.setdefault("variant", "suggestion")
        super().__init__(label, **kwargs)


class Badge(Widget):
    """A small count/dot overlaid on the top-right of its child."""

    _widget_type = "Badge"

    def __init__(
        self,
        label: Optional[Union[str, int]] = None,
        *,
        child: Optional[Widget] = None,
        color: str = Colors.ERROR,
        text_color: str = Colors.WHITE,
        max_count: int = 99,
        show: bool = True,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if isinstance(label, (int, float)):
            count = int(label)
            self.label = f"{max_count}+" if count > max_count else str(count)
            self.show = show and count > 0
        else:
            self.label = str(label) if label is not None else ""
            self.show = show
        self.color = color
        self.text_color = text_color
        if child is not None:
            self.children = [child]

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "label": self.label,
            "color": self.color,
            "textColor": self.text_color,
            "show": self.show,
        })
        return props


class Avatar(Widget):
    """A circular user image, icon or initials bubble."""

    _widget_type = "Avatar"

    def __init__(
        self,
        source: Optional[str] = None,
        *,
        initials: Optional[str] = None,
        icon: Optional[str] = None,
        size: float = 40,
        bg: str = Colors.PRIMARY,
        color: str = Colors.WHITE,
        on_click: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_click=on_click, **kwargs)
        self.source = source
        self.initials = (initials or "")[:2].upper()
        self.icon = icon
        self.size = float(size)
        self.bg = bg
        self.color = color

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "source": self.source,
            "initials": self.initials or None,
            "icon": self.icon,
            "size": self.size,
            "bg": self.bg,
            "color": self.color,
        }))
        return props


class Banner(Widget):
    """A prominent, dismissible message at the top of the content area."""

    _widget_type = "Banner"

    SEVERITIES = {"info": Colors.INFO, "success": Colors.SUCCESS,
                  "warning": Colors.WARNING, "error": Colors.ERROR}

    def __init__(
        self,
        message: str = "",
        *,
        severity: str = "info",
        icon: Optional[str] = None,
        action: Optional[str] = None,
        dismissible: bool = True,
        on_action: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if severity not in self.SEVERITIES:
            raise ValueError(
                f"Banner severity must be one of {sorted(self.SEVERITIES)}")
        self.message = str(message)
        self.severity = severity
        self.icon = icon
        self.action = action
        self.dismissible = dismissible
        if on_action is not None:
            self.event_handlers["click"] = on_action
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    @property
    def color(self) -> str:
        return self.SEVERITIES[self.severity]

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "message": self.message,
            "severity": self.severity,
            "color": self.color,
            "icon": self.icon,
            "action": self.action,
            "dismissible": self.dismissible,
        }))
        return props


class Tooltip(Widget):
    """Wraps a child with a long-press tooltip (native Android tooltip)."""

    _widget_type = "Tooltip"

    def __init__(self, message: str = "", *, child: Optional[Widget] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(key=key, **kwargs)
        self.message = str(message)
        if child is not None:
            self.children = [child]

    def _serialise_props(self) -> dict:
        return {**self._extra, "message": self.message}
