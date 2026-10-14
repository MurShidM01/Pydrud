"""
Date and time pickers — Material 3 selection components.

Provides declarative DatePicker, DateRangePicker, and TimePicker widgets.
"""

from __future__ import annotations

from typing import Callable, Optional
from pydrud.widgets.base import Widget
from pydrud.widgets.material._common import _clean


class DatePicker(Widget):
    """A Material 3 date picker.

    Supports calendar and input modes, date constraints, and selection.

    ::

        DatePicker(
            selected="2026-01-15",
            first_date="2020-01-01",
            last_date="2030-12-31",
            on_change=lambda e: print(e.data["date"]),
        )
    """

    _widget_type = "DatePicker"

    MODES = ("calendar", "input")

    def __init__(
        self,
        *,
        selected: Optional[str] = None,
        first_date: Optional[str] = None,
        last_date: Optional[str] = None,
        mode: str = "calendar",
        on_change: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.selected = selected
        self.first_date = first_date
        self.last_date = last_date
        if mode not in self.MODES:
            raise ValueError(f"DatePicker mode must be one of {self.MODES}")
        self.mode = mode
        if on_change is not None:
            self.event_handlers["change"] = on_change
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "selected": self.selected,
            "firstDate": self.first_date,
            "lastDate": self.last_date,
            "mode": self.mode,
        }))
        return props


class DateRangePicker(Widget):
    """A Material 3 date range picker.

    ::

        DateRangePicker(
            start_date="2026-01-01",
            end_date="2026-01-31",
            on_change=lambda e: print(e.data["start"], e.data["end"]),
        )
    """

    _widget_type = "DateRangePicker"

    def __init__(
        self,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        first_date: Optional[str] = None,
        last_date: Optional[str] = None,
        on_change: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.start_date = start_date
        self.end_date = end_date
        self.first_date = first_date
        self.last_date = last_date
        if on_change is not None:
            self.event_handlers["change"] = on_change
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "startDate": self.start_date,
            "endDate": self.end_date,
            "firstDate": self.first_date,
            "lastDate": self.last_date,
        }))
        return props


class TimePicker(Widget):
    """A Material 3 time picker.

    Supports dial and input modes.

    ::

        TimePicker(
            hour=14, minute=30,
            mode="dial",
            on_change=lambda e: print(e.data["hour"], e.data["minute"]),
        )
    """

    _widget_type = "TimePicker"

    MODES = ("dial", "input")

    def __init__(
        self,
        *,
        hour: int = 0,
        minute: int = 0,
        mode: str = "dial",
        is_24hour: bool = False,
        on_change: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.hour = max(0, min(23, int(hour)))
        self.minute = max(0, min(59, int(minute)))
        if mode not in self.MODES:
            raise ValueError(f"TimePicker mode must be one of {self.MODES}")
        self.mode = mode
        self.is_24hour = bool(is_24hour)
        if on_change is not None:
            self.event_handlers["change"] = on_change
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "hour": self.hour,
            "minute": self.minute,
            "mode": self.mode,
            "is24hour": self.is_24hour or None,
        }))
        return props