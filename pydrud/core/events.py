"""
Event dispatcher — routes UI events from the Android layer back to Python callbacks.

Events arrive as JSON messages from the Java bridge:

    {"type": "click", "key": "btn_abc123", "data": {}}
    {"type": "change", "key": "tf_xyz", "data": {"value": "hello"}}
    {"type": "submit", "key": "tf_xyz", "data": {"value": "hello"}}
    {"type": "focus", "key": "tf_xyz", "data": {"focused": true}}
"""

from __future__ import annotations
import inspect
import json
from typing import Any, Callable, Optional

from pydrud.widgets.base import Widget


class Event(dict):
    """The object handed to every event callback.

    It *is* the event's ``data`` dict — ``event["value"]`` keeps working —
    but it also carries the context a real handler usually needs::

        def on_change(e):
            print(e.type, e.key, e.value, e.data)

    Keeping it a dict subclass means handlers written against earlier
    versions of Pydrud continue to work unchanged.
    """

    __slots__ = ("type", "key", "data", "control")

    def __init__(self, type: str = "", key: str = "", data: Optional[dict] = None,
                 control: Any = None):
        super().__init__(data or {})
        self.type = type
        self.key = key
        self.data = dict(data or {})
        self.control = control

    @property
    def value(self) -> Any:
        """The new value for change/submit events (None for taps)."""
        for name in ("value", "checked", "selected", "index"):
            if name in self.data:
                return self.data[name]
        return None

    def __repr__(self) -> str:
        return f"<Event {self.type} key={self.key!r} data={self.data!r}>"


class EventDispatcher:
    """Maintains a mapping of widget keys → callbacks and dispatches events.

    ``schedule_awaitable`` lets the owning :class:`App` run ``async def``
    callbacks on its coroutine runner instead of silently dropping the
    coroutine object (the default Python behaviour when an async callback is
    called like a normal function).
    """

    def __init__(self, schedule_awaitable: Optional[Callable[[Any], None]] = None):
        self._handlers: dict[str, dict[str, Any]] = {}
        self._controls: dict[str, Widget] = {}
        self._schedule_awaitable = schedule_awaitable

    def register_tree(self, root: Widget):
        """Walk the widget tree and index all event handlers by key."""
        for widget, _ in root.walk():
            if widget.event_handlers:
                self._handlers[widget.key] = dict(widget.event_handlers)
                self._controls[widget.key] = widget

    def unregister_key(self, key: str):
        self._handlers.pop(key, None)
        self._controls.pop(key, None)

    def unregister_all(self):
        self._handlers.clear()
        self._controls.clear()

    def dispatch(self, message: str) -> list[Any]:
        """Parse a JSON event message and invoke the matching handler.

        Returns a list of return values from the handlers (for testing/telemetry).
        """
        try:
            event = json.loads(message)
        except json.JSONDecodeError:
            return []

        event_type = event.get("type", "")
        key = event.get("key", "")
        data = event.get("data", {})

        handlers = self._handlers.get(key, {})
        cb = handlers.get(event_type)

        if cb is None:
            # Fall back to a generic handler if present.
            cb = handlers.get("*")
        if cb is None:
            return []

        event_obj = Event(type=event_type, key=key, data=data,
                          control=self._controls.get(key))
        result = cb(event_obj)
        if inspect.isawaitable(result) and self._schedule_awaitable is not None:
            self._schedule_awaitable(result)
            # The coroutine is intentionally represented as scheduled rather
            # than returned: no caller may accidentally forget to await it.
            return []
        return [result]

    def create_event_json(self, event_type: str, key: str, data: dict | None = None) -> str:
        """Create a JSON event string (used by the Java bridge to send events)."""
        payload = {"type": event_type, "key": key}
        if data:
            payload["data"] = data
        return json.dumps(payload)
