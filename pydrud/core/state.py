"""
Simple reactive state management for Pydrud.

Each ``State`` object wraps a value and notifies registered callbacks
when the value changes. An ``App`` instance maintains the root state
and re-renders the UI on change.
"""

from __future__ import annotations
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class State(Generic[T]):
    """A reactive value container.

    Usage::

        count = State(0)
        count.value += 1   # triggers watchers
    """

    def __init__(self, initial: T, *, name: str = ""):
        self._value: T = initial
        self._watchers: list[Callable[[T, T], None]] = []
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
        self._value = new_value
        for cb in self._watchers:
            cb(old, new_value)

    def watch(self, callback: Callable[[T, T], None]):
        """Register a watcher called as ``fn(old_value, new_value)``."""
        self._watchers.append(callback)

    def unwatch(self, callback: Callable[[T, T], None]):
        try:
            self._watchers.remove(callback)
        except ValueError:
            pass

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
        except KeyError:
            raise AttributeError(f"ReactiveDict has no key {name!r}")

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
