"""
Application-level state management.

``State`` is perfect for a counter inside one screen.  Real apps also need
state that outlives a screen, is mutated from many places and is observed by
several widgets at once.  This module adds three pieces modelled on patterns
that proved themselves in Flutter (Provider/Riverpod) and React (Redux):

* :class:`Store` — a single source of truth with *actions* that produce a new
  state and *selectors* that subscribe to one slice, so a widget only
  re-renders when the slice it cares about actually changed;
* :class:`Computed` — a cached derived value that invalidates itself when any
  of its sources change;
* :class:`ReactiveList` — a list that notifies on structural changes, for the
  very common "list of items" screen.

All three expose ``subscribe()`` and are accepted by ``App.bind()``.
"""

from __future__ import annotations

import copy
import threading
from typing import Any, Callable, Generic, Iterable, Iterator, Optional, TypeVar

from pydrud.core.state import State
from pydrud.core.subscriptions import Subscription

T = TypeVar("T")
Unsubscribe = Callable[[], None]


class _Observable:
    """Mixin providing subscribe/notify plus a ``changed`` State for App.bind."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[..., Any]] = []
        self._notify_lock = threading.RLock()
        self._muted = 0
        self._dirty = False
        self.changed = State(0)

    def subscribe(self, callback: Callable[..., Any]) -> Subscription:
        """Register *callback* and return an idempotent lifetime handle."""
        with self._notify_lock:
            self._subscribers.append(callback)

        def _unsubscribe() -> None:
            with self._notify_lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return Subscription(_unsubscribe)

    def unsubscribe(self, callback: Callable[..., Any]) -> None:
        with self._notify_lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def _emit(self, *args) -> None:
        if self._muted:
            self._dirty = True
            return
        with self._notify_lock:
            subscribers = list(self._subscribers)
        for cb in subscribers:
            try:
                cb(*args)
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[Pydrud] store subscriber error: {exc}")
        self.changed.value += 1

    def batch(self) -> "_Batch":
        """Context manager coalescing many mutations into a single notify."""
        return _Batch(self)


class _Batch:
    def __init__(self, owner: _Observable):
        self._owner = owner

    def __enter__(self):
        self._owner._muted += 1
        return self._owner

    def __exit__(self, *exc):
        self._owner._muted -= 1
        if self._owner._muted == 0 and self._owner._dirty:
            self._owner._dirty = False
            self._owner._emit()
        return False


class Store(_Observable):
    """An observable, immutable-by-convention dictionary of app state.

    Example::

        store = Store({"todos": [], "filter": "all"})

        @store.action
        def add_todo(state, text):
            return {"todos": state["todos"] + [text]}

        store.select("todos").listen(lambda todos: print(len(todos)))
        add_todo("Buy milk")
    """

    def __init__(self, initial: Optional[dict] = None, *, name: str = "store"):
        super().__init__()
        self.name = name
        self._state: dict = dict(initial or {})
        self._history: list[dict] = []
        self._max_history = 50
        self._selectors: list["Selector"] = []
        self._middleware: list[Callable[[str, dict, dict], None]] = []

    # ── reading ──────────────────────────────────────────────────────────

    @property
    def state(self) -> dict:
        """A shallow copy — mutating it will not corrupt the store."""
        return dict(self._state)

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._state[key]

    def __contains__(self, key: str) -> bool:
        return key in self._state

    # ── writing ──────────────────────────────────────────────────────────

    def set(self, key: str, value: Any) -> "Store":
        """Set a single key (no-op when the value is unchanged)."""
        return self.update({key: value})

    def __setitem__(self, key: str, value: Any) -> None:
        self.update({key: value})

    def update(self, changes: dict, *, action: str = "update") -> "Store":
        """Merge *changes* into the state and notify what really changed."""
        if not isinstance(changes, dict):
            raise TypeError("Store.update() expects a dict of changes")
        diff = {k: v for k, v in changes.items()
                if k not in self._state or self._state[k] != v}
        if not diff:
            return self
        previous = dict(self._state)
        self._push_history(previous)
        self._state.update(diff)
        for hook in self._middleware:
            try:
                hook(action, previous, dict(self._state))
            except Exception as exc:  # pragma: no cover
                print(f"[Pydrud] middleware error: {exc}")
        self._notify_selectors(previous)
        self._emit(dict(self._state), set(diff))
        return self

    def replace(self, state: dict, *, action: str = "replace") -> "Store":
        """Swap the whole state for *state*, notifying every changed key.

        Used by stateful hot reload to push a pre-reload snapshot back into
        a freshly constructed store, including keys that were removed.
        """
        if not isinstance(state, dict):
            raise TypeError("Store.replace() expects a dict")
        previous = dict(self._state)
        changed = {k for k in set(previous) | set(state)
                   if previous.get(k) != state.get(k)}
        if not changed:
            return self
        self._push_history(previous)
        self._state = dict(state)
        for hook in self._middleware:
            try:
                hook(action, previous, dict(self._state))
            except Exception as exc:  # pragma: no cover
                print(f"[Pydrud] middleware error: {exc}")
        self._notify_selectors(previous)
        self._emit(dict(self._state), changed)
        return self

    def mutate(self, fn: Callable[[dict], Optional[dict]], *,
               action: str = "mutate") -> "Store":
        """Mutate via a function receiving a *copy* of the state.

        Return a dict of changes, or mutate the copy in place and return None.
        """
        draft = copy.deepcopy(self._state)
        returned = fn(draft)
        changes = returned if isinstance(returned, dict) else draft
        return self.update(changes, action=action)

    def action(self, fn: Callable) -> Callable:
        """Decorator turning ``fn(state, *args)`` into a dispatchable action."""

        def wrapper(*args, **kwargs):
            changes = fn(self.state, *args, **kwargs)
            if isinstance(changes, dict):
                self.update(changes, action=getattr(fn, "__name__", "action"))
            return changes

        wrapper.__name__ = getattr(fn, "__name__", "action")
        wrapper.__doc__ = fn.__doc__
        return wrapper

    def use(self, middleware: Callable[[str, dict, dict], None]) -> "Store":
        """Add a logger/persistence hook called as ``(action, old, new)``."""
        self._middleware.append(middleware)
        return self

    # ── selectors ────────────────────────────────────────────────────────

    def select(self, key_or_fn) -> "Selector":
        """Observe one slice of the state.

        Accepts a key name or a ``fn(state)`` projection.
        """
        selector = Selector(self, key_or_fn)
        self._selectors.append(selector)
        return selector

    def _notify_selectors(self, previous: dict) -> None:
        for selector in list(self._selectors):
            selector._check(previous, self._state)

    # ── time travel (debugging) ──────────────────────────────────────────

    def _push_history(self, snapshot: dict) -> None:
        self._history.append(snapshot)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    def undo(self) -> bool:
        """Restore the previous state. Returns False if there is none."""
        if not self._history:
            return False
        previous = self._history.pop()
        old = dict(self._state)
        self._state = previous
        self._notify_selectors(old)
        self._emit(dict(self._state), set(old) | set(previous))
        return True

    def reset(self, state: Optional[dict] = None) -> "Store":
        old = dict(self._state)
        self._state = dict(state or {})
        self._history.clear()
        self._notify_selectors(old)
        self._emit(dict(self._state), set(old) | set(self._state))
        return self

    def __repr__(self) -> str:
        return f"Store({self.name!r}, keys={sorted(self._state)})"


class Selector:
    """A subscription to one slice of a :class:`Store`."""

    def __init__(self, store: Store, key_or_fn):
        self._store = store
        if callable(key_or_fn):
            self._project = key_or_fn
            self.key = getattr(key_or_fn, "__name__", "<fn>")
        else:
            self.key = key_or_fn
            self._project = lambda state: state.get(key_or_fn)
        self._listeners: list[Callable[[Any], Any]] = []

    @property
    def value(self) -> Any:
        return self._project(self._store.state)

    def listen(self, callback: Callable[[Any], Any], *,
               immediate: bool = False) -> Subscription:
        self._listeners.append(callback)
        if immediate:
            callback(self.value)

        def _unsubscribe() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return Subscription(_unsubscribe)

    def _check(self, previous: dict, current: dict) -> None:
        try:
            before = self._project(previous)
            after = self._project(current)
        except Exception:  # pragma: no cover - projection over partial state
            return
        if before == after:
            return
        for cb in list(self._listeners):
            try:
                cb(after)
            except Exception as exc:  # pragma: no cover
                print(f"[Pydrud] selector listener error: {exc}")

    def __repr__(self) -> str:
        return f"<Selector {self.key!r}={self.value!r}>"


class Computed(Generic[T]):
    """A lazily-evaluated, cached derived value.

    ``Computed(lambda: a.value * b.value, sources=[a, b])`` recomputes only
    after one of its sources changed, so expensive derivations (filtering a
    long list, formatting currency) do not run on every render.
    """

    def __init__(self, fn: Callable[[], T], sources: Iterable[Any] = ()):
        self._fn = fn
        self._cache: Any = None
        self._valid = False
        self._subscribers: list[Callable[[T], Any]] = []
        self._sources = list(sources)
        for source in self._sources:
            self._bind(source)

    def _bind(self, source: Any) -> None:
        if isinstance(source, State):
            source.watch(lambda *_: self.invalidate())
        elif hasattr(source, "subscribe"):
            source.subscribe(lambda *_: self.invalidate())

    @property
    def value(self) -> T:
        if not self._valid:
            self._cache = self._fn()
            self._valid = True
        return self._cache  # type: ignore[return-value]

    @property
    def stale(self) -> bool:
        return not self._valid

    def invalidate(self) -> None:
        was = self._cache
        self._valid = False
        new = self.value
        if new != was:
            for cb in list(self._subscribers):
                try:
                    cb(new)
                except Exception as exc:  # pragma: no cover
                    print(f"[Pydrud] computed subscriber error: {exc}")

    def subscribe(self, callback: Callable[[T], Any]) -> Subscription:
        self._subscribers.append(callback)

        def _unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return Subscription(_unsubscribe)

    def __repr__(self) -> str:
        return f"Computed({self.value!r})"


class ReactiveList(_Observable, Generic[T]):
    """A list that notifies subscribers on every structural change."""

    def __init__(self, initial: Optional[Iterable[T]] = None):
        super().__init__()
        self._items: list[T] = list(initial or [])

    # ── list protocol ────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        return iter(list(self._items))

    def __getitem__(self, index):
        return self._items[index]

    def __setitem__(self, index, value) -> None:
        self._items[index] = value
        self._emit(self.value)

    def __contains__(self, item) -> bool:
        return item in self._items

    def __repr__(self) -> str:
        return f"ReactiveList({self._items!r})"

    @property
    def value(self) -> list[T]:
        return list(self._items)

    # ── mutations ────────────────────────────────────────────────────────

    def append(self, item: T) -> "ReactiveList[T]":
        self._items.append(item)
        self._emit(self.value)
        return self

    def extend(self, items: Iterable[T]) -> "ReactiveList[T]":
        added = list(items)
        if added:
            self._items.extend(added)
            self._emit(self.value)
        return self

    def insert(self, index: int, item: T) -> "ReactiveList[T]":
        self._items.insert(index, item)
        self._emit(self.value)
        return self

    def remove(self, item: T) -> bool:
        try:
            self._items.remove(item)
        except ValueError:
            return False
        self._emit(self.value)
        return True

    def pop(self, index: int = -1) -> T:
        item = self._items.pop(index)
        self._emit(self.value)
        return item

    def clear(self) -> "ReactiveList[T]":
        if self._items:
            self._items.clear()
            self._emit(self.value)
        return self

    def replace_all(self, items: Iterable[T]) -> "ReactiveList[T]":
        self._items = list(items)
        self._emit(self.value)
        return self

    def sort(self, *, key=None, reverse: bool = False) -> "ReactiveList[T]":
        self._items.sort(key=key, reverse=reverse)
        self._emit(self.value)
        return self

    def move(self, old_index: int, new_index: int) -> "ReactiveList[T]":
        """Reorder an item (drag-and-drop lists)."""
        item = self._items.pop(old_index)
        self._items.insert(new_index, item)
        self._emit(self.value)
        return self

    # ── queries ──────────────────────────────────────────────────────────

    def where(self, predicate: Callable[[T], bool]) -> list[T]:
        return [i for i in self._items if predicate(i)]

    def first(self, predicate: Callable[[T], bool], default: Any = None):
        for item in self._items:
            if predicate(item):
                return item
        return default

    def index_where(self, predicate: Callable[[T], bool]) -> int:
        for index, item in enumerate(self._items):
            if predicate(item):
                return index
        return -1
