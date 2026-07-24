"""
Event dispatcher — routes UI events from the Android layer back to Python callbacks.

Events arrive as JSON messages from the Java bridge:

    {"type": "click", "key": "btn_abc123", "data": {}}
    {"type": "change", "key": "tf_xyz", "data": {"value": "hello"}}
    {"type": "submit", "key": "tf_xyz", "data": {"value": "hello"}}
    {"type": "focus", "key": "tf_xyz", "data": {"focused": true}}
"""

from __future__ import annotations
import json
from typing import Any, Optional

from pydrud.widgets.base import Widget


class EventDispatcher:
    """Maintains a mapping of widget keys → callbacks and dispatches events."""

    def __init__(self):
        self._handlers: dict[str, dict[str, Any]] = {}

    def register_tree(self, root: Widget):
        """Walk the widget tree and index all event handlers by key."""
        for widget, _ in root.walk():
            if widget.event_handlers:
                self._handlers[widget.key] = dict(widget.event_handlers)

    def unregister_key(self, key: str):
        self._handlers.pop(key, None)

    def unregister_all(self):
        self._handlers.clear()

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

        result = cb(data)
        return [result]

    def create_event_json(self, event_type: str, key: str, data: dict | None = None) -> str:
        """Create a JSON event string (used by the Java bridge to send events)."""
        payload = {"type": event_type, "key": key}
        if data:
            payload["data"] = data
        return json.dumps(payload)
