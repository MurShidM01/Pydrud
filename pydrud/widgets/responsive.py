"""
Responsive widgets — layouts that follow the real device resolution.

These widgets resolve themselves **at serialisation time**, so every time
the window changes (rotation, split screen, foldable unfold, font scale)
the app re-renders and the tree is rebuilt against fresh metrics.

::

    from pydrud import ResponsiveBuilder, AdaptiveLayout, ResponsiveGrid, ShowWhen

    ResponsiveBuilder(lambda s: Text(f"{s.width}x{s.height} ({s.breakpoint})"))

    AdaptiveLayout(
        compact=PhoneLayout(),
        medium=TabletLayout(),
        expanded=DesktopLayout(),
    )

    ResponsiveGrid(children=cards, min_item_width=180)

    ShowWhen(Sidebar(), min_width=600)
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from pydrud.core.responsive import Breakpoints, MediaQuery, Responsive
from pydrud.core.state import UNSET, is_truthy
from pydrud.widgets.base import Widget
from pydrud.widgets.layout import Container, GridView

__all__ = [
    "ResponsiveBuilder",
    "LayoutBuilder",
    "Constraints",
    "AdaptiveLayout",
    "ResponsiveGrid",
    "ShowWhen",
    "SafeArea",
]


def _empty(key: str) -> Widget:
    box = Container(key=key)
    box.style.setdefault("width", 0)
    box.style.setdefault("height", 0)
    return box


class ResponsiveBuilder(Widget):
    """Build a subtree from the live screen metrics.

    The builder is called with a
    :class:`~pydrud.core.responsive.ScreenInfo` snapshot every time the
    tree is serialised::

        ResponsiveBuilder(lambda screen:
            Row(children=cards) if screen.is_tablet else Column(children=cards))

    A zero-argument builder is also accepted, for when you prefer to read
    ``MediaQuery`` / ``Responsive`` directly inside it.
    """

    _widget_type = "ResponsiveBuilder"

    def __init__(self, builder: Callable[..., Optional[Widget]], *,
                 key: Optional[str] = None, **kwargs):
        super().__init__(key=key, **kwargs)
        if not callable(builder):
            raise TypeError("ResponsiveBuilder() expects a callable builder")
        self.builder = builder
        self.rebuild()

    # ── internals ───────────────────────────────────────────────────────

    def _invoke(self) -> Widget:
        info = MediaQuery.info()
        try:
            built = self.builder(info)
        except TypeError:
            built = self.builder()
        if built is None:
            return _empty(f"{self.key}._empty")
        if not isinstance(built, Widget):
            raise TypeError(
                "ResponsiveBuilder() builder must return a Widget or None, "
                f"got {type(built).__name__}")
        if built._auto_key:
            built.key = f"{self.key}._child"
            built._auto_key = False
        return built

    def rebuild(self) -> None:
        self.children = [self._invoke()]

    def unwrap(self) -> Widget:
        self.rebuild()
        return self.children[0]


class Constraints:
    """The box constraints a :class:`LayoutBuilder` builder receives.

    Flutter hands a builder a :class:`BoxConstraints`; Pydrud knows the same
    numbers from the live media query, so a builder can branch on the real
    available space instead of a hard-coded breakpoint::

        LayoutBuilder(lambda c: Row(children=cards) if c.max_width >= 600
                                else Column(children=cards))

    Unknown attributes fall through to the underlying
    :class:`~pydrud.core.responsive.ScreenInfo`, so ``c.orientation``,
    ``c.breakpoint`` and ``c.is_tablet`` all work.
    """

    __slots__ = ("_screen",)

    def __init__(self, screen):
        self._screen = screen

    @property
    def screen(self):
        """The full :class:`ScreenInfo` snapshot behind these constraints."""
        return self._screen

    @property
    def max_width(self) -> float:
        return self._screen.width

    @property
    def max_height(self) -> float:
        return self._screen.height

    @property
    def min_width(self) -> float:
        return 0

    @property
    def min_height(self) -> float:
        return 0

    # Flutter calls the bounded extent simply width/height.
    @property
    def width(self) -> float:
        return self.max_width

    @property
    def height(self) -> float:
        return self.max_height

    # ── size-class predicates (Flutter exposes these as plain getters) ───

    @property
    def is_phone(self) -> bool:
        return MediaQuery.is_phone()

    @property
    def is_tablet(self) -> bool:
        return MediaQuery.is_tablet()

    @property
    def is_desktop(self) -> bool:
        return MediaQuery.is_desktop()

    @property
    def is_landscape(self) -> bool:
        return MediaQuery.is_landscape()

    @property
    def is_portrait(self) -> bool:
        return MediaQuery.is_portrait()

    @property
    def is_dark(self) -> bool:
        return MediaQuery.is_dark()

    @property
    def breakpoint(self) -> str:
        return self._screen.breakpoint

    @property
    def orientation(self) -> str:
        return self._screen.orientation

    def at_least(self, size_class: str) -> bool:
        """True when the window is *size_class* or wider."""
        return MediaQuery.at_least(size_class)

    def at_most(self, size_class: str) -> bool:
        """True when the window is *size_class* or narrower."""
        return MediaQuery.at_most(size_class)

    def columns(self, min_item_width: float = 160, *,
                max_columns: int = 12, gutter: float = 16) -> int:
        """How many grid columns of at least *min_item_width* dp fit."""
        return Responsive.columns(min_item_width, max_columns=max_columns,
                                  gutter=gutter)

    def grid(self, min_item_width: float = 160, *, gutter: float = 16,
             max_columns: int = 12):
        """``(columns, item_width_dp)`` for a responsive grid."""
        return Responsive.grid(min_item_width, gutter=gutter,
                               max_columns=max_columns)

    def content_width(self, max_width: float = 560) -> int:
        """Page width capped on large screens (keeps line length sane)."""
        return Responsive.content_width(max_width)

    def matches(self, **query) -> bool:
        """A CSS-style media query, e.g. ``c.matches(min_width=600)``."""
        return MediaQuery.matches(**query)

    def __getattr__(self, item: str):
        # Raw metrics (device_type, refresh_rate, density, …) come straight
        # from the screen snapshot the constraints were derived from.
        try:
            return getattr(self._screen, item)
        except AttributeError:
            raise AttributeError(
                f"Constraints has no {item!r}; it exposes max_width, "
                f"max_height, is_tablet, columns(), grid(), matches() and "
                f"every ScreenInfo metric"
            ) from None

    def __repr__(self) -> str:
        return (f"Constraints(max_width={self.max_width:g}, "
                f"max_height={self.max_height:g})")


class LayoutBuilder(ResponsiveBuilder):
    """Build a subtree from the live box constraints (Flutter's names).

    ::

        LayoutBuilder(lambda c: GridView(columns=c.columns(180),
                                         children=cards))

    Like every responsive widget it re-runs on each serialisation, so a
    rotation, a split-screen resize or a foldable unfold rebuilds it.
    """

    _widget_type = "LayoutBuilder"

    def __init__(self, builder: Callable[..., Optional[Widget]], *,
                 key: Optional[str] = None):
        if not callable(builder):
            raise TypeError("LayoutBuilder() expects a callable builder")
        self._constraints_builder = builder
        super().__init__(self._adapt, key=key)

    def _adapt(self, screen) -> Optional[Widget]:
        return self._constraints_builder(Constraints(screen))

    @property
    def constraints(self) -> Constraints:
        """The constraints the current build was made from."""
        return Constraints(MediaQuery.info())


class AdaptiveLayout(ResponsiveBuilder):
    """Pick a completely different layout per window size class.

    ::

        AdaptiveLayout(
            compact=Column(children=items),      # phones
            medium=Row(children=items),          # small tablets
            expanded=Row(children=[rail, body]), # large tablets
            landscape=WideLayout(),              # orientation override
        )

    Missing classes fall back to the next smaller one, exactly like
    :meth:`Responsive.value`.  Values may be widgets *or* callables that
    return a widget (lazy — only the matching branch is built).
    """

    _widget_type = "AdaptiveLayout"

    def __init__(self, compact: Any = None, medium: Any = None,
                 expanded: Any = None, *, key: Optional[str] = None,
                 **cases: Any):
        self._cases = dict(cases)
        self._cases.update({"compact": compact, "medium": medium,
                            "expanded": expanded})
        super().__init__(self._pick, key=key)

    def _pick(self, info) -> Optional[Widget]:
        chosen = Responsive.value(**{k: v for k, v in self._cases.items()
                                     if v is not None})
        if callable(chosen) and not isinstance(chosen, Widget):
            chosen = chosen()
        return chosen


class ResponsiveGrid(ResponsiveBuilder):
    """A grid whose column count is computed from the screen width.

    ``min_item_width`` is the smallest comfortable item width in dp; the
    grid fits as many columns as it can (optionally capped by
    ``max_columns``), so a phone gets 1-2 columns and a tablet 3-5 —
    without you writing a single breakpoint.
    """

    _widget_type = "ResponsiveGrid"

    def __init__(self, *, children: Optional[list] = None,
                 min_item_width: float = 160, max_columns: int = 12,
                 spacing: float = 12, key: Optional[str] = None,
                 style: Optional[dict] = None, **kwargs):
        self._items = list(children or [])
        self._min_item_width = float(min_item_width)
        self._max_columns = int(max_columns)
        self._spacing = spacing
        self._grid_style = dict(style or {})
        self._grid_kwargs = kwargs
        super().__init__(self._build_grid, key=key)

    @property
    def columns(self) -> int:
        """The column count for the current screen."""
        return Responsive.columns(self._min_item_width,
                                  max_columns=self._max_columns,
                                  gutter=float(self._spacing))

    def add(self, *widgets: Widget) -> "ResponsiveGrid":
        self._items.extend(widgets)
        self.rebuild()
        return self

    def _build_grid(self, info) -> Widget:
        return GridView(
            key=f"{self.key}._grid",
            children=self._items,
            columns=self.columns,
            spacing=self._spacing,
            style=dict(self._grid_style),
            **self._grid_kwargs,
        )


class ShowWhen(ResponsiveBuilder):
    """Render *child* only when the media query — and ``condition`` — match.

    ::

        ShowWhen(Sidebar(), min_width=600)
        ShowWhen(CompactHeader(), at_most="compact")
        ShowWhen(Hero(), orientation="landscape", device="tablet")
        ShowWhen(Banner(), condition=has_unread)          # state, not size
        ShowWhen(Tips(), min_width=600, condition=show_tips)

    ``condition`` accepts anything readable — a bool, a ``State``, a
    ``Computed``, a ``Selector`` or a callable — and is re-read on every
    serialisation; :class:`~pydrud.widgets.conditional.Visible` is the
    clearer name for a purely state-driven toggle. When it does not
    match, ``otherwise`` (or a zero-sized placeholder) renders, so the
    diff engine can swap the real widget back without rebuilding the page.
    """

    _widget_type = "ShowWhen"

    def __init__(self, child: Optional[Widget] = None, *,
                 min_width: Optional[float] = None,
                 max_width: Optional[float] = None,
                 min_height: Optional[float] = None,
                 max_height: Optional[float] = None,
                 orientation: Optional[str] = None,
                 device: Optional[str] = None,
                 at_least: Optional[str] = None,
                 at_most: Optional[str] = None,
                 condition: Any = UNSET,
                 otherwise: Optional[Widget] = None,
                 key: Optional[str] = None):
        self._child = child
        self._otherwise = otherwise
        self._query = {
            "min_width": min_width, "max_width": max_width,
            "min_height": min_height, "max_height": max_height,
            "orientation": orientation, "device": device,
        }
        for name in (at_least, at_most):
            if name is not None:
                Breakpoints.index(name)  # validate early
        self._at_least = at_least
        self._at_most = at_most
        self._condition = condition
        super().__init__(self._choose, key=key)

    def matches(self) -> bool:
        if self._condition is not UNSET and not is_truthy(self._condition):
            return False
        if not MediaQuery.matches(**self._query):
            return False
        if self._at_least is not None and not MediaQuery.at_least(self._at_least):
            return False
        if self._at_most is not None and not MediaQuery.at_most(self._at_most):
            return False
        return True

    def _choose(self, info) -> Optional[Widget]:
        return self._child if self.matches() else self._otherwise


class SafeArea(Widget):
    """Pad a child away from status bars, gesture bars and cutouts.

    Insets come from the live device metrics, so a notched phone, a
    gesture-navigation phone and a tablet each get the right padding::

        SafeArea(child=Column(children=[...]))
        SafeArea(child=body, top=False)   # the AppBar already handles the top
    """

    _widget_type = "SafeArea"

    def __init__(self, *, child: Optional[Widget] = None, top: bool = True,
                 bottom: bool = True, left: bool = True, right: bool = True,
                 minimum: float = 0, key: Optional[str] = None,
                 style: Optional[dict] = None, **kwargs):
        super().__init__(key=key, style=style, **kwargs)
        self.child = child
        self.top, self.bottom = bool(top), bool(bottom)
        self.left, self.right = bool(left), bool(right)
        self.minimum = float(minimum)
        self.rebuild()

    def _padding(self) -> dict:
        insets = MediaQuery.safe_area()
        return {
            "top": max(insets["top"] if self.top else 0, self.minimum),
            "bottom": max(insets["bottom"] if self.bottom else 0, self.minimum),
            "left": max(insets["left"] if self.left else 0, self.minimum),
            "right": max(insets["right"] if self.right else 0, self.minimum),
        }

    def rebuild(self) -> None:
        style = dict(self.style)
        style.setdefault("width", "match")
        style["padding"] = self._padding()
        container = Container(key=f"{self.key}._safe", style=style,
                              child=self.child, expand=self.expand)
        self.children = [container]

    def unwrap(self) -> Widget:
        self.rebuild()
        return self.children[0]
