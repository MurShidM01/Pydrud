"""
Conditional rendering — show a subtree only while some state says so.

``ShowWhen`` answers "is the *window* big enough?"; :class:`Visible`
answers the half every app asks: "is the *app* in the right state?" ::

    Visible(Dashboard(), when=logged_in)
    Visible(Spinner(), when=is_loading, otherwise=Results())
    Hidden(CheckoutButton(), when=lambda: cart.count == 0)

The condition — a bool, ``State``, ``Computed``, ``Selector``,
``ReactiveList`` (truthy when non-empty) or a callable — is read at
serialisation time, so the widget only has to sit in a tree that is
rebuilt when the state changes. When false, ``otherwise`` renders, or a
zero-sized placeholder the diff engine can swap back out.
"""

from __future__ import annotations

from typing import Any, Optional

from pydrud.core.state import UNSET, is_truthy
from pydrud.widgets.base import Widget
from pydrud.widgets.responsive import ResponsiveBuilder

__all__ = ["Visible", "Hidden"]


def _one_condition(when: Any, condition: Any, visible: Any) -> Any:
    given = [v for v in (when, condition, visible) if v is not UNSET]
    if len(given) > 1:
        raise TypeError(
            "pass only one of when=, condition= or visible= to Visible()")
    return given[0] if given else True


class Visible(ResponsiveBuilder):
    """Render *child* only while a condition is true.

    ``when=``, ``condition=`` and ``visible=`` are one parameter under
    three names, because three framework backgrounds reach for three
    different words.
    """

    _widget_type = "Visible"

    def __init__(self, child: Optional[Widget] = None, when: Any = UNSET, *,
                 condition: Any = UNSET, visible: Any = UNSET,
                 otherwise: Optional[Widget] = None, invert: bool = False,
                 key: Optional[str] = None):
        self._child = child
        self._otherwise = otherwise
        self._condition = _one_condition(when, condition, visible)
        self._invert = bool(invert)
        super().__init__(self._choose, key=key)

    def matches(self) -> bool:
        """True when the condition currently resolves truthy."""
        result = is_truthy(self._condition)
        return not result if self._invert else result

    def _choose(self, info) -> Optional[Widget]:
        return self._child if self.matches() else self._otherwise

    def __repr__(self) -> str:
        return (f"{type(self).__name__}(key={self.key!r}, "
                f"visible={self.matches()})")


class Hidden(Visible):
    """The inverse of :class:`Visible` — render *child* unless it holds."""

    _widget_type = "Hidden"

    def __init__(self, child: Optional[Widget] = None, when: Any = UNSET, *,
                 condition: Any = UNSET, visible: Any = UNSET,
                 otherwise: Optional[Widget] = None,
                 key: Optional[str] = None):
        super().__init__(child, when, condition=condition, visible=visible,
                         otherwise=otherwise, invert=True, key=key)
