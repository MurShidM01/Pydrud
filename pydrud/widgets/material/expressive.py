"""
M3 Expressive components — button groups, split buttons, loading indicators.
"""

from __future__ import annotations

from typing import Callable, Optional
from pydrud.widgets.base import Widget
from pydrud.widgets.material._common import _clean


class ButtonGroup(Widget):
    """A Material 3 button group — organizes related buttons.

    Buttons in a group bump and react to each other with expressive
    shape and motion.

    ::

        ButtonGroup(
            buttons=[
                Button("Day"), Button("Week"), Button("Month"),
            ],
            selected=0,
            on_change=lambda e: switch_view(e.data["index"]),
        )
    """

    _widget_type = "ButtonGroup"

    def __init__(
        self,
        *,
        buttons: Optional[list[Widget]] = None,
        selected: int = 0,
        on_change: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.buttons = list(buttons or [])
        self.selected = max(0, min(int(selected), max(0, len(self.buttons) - 1)))
        for i, btn in enumerate(self.buttons):
            if isinstance(btn, Widget) and btn._auto_key:
                btn.key = f"{self.key}_btn{i}"
                btn._auto_key = False
        self.children = list(self.buttons)
        if on_change is not None:
            self.event_handlers["change"] = on_change

    def _serialise_props(self) -> dict:
        return {"selected": self.selected}


class SplitButton(Widget):
    """A Material 3 split button — a button paired with a related menu.

    The primary action is on the left; tapping the arrow opens a menu
    with additional related actions.

    ::

        SplitButton(
            label="Send",
            icon="send",
            menu_items=[
                MenuItem("Send now"),
                MenuItem("Schedule"),
                MenuItem("Save draft"),
            ],
            on_click=lambda e: send_now(),
            on_select=lambda e: handle(e.data["value"]),
        )
    """

    _widget_type = "SplitButton"

    def __init__(
        self,
        *,
        label: str = "",
        icon: Optional[str] = None,
        variant: str = "filled",
        menu_items: Optional[list] = None,
        on_click: Optional[Callable] = None,
        on_select: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_click=on_click, **kwargs)
        self.label = str(label)
        self.icon = icon
        self.variant = variant
        self.menu_items = list(menu_items or [])
        if on_select is not None:
            self.event_handlers["select"] = on_select

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "label": self.label,
            "icon": self.icon,
            "variant": self.variant,
            "menuItems": [
                m.to_dict() if hasattr(m, "to_dict") else {"label": str(m)}
                for m in self.menu_items
            ] or None,
        }))
        return props


class LoadingIndicator(Widget):
    """A Material 3 loading indicator — the new M3 Expressive component.

    An eye-catching way to show the status of a process with customizable
    waveform and thickness.

    ::

        LoadingIndicator()
        LoadingIndicator(
            progress=0.65,
            waveform="sine",
            thickness=4,
            color=Colors.PRIMARY,
        )
    """

    _widget_type = "LoadingIndicator"

    WAVEFORMS = ("linear", "sine", "saw", "spring")

    def __init__(
        self,
        *,
        progress: Optional[float] = None,
        waveform: str = "linear",
        thickness: float = 4,
        color: Optional[str] = None,
        size: float = 48,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.progress = None if progress is None else max(0.0, min(float(progress), 1.0))
        if waveform not in self.WAVEFORMS:
            raise ValueError(f"LoadingIndicator waveform must be one of {self.WAVEFORMS}")
        self.waveform = waveform
        self.thickness = float(thickness)
        self.color = color
        self.size = float(size)

    @property
    def indeterminate(self) -> bool:
        return self.progress is None

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "progress": self.progress,
            "waveform": self.waveform,
            "thickness": self.thickness,
            "color": self.color,
            "size": self.size,
            "indeterminate": self.indeterminate,
        }))
        return props


class Toolbar(Widget):
    """A Material 3 toolbar — flexible component for frequently used actions.

    Can be paired with a FAB. Supports overflow, selection, and context modes.

    ::

        Toolbar(
            title="Inbox",
            actions=[
                IconButton(Icons.SEARCH),
                IconButton(Icons.FILTER),
            ],
            navigation=IconButton(Icons.MENU),
        )
    """

    _widget_type = "Toolbar"

    def __init__(
        self,
        *,
        title: str = "",
        navigation: Optional[Widget] = None,
        actions: Optional[list[Widget]] = None,
        variant: str = "small",  # small, medium, large
        bg: Optional[str] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.title = str(title)
        self.navigation = navigation
        self.actions = list(actions or [])
        self.variant = variant
        self.bg = bg
        children = []
        if navigation is not None:
            if navigation._auto_key:
                navigation.key = f"{self.key}_nav"
                navigation._auto_key = False
            children.append(navigation)
        for i, action in enumerate(self.actions):
            if isinstance(action, Widget) and action._auto_key:
                action.key = f"{self.key}_action{i}"
                action._auto_key = False
            children.append(action)
        self.children = children

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "title": self.title,
            "variant": self.variant,
            "bg": self.bg,
        }))
        return props