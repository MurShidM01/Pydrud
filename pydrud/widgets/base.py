"""
Core widget base class for Pydrud.

Every UI element in Pydrud is a Widget. Widgets form a declarative tree
that gets serialized to JSON, sent to the Android runtime, and rendered
as native Android Views.
"""

from __future__ import annotations
import copy
import json
import uuid
from typing import Any, Callable, Optional


class Widget:
    """Base class for all Pydrud widgets.

    Each widget has:
    - A unique ``key`` for identity tracking during virtual-tree diffing.
    - An optional ``style`` dict for layout/visual properties.
    - A list of ``children`` (sub-widgets).
    - An ``event_handlers`` dict mapping event names to Python callbacks.
    """

    # Every subclass sets this to a PascalCase string like "Text", "Button".
    _widget_type: str = "Widget"

    def __init__(
        self,
        *,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        tooltip: Optional[str] = None,
        **kwargs,
    ):
        #: Unique identifier; auto-generated if omitted.
        self.key: str = key or _gen_key()
        #: Style dictionary (see pydrud.widgets.styling for helpers).
        self.style: dict = style or {}
        #: Flex / weight factor inside a Row or Column.
        self.expand: Optional[int] = expand
        #: Whether the widget is visible.
        self.visible: bool = visible
        #: Tooltip text (shown on long-press on Android).
        self.tooltip: Optional[str] = tooltip
        #: Child widgets (populated by subclasses for layout widgets).
        self.children: list["Widget"] = []
        #: Event callbacks: {"click": callable, "change": callable, ...}
        self.event_handlers: dict[str, Callable] = {}
        #: Catch-all extra properties passed by subclasses.
        self._extra: dict = kwargs

    # ── builder pattern helpers ──────────────────────────────────────────

    def on_click(self, callback: Callable) -> "Widget":
        """Register a click/tap handler. Returns self for chaining."""
        self.event_handlers["click"] = callback
        return self

    def on_change(self, callback: Callable) -> "Widget":
        """Register a change handler (TextField, Checkbox, Switch)."""
        self.event_handlers["change"] = callback
        return self

    def on_submit(self, callback: Callable) -> "Widget":
        """Register a submit handler (TextField)."""
        self.event_handlers["submit"] = callback
        return self

    def on_focus(self, callback: Callable) -> "Widget":
        """Register a focus-change handler."""
        self.event_handlers["focus"] = callback
        return self

    # ── serialisation ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Recursively serialise this widget and its children to a JSON-safe dict."""
        d: dict[str, Any] = {
            "type": self._widget_type,
            "key": self.key,
            "style": self.style,
            "expand": self.expand,
            "visible": self.visible,
            "tooltip": self.tooltip,
            "has_events": bool(self.event_handlers),
            "props": self._serialise_props(),
        }
        if self.children:
            d["children"] = [c.to_dict() for c in self.children if c.visible]
        return d

    def _serialise_props(self) -> dict:
        """Override in subclasses to add widget-specific properties."""
        return dict(self._extra)

    def to_json(self) -> str:
        """JSON string representation of the widget tree."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    # ── tree helpers ─────────────────────────────────────────────────────

    def find_by_key(self, key: str) -> Optional["Widget"]:
        """Walk the tree and return the first widget matching *key*."""
        if self.key == key:
            return self
        for child in self.children:
            result = child.find_by_key(key)
            if result is not None:
                return result
        return None

    def walk(self):
        """Depth-first generator yielding (widget, depth) tuples."""
        yield self, 0
        for child in self.children:
            yield from child.walk()

    def clone(self) -> "Widget":
        """Deep-copy this widget subtree."""
        return copy.deepcopy(self)

    def __repr__(self) -> str:
        return f"{self._widget_type}(key={self.key!r})"


def _gen_key() -> str:
    return uuid.uuid4().hex[:12]
