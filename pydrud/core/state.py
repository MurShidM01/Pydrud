"""
Simple reactive state management for Pydrud.

Each ``State`` object wraps a value and notifies registered callbacks
when the value changes. An ``App`` instance maintains the root state
and re-renders the UI on change.
"""

from __future__ import annotations
from typing import Any, Callable, Generic, Optional, TypeVar

from pydrud.core.subscriptions import Subscription

T = TypeVar("T")

#: Marker for "no value supplied" where ``None`` is a legitimate value.
UNSET: Any = object()


def read_reactive(value: Any, *, default: Any = None, _depth: int = 0) -> Any:
    """Read a plain value, a reactive container or a zero-arg callable.

    Conditional widgets accept whatever the app has to hand — a bool, a
    :class:`State`, a ``Computed``, a ``Selector``, a ``ReactiveList`` or
    a lambda — so the rules live here once. Resolution repeats to a small
    depth, so a callable may return a reactive container.
    """
    if value is UNSET:
        return default
    if _depth >= 5:
        return value
    if callable(value) and not hasattr(value, "to_dict"):
        try:
            resolved = value()
        except TypeError:
            return value
        return read_reactive(resolved, default=default, _depth=_depth + 1)
    if hasattr(type(value), "value") and not isinstance(
            value, (str, bytes, int, float, bool)):
        return read_reactive(value.value, default=default, _depth=_depth + 1)
    return value


def is_truthy(value: Any, *, default: bool = True) -> bool:
    """``read_reactive`` plus a ``bool()``, with an empty-value default."""
    resolved = read_reactive(value, default=default)
    return bool(default if resolved is UNSET else resolved)


class State(Generic[T]):
    """A reactive value container.

    Usage::

        count = State(0)
        count.value += 1   # triggers watchers
    """

    def __init__(self, initial: T, *, name: str = "", distinct: bool = False):
        self._value: T = initial
        self._watchers: list[tuple[Callable[[T, T], None], Optional[Callable]]] = []
        self.distinct = bool(distinct)
        #: Optional label. Naming a State lets stateful hot reload match it
        #: to its replacement after a module is reloaded, even if the order
        #: of declarations in the file changed.
        self.name: str = name

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, new_value: T):
        old = self._value
        if self.distinct and old == new_value:
            return
        self._value = new_value
        for cb, scheduler in list(self._watchers):
            if scheduler is None:
                cb(old, new_value)
            else:
                scheduler(lambda cb=cb, old=old, new_value=new_value: cb(old, new_value))

    def watch(
        self,
        callback: Callable[[T, T], None],
        *,
        scheduler: Optional[Callable[[Callable], None]] = None,
    ) -> Subscription:
        """Register a watcher and return an explicit lifetime handle."""
        entry = (callback, scheduler)
        self._watchers.append(entry)

        def _unsubscribe() -> None:
            try:
                self._watchers.remove(entry)
            except ValueError:
                pass

        return Subscription(_unsubscribe)

    def unwatch(self, callback: Callable[[T, T], None]):
        self._watchers[:] = [entry for entry in self._watchers if entry[0] is not callback]

    def __repr__(self) -> str:
        if self.name:
            return f"State({self._value!r}, name={self.name!r})"
        return f"State({self._value!r})"


class ReactiveDict:
    """A dict whose ``changed`` State toggles whenever keys are set.

    Useful as a lightweight page-level state store::

        store = ReactiveDict({"count": 0, "name": "World"})
        store.count = 5            # triggers store.changed
        store["name"] = "Pydrud"   # also works
    """

    def __init__(self, initial: dict[str, Any] | None = None):
        self._data: dict[str, Any] = {}
        self.changed = State(0)  # increment counter
        if initial:
            for k, v in initial.items():
                self._data[k] = v

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        try:
            return self._data[name]
        except KeyError as exc:
            raise AttributeError(
                f"ReactiveDict has no key {name!r}") from exc

    def __setattr__(self, name: str, value: Any):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value
            self.changed.value += 1

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any):
        self._data[key] = value
        self.changed.value += 1

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"ReactiveDict({self._data})"
