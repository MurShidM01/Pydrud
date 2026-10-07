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

from pydrud.core.errors import MaxDepthError

#: Event names a widget may subscribe to.
EVENT_NAMES = (
    "click",
    "long_press",
    "change",
    "submit",
    "focus",
    "scroll",
)

#: Maximum nesting depth of a widget tree.
#:
#: Every tree algorithm in Pydrud is iterative, so this is not a Python
#: stack limit — it is a guard for the *native* side, whose ``createView``,
#: ``indexParents`` and ``removeViewTree`` walk the tree recursively and
#: whose view hierarchy degrades long before this. Exceeding it raises
#: :class:`~pydrud.errors.MaxDepthError` with an actionable message instead
#: of a bare ``RecursionError``. Raise it (``pydrud.widgets.base.
#: MAX_TREE_DEPTH = …``) only if you know the device can take it.
MAX_TREE_DEPTH = 1000


def _serialise_value(value):
    """Convert style helpers and nested values into JSON-safe primitives."""
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _serialise_value(value.to_dict())
    if isinstance(value, dict):
        return {key: _serialise_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialise_value(item) for item in value]
    return value


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
        semantics: Optional[str] = None,
        on_click: Optional[Callable] = None,
        on_long_press: Optional[Callable] = None,
        class_: Optional[list[str]] = None,
        **kwargs,
    ):
        #: Whether ``key`` was auto-generated (eligible for key stabilisation).
        self._auto_key: bool = key is None
        #: Unique identifier; auto-generated if omitted.
        self.key: str = key or _gen_key()
        #: Inline style dictionary (see pydrud.widgets.styling for helpers).
        self.style: dict = dict(style) if style else {}
        #: CSS-like classes used by the Python-side stylesheet resolver only.
        #: They are deliberately separate from ``style`` and never go on wire.
        if isinstance(class_, str):
            self.class_ = [name for name in class_.split() if name]
        else:
            self.class_ = list(class_) if class_ else []
        if any(not isinstance(name, str) for name in self.class_):
            raise TypeError("class_ entries must be strings")
        #: PSS declarations are stored separately so inline style remains
        #: authoritative and stylesheet edits do not leave stale values.
        self._resolved_style: dict = {}
        #: Flex / weight factor inside a Row or Column.
        self.expand: Optional[int] = expand
        #: Whether the widget is visible.
        self.visible: bool = visible
        #: Tooltip text (shown on long-press on Android).
        self.tooltip: Optional[str] = tooltip
        #: Accessibility label, sent as Android's ``contentDescription``.
        #: Screen readers announce this instead of the raw text, so an
        #: icon-only button needs it to be reachable at all.
        self.semantics: Optional[str] = semantics
        #: Child widgets (populated by subclasses for layout widgets).
        self.children: list["Widget"] = []
        # ``children=`` works on every widget, not just the layouts that
        # name it. It used to fall through to ``_extra`` and be serialised
        # as a prop full of Widget objects — i.e. silently dropped.
        if "children" in kwargs:
            supplied = kwargs.pop("children") or []
            if isinstance(supplied, Widget):
                supplied = [supplied]
            for child in supplied:
                if not isinstance(child, Widget):
                    raise TypeError(
                        f"children= expects Widget instances, "
                        f"got {type(child).__name__}")
            self.children = list(supplied)
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
        """Merge extra inline style properties into this widget (chainable)."""
        self.style.update(props)
        return self

    def _effective_style(self) -> dict:
        """Return PSS declarations overlaid by inline widget styles.

        The PSS result is kept separately from ``style`` so an edited sheet
        can remove a declaration cleanly and inline values always win.
        """
        return {**self._resolved_style, **self.style}

    def _serialise_style(self):
        """Return the effective style without Python-only class markers."""
        style = {
            key: value
            for key, value in self._effective_style().items()
            if not (isinstance(key, str) and key.startswith("class_"))
        }
        return _serialise_value(style)

    # ── serialisation ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Recursively serialise this widget and its children to a JSON-safe dict."""
        root = self.unwrap()
        _merge_unwrapped_style(self, root)
        validate_tree_keys(root)
        return _serialise_tree(root)

    def _serialise_props(self) -> dict:
        """Override in subclasses to add widget-specific properties."""
        return dict(self._extra)

    def _freeze_props(self) -> dict:
        """Snapshot this widget's serialised props for the current build.

        The diff engine compares these frozen values (PB-004). Widgets whose
        serialisation is *dynamic* — a ``Canvas`` re-runs its ``on_draw``
        painter — would otherwise be re-serialised against the live state at
        diff time, so the old and new trees would look identical and the diff
        would emit zero patches (a silent freeze).
        """
        frozen = self._serialise_props()
        self.__dict__["_props_cache"] = frozen
        return frozen

    def _current_props(self) -> dict:
        """The props frozen for this build, or a fresh snapshot if unfrozen."""
        cached = self.__dict__.get("_props_cache")
        if cached is None:
            return self._freeze_props()
        return cached

    def _serialise_self(self) -> dict:
        """This node's own serialised fields (``children`` left empty).

        The iterative :func:`_serialise_tree` fills ``children`` afterwards.
        Override this — not :meth:`to_dict` — when a widget renders as a
        different native node (``FloatingActionButton`` serialises as a
        ``Container``), so the tree stays depth-safe.

        ``on_draw``-style painters still run on every serialisation (that is
        the documented contract), and the result becomes the build's frozen
        props so the diff compares like with like.
        """
        props = self._serialise_props()
        self.__dict__["_props_cache"] = props
        return {
            "type": self._widget_type,
            "key": self.key,
            "style": self._serialise_style(),
            "expand": self.expand,
            "visible": self.visible,
            "tooltip": self.tooltip,
            "semantics": self.semantics,
            "has_events": bool(self.event_handlers),
            "events": sorted(self.event_handlers.keys()),
            "props": _serialise_value(props),
            "children": [],
        }

    def to_json(self) -> str:
        """JSON string representation of the widget tree."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    # ── tree helpers ─────────────────────────────────────────────────────

    def find_by_key(self, key: str) -> Optional["Widget"]:
        """Walk the tree and return the first widget matching *key*."""
        stack: list["Widget"] = [self]
        while stack:
            widget = stack.pop()
            if widget.key == key:
                return widget
            # Reversed so children are visited left-to-right, matching the
            # pre-2.0.3 recursive order.
            stack.extend(reversed(widget.children))
        return None

    def walk(self):
        """Depth-first generator yielding (widget, depth) tuples."""
        stack: list[tuple["Widget", int]] = [(self, 0)]
        while stack:
            widget, depth = stack.pop()
            yield widget, depth
            for child in reversed(widget.children):
                stack.append((child, depth + 1))

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

        The copy is *iterative*: ``copy.deepcopy`` recursed once per tree
        level and blew the C stack around depth 200, which meant a moderately
        deep tree wedged rendering on every frame (2.0.2, PB-001). Only each
        node's own (shallow) attributes are deep-copied here; children are
        linked with an explicit stack.
        """
        memo: dict[int, Any] = {}
        root = self._copy_node(memo)
        stack: list[tuple["Widget", "Widget"]] = [(self, root)]
        while stack:
            source, target = stack.pop()
            for child in source.children:
                child_clone = child._copy_node(memo)
                target.children.append(child_clone)
                stack.append((child, child_clone))
        return root

    def _copy_node(self, memo: dict) -> "Widget":
        """Shallow-copy one widget, deep-copying its non-child attributes."""
        clone = object.__new__(type(self))
        for name, value in self.__dict__.items():
            if name == "children":
                clone.children = []
            elif name == "event_handlers":
                # Share callables; copy the mapping so mutations are local.
                clone.event_handlers = dict(value)
            else:
                clone.__dict__[name] = copy.deepcopy(value, memo)
        return clone

    def __repr__(self) -> str:
        return f"{self._widget_type}(key={self.key!r})"


def _merge_unwrapped_style(source: "Widget", rendered: "Widget") -> None:
    """Carry a composite widget's effective style to its rendered root.

    Composite wrappers may rebuild their implementation node inside
    ``unwrap()``. Applying the wrapper's resolved/inline styles here keeps PSS
    behavior intact without adding wrapper metadata to the wire tree.
    """
    if rendered is source:
        return
    inherited = {
        key: value
        for key, value in source._effective_style().items()
        if not (isinstance(key, str) and key.startswith("class_"))
    }
    if inherited:
        rendered.style = {**rendered.style, **inherited}


def _serialise_tree(root: "Widget") -> dict:
    """Serialise a widget tree without recursion (PB-001).

    Composite widgets (``AppBar``, ``Scaffold``, ``Visible`` …) render as an
    internal node; :meth:`Widget.unwrap` is resolved once per node and cached
    so a builder with side effects runs exactly once, and each node's own
    fields come from :meth:`Widget._serialise_self`. A pre-order pass
    collects the rendered nodes; the reversed pass builds each dict once its
    children already have one, giving the same output as the recursive
    ``to_dict`` with O(n) stack.

    *root* must already be unwrapped (``to_dict`` does that).
    """
    children_of: dict[int, list["Widget"]] = {}
    order: list[Widget] = []
    stack: list[Widget] = [root]
    while stack:
        widget = stack.pop()
        order.append(widget)
        kids: list[Widget] = []
        for child in widget.children:
            rendered = child.unwrap()
            _merge_unwrapped_style(child, rendered)
            kids.append(rendered)
            stack.append(rendered)
        children_of[id(widget)] = kids

    serialised: dict[int, dict] = {}
    for widget in reversed(order):
        d = widget._serialise_self()
        kids = children_of[id(widget)]
        if kids:
            # Hidden children are serialised too (the renderer gives them
            # View.GONE). Dropping them here would make the native child
            # indices disagree with the diff's indices, so a later
            # create/move patch would land in the wrong position.
            d["children"] = [serialised[id(c)] for c in kids]
        else:
            d.pop("children", None)
        serialised[id(widget)] = d
    return serialised[id(root)]


def assign_stable_keys(root: "Widget", prefix: str = "r") -> "Widget":
    """Rewrite auto-generated keys into deterministic, structural keys.

    Widgets created with an explicit ``key=`` keep it. Everything else gets
    ``<parent>.<index><Type>`` so the same widget in the same position across
    two rebuilds compares equal and the diff engine can emit a small
    ``update`` patch instead of re-creating the whole subtree.
    """
    if root._auto_key:
        root.key = prefix
    stack: list[Widget] = [root]
    while stack:
        widget = stack.pop()
        for index, child in enumerate(widget.children):
            if child._auto_key:
                child.key = f"{widget.key}.{index}{child._widget_type}"
            stack.append(child)
    return root


def _gen_key() -> str:
    return uuid.uuid4().hex[:12]


def validate_tree_keys(root: "Widget") -> None:
    """Validate that every widget key is unique and non-empty.

    Duplicate keys make keyed reconciliation mathematically ambiguous and can
    otherwise collapse entries in the diff engine's dictionaries.

    Iterative (PB-001): the old recursive walk raised ``RecursionError`` on a
    deep tree; now an over-deep tree raises :class:`MaxDepthError` with the
    offending widget named, and duplicate keys are still reported with both
    paths (in the same left-to-right order as before).
    """
    seen: dict[str, tuple[str, ...]] = {}
    stack: list[tuple["Widget", tuple[str, ...], int]] = [
        (root, (root._widget_type,), 0)
    ]
    while stack:
        widget, path, depth = stack.pop()
        if depth > MAX_TREE_DEPTH:
            raise MaxDepthError(
                f"Pydrud widget tree exceeds the maximum depth of "
                f"{MAX_TREE_DEPTH} at {widget._widget_type}"
                f"(key={widget.key!r}). Flatten the tree, or raise "
                "pydrud.widgets.base.MAX_TREE_DEPTH if the device can take it."
            )
        key = str(widget.key or "")
        if not key:
            raise ValueError("Pydrud widget keys must be non-empty")
        if key in seen:
            previous = " > ".join(seen[key]) or "<root>"
            current = " > ".join(path) or "<root>"
            raise ValueError(
                f"Duplicate Pydrud widget key {key!r}: "
                f"{previous} and {current}"
            )
        seen[key] = path
        # Push in reverse so children are visited left-to-right.
        for index in range(len(widget.children) - 1, -1, -1):
            child = widget.children[index]
            stack.append((child, path + (f"{widget._widget_type}[{index}]",),
                          depth + 1))
