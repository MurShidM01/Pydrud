"""Persistent logical UI elements.

An Element is the runtime identity between a declarative Python Widget and the
native view which materializes it. Elements survive widget rebuilds
when identity is preserved, allowing native state to remain intact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class Element:
    """Persistent runtime identity for one widget node."""

    key: str
    widget_type: str
    parent_key: Optional[str] = None
    index: int = 0
    native_ref: Any = None
    desired_props: dict[str, Any] = field(default_factory=dict)
    confirmed_props: dict[str, Any] = field(default_factory=dict)
    children: list[str] = field(default_factory=list)
    listeners: set[str] = field(default_factory=set)
    resource_scope: Any = None
    confirmed_revision: int = 0
    source: Optional[str] = None
    state_policy: str = "preserve"

    @property
    def is_mounted(self) -> bool:
        return self.native_ref is not None

    def update_desired(self, props: dict[str, Any]) -> None:
        self.desired_props = dict(props)

    def confirm(self, props: Optional[dict[str, Any]], revision: int) -> None:
        if props is not None:
            self.confirmed_props.update(props)
        self.confirmed_revision = max(self.confirmed_revision, int(revision))


class ElementTree:
    """Persistent keyed element registry.

    The tree is deliberately independent from any renderer transport so tests
    can validate identity/reuse without requiring a device.
    """

    def __init__(self):
        self._elements: dict[str, Element] = {}
        self.revision = 0

    def get(self, key: str) -> Optional[Element]:
        return self._elements.get(key)

    def require(self, key: str) -> Element:
        element = self.get(key)
        if element is None:
            raise KeyError(f"Unknown Pydrud element {key!r}")
        return element

    def upsert(
        self,
        key: str,
        widget_type: str,
        *,
        parent_key: Optional[str] = None,
        index: int = 0,
        desired_props: Optional[dict[str, Any]] = None,
        source: Optional[str] = None,
    ) -> tuple[Element, bool]:
        existing = self._elements.get(key)
        if existing is not None:
            if existing.widget_type != widget_type:
                raise TypeError(
                    f"Element key {key!r} changed type from "
                    f"{existing.widget_type!r} to {widget_type!r}"
                )
            existing.parent_key = parent_key
            existing.index = index
            if desired_props is not None:
                existing.update_desired(desired_props)
            if source:
                existing.source = source
            return existing, False

        element = Element(
            key=key,
            widget_type=widget_type,
            parent_key=parent_key,
            index=index,
            desired_props=desired_props or {},
            source=source,
        )
        self._elements[key] = element
        return element, True

    def remove(self, key: str) -> Optional[Element]:
        return self._elements.pop(key, None)

    def clear(self) -> None:
        self._elements.clear()
        self.revision = 0

    def keys(self) -> list[str]:
        return list(self._elements)

    def __len__(self) -> int:
        return len(self._elements)
