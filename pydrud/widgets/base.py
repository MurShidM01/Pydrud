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

#: Event names a widget may subscribe to.
EVENT_NAMES = (
    "click",
    "long_press",
    "change",
    "submit",
    "focus",
    "scroll",
)


class Widget:
    """Base class for all Pydrud widgets.

    Each widget has:
    - A unique ``key`` for identity tracking during virtual-tree diffing.
    - An optional ``style`` dict for layout/visual properties.
    - A list of ``children`` (sub-widgets).
    - An ``event_handlers`` dict mapping event names to Python callbacks.

    Keys
    ----
    If no ``key`` is given, a random one is generated so the widget is always
    addressable. Before a tree is serialised, :func:`assign_stable_keys`
    rewrites every *auto-generated* key into a deterministic, position-based
    key (``p0.c2.Text``). This is what makes incremental diffing work across
    rebuilds — without it, every rebuild produces brand-new keys and the whole
    UI has to be re-created on every ``page.update()``.
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
        on_click: Optional[Callable] = None,
        on_long_press: Optional[Callable] = None,
        **kwargs,
    ):
        #: Whether ``key`` was auto-generated (eligible for key stabilisation).
        self._auto_key: bool = key is None
        #: Unique identifier; auto-generated if omitted.
        self.key: str = key or _gen_key()
        #: Style dictionary (see pydrud.widgets.styling for helpers).
        self.style: dict = dict(style) if style else {}
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
        # Any ``on_<event>=callable`` keyword works on every widget, even
        # when the subclass does not name it explicitly. Without this a typo
        # like ``TextField(on_change=cb)`` on a widget that forgot to declare
        # the parameter would silently serialise a function into `props`.
        for name in [k for k in kwargs if k.startswith("on_")]:
            handler = kwargs.pop(name)
            if handler is None:
                continue
            if not callable(handler):
                raise TypeError(
                    f"{name}= must be callable, got {type(handler).__name__}")
            self.event_handlers[name[3:]] = handler

        #: Catch-all extra properties passed by subclasses.
        self._extra: dict = kwargs

        if on_click is not None:
            self.event_handlers["click"] = on_click
        if on_long_press is not None:
            self.event_handlers["long_press"] = on_long_press

    # ── builder pattern helpers ──────────────────────────────────────────

    def on_click(self, callback: Callable) -> "Widget":
        """Register a click/tap handler. Returns self for chaining."""
        self.event_handlers["click"] = callback
        return self

    def on_long_press(self, callback: Callable) -> "Widget":
        """Register a long-press handler. Returns self for chaining."""
        self.event_handlers["long_press"] = callback
        return self

    def on_change(self, callback: Callable) -> "Widget":
        """Register a change handler (TextField, Checkbox, Switch, Slider)."""
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

    def on(self, event: str, callback: Callable) -> "Widget":
        """Register an arbitrary event handler by name."""
        self.event_handlers[event] = callback
        return self

    # ── style helpers ────────────────────────────────────────────────────

    def with_style(self, **props) -> "Widget":
        """Merge extra style properties into this widget (chainable)."""
        self.style.update(props)
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
            "events": sorted(self.event_handlers.keys()),
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
        yield from _walk(self, 0)

    def unwrap(self) -> "Widget":
        """Return the widget that is actually serialised.

        Composite widgets (AppBar, Scaffold) build an internal layout and
        delegate ``to_dict`` to it. The diff engine calls ``unwrap()`` so it
        compares the *rendered* nodes, keeping patch keys aligned with the
        views that exist on the Android side.
        """
        return self

    def clone(self) -> "Widget":
        """Deep-copy this widget subtree.

        Event handlers are shared (not deep-copied) because callables —
        especially bound methods and closures over sockets — are not always
        copyable.  The clone is only used for diffing, where handler identity
        does not matter.
        """
        memo: dict[int, Any] = {}
        handlers: list[tuple[Widget, dict]] = []
        for w, _ in self.walk():
            handlers.append((w, w.event_handlers))
            memo[id(w.event_handlers)] = dict(w.event_handlers)
        return copy.deepcopy(self, memo)

    def __repr__(self) -> str:
        return f"{self._widget_type}(key={self.key!r})"


def _walk(widget: "Widget", depth: int):
    yield widget, depth
    for child in widget.children:
        yield from _walk(child, depth + 1)


def assign_stable_keys(root: "Widget", prefix: str = "r") -> "Widget":
    """Rewrite auto-generated keys into deterministic, structural keys.

    Widgets created with an explicit ``key=`` keep it. Everything else gets
    ``<parent>.<index><Type>`` so the same widget in the same position across
    two rebuilds compares equal and the diff engine can emit a small
    ``update`` patch instead of re-creating the whole subtree.
    """
    if root._auto_key:
        root.key = prefix
    _stabilise_children(root)
    return root


def _stabilise_children(widget: "Widget") -> None:
    for index, child in enumerate(widget.children):
        if child._auto_key:
            child.key = f"{widget.key}.{index}{child._widget_type}"
        _stabilise_children(child)


def _gen_key() -> str:
    return uuid.uuid4().hex[:12]
