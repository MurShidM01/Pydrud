"""
Bottom navigation bars.
"""

from __future__ import annotations

from typing import Callable, Optional, Union
from pydrud.widgets.base import Widget
from pydrud.widgets.material._common import _clean, _nav_height

class NavItem:
    """One destination in a :class:`BottomNavigationBar` or :class:`NavigationRail`.

    ::

        NavItem("Cart", icon=Icons.CART, active_icon=Icons.CART,
                badge=3, badge_color="#FFEF4444", route="/cart")
    """

    def __init__(self, label: str = "", *, icon: str = "", route: Optional[str] = None,
                 badge: Optional[Union[str, int]] = None, enabled: bool = True,
                 active_icon: Optional[str] = None,
                 color: Optional[str] = None,
                 unselected_color: Optional[str] = None,
                 bg: Optional[str] = None,
                 badge_color: Optional[str] = None,
                 badge_text_color: Optional[str] = None,
                 tooltip: Optional[str] = None,
                 on_click: Optional[Callable] = None):
        self.label = str(label)
        self.icon = icon
        self.active_icon = active_icon
        self.route = route
        self.badge = badge
        self.enabled = enabled
        self.color = color
        self.unselected_color = unselected_color
        self.bg = bg
        self.badge_color = badge_color
        self.badge_text_color = badge_text_color
        self.tooltip = tooltip
        self.on_click = on_click

    def to_dict(self) -> dict:
        return _clean({
            "label": self.label,
            "icon": self.icon,
            "activeIcon": self.active_icon,
            "route": self.route,
            "badge": str(self.badge) if self.badge not in (None, "") else None,
            "enabled": None if self.enabled else False,
            "color": self.color,
            "unselectedColor": self.unselected_color,
            "bg": self.bg,
            "badgeColor": self.badge_color,
            "badgeTextColor": self.badge_text_color,
            "tooltip": self.tooltip,
        })


#: Flutter spells this ``NavigationDestination``/``BottomNavigationBarItem``;
#: plenty of ported code reaches for ``NavigationItem``. Same class, so
#: ``isinstance(item, NavItem)`` keeps working either way.
NavigationItem = NavItem
NavigationDestination = NavItem


class BottomNavigationBar(Widget):
    """A fully customisable bottom navigation bar (2-7 destinations).

    Pydrud draws the bar itself, so every property below really changes
    the pixels — nothing is locked behind a Material theme attribute::

        BottomNavigationBar(
            [NavItem("Home",  icon=Icons.HOME),
             NavItem("Search", icon=Icons.SEARCH),
             NavItem("Cart",  icon=Icons.CART, badge=3),
             NavItem("Me",    icon=Icons.PERSON)],
            selected=0,
            on_change=lambda e: go(e.value),

            # surface
            height=68, bg="#FFFFFFFF", elevation=12, radius=24,
            floating=True, margin=12, border_color="#14000000",
            top_divider=False,

            # selection indicator (Material 3 pill, like Flutter's NavigationBar)
            indicator="pill", indicator_color="#1A6366F1",
            indicator_width=64, indicator_height=34,

            # icons + labels
            icon_size=24, selected_icon_size=26,
            selected_color="#FF6366F1", unselected_color="#FF9CA3AF",
            label_behavior="selected",    # always | selected | never
            label_size=11, selected_label_size=12, bold_selected=True,

            # feedback
            ripple=True, ripple_color="#1A6366F1",
            animate=True, duration=180, haptic=True,
        )

    Set ``native=True`` to fall back to Android's ``BottomNavigationView``.
    """

    _widget_type = "BottomNavigationBar"

    INDICATORS = ("pill", "circle", "line", "dot", "none")
    LABEL_BEHAVIORS = ("always", "selected", "never")
    TYPES = ("fixed", "shifting")

    def __init__(
        self,
        items: Optional[list[NavItem]] = None,
        *,
        selected: int = 0,
        on_change: Optional[Callable] = None,
        # surface
        bg: Optional[str] = None,
        height: Optional[float] = None,
        elevation: Optional[float] = None,
        radius: Optional[float] = None,
        floating: bool = False,
        margin: Optional[float] = None,
        border_color: Optional[str] = None,
        border_width: Optional[float] = None,
        shadow_color: Optional[str] = None,
        top_divider: bool = False,
        divider_color: Optional[str] = None,
        item_padding: Optional[float] = None,
        icon_label_gap: Optional[float] = None,
        # indicator
        indicator: str = "pill",
        indicator_color: Optional[str] = None,
        indicator_width: Optional[float] = None,
        indicator_height: Optional[float] = None,
        indicator_radius: Optional[float] = None,
        # icons / labels
        selected_color: Optional[str] = None,
        unselected_color: Optional[str] = None,
        icon_size: Optional[float] = None,
        selected_icon_size: Optional[float] = None,
        show_labels: bool = True,
        label_behavior: Optional[str] = None,
        label_size: Optional[float] = None,
        selected_label_size: Optional[float] = None,
        bold_selected: bool = True,
        max_label_lines: int = 1,
        # badges
        badge_color: Optional[str] = None,
        badge_text_color: Optional[str] = None,
        # behaviour
        type: str = "fixed",
        ripple: bool = True,
        ripple_color: Optional[str] = None,
        animate: bool = True,
        duration: Optional[int] = None,
        haptic: bool = False,
        safe_area: bool = True,
        native: bool = False,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.items: list[NavItem] = list(items or [])
        self.selected = max(0, min(int(selected), max(0, len(self.items) - 1)))

        if indicator not in self.INDICATORS:
            raise ValueError(
                f"BottomNavigationBar indicator must be one of {self.INDICATORS}")
        if label_behavior is not None and label_behavior not in self.LABEL_BEHAVIORS:
            raise ValueError(
                f"label_behavior must be one of {self.LABEL_BEHAVIORS}")
        if type not in self.TYPES:
            raise ValueError(f"type must be one of {self.TYPES}")

        self.bg = bg
        self.height = height
        self.elevation = elevation
        self.radius = radius
        self.floating = floating
        self.margin = margin
        self.border_color = border_color
        self.border_width = border_width
        self.shadow_color = shadow_color
        self.top_divider = top_divider
        self.divider_color = divider_color
        self.item_padding = item_padding
        self.icon_label_gap = icon_label_gap

        self.indicator = indicator
        self.indicator_color = indicator_color
        self.indicator_width = indicator_width
        self.indicator_height = indicator_height
        self.indicator_radius = indicator_radius

        self.selected_color = selected_color
        self.unselected_color = unselected_color
        self.icon_size = icon_size
        self.selected_icon_size = selected_icon_size
        self.show_labels = show_labels
        self.label_behavior = (label_behavior
                               or ("always" if show_labels else "never"))
        self.label_size = label_size
        self.selected_label_size = selected_label_size
        self.bold_selected = bold_selected
        self.max_label_lines = max(1, int(max_label_lines))

        self.badge_color = badge_color
        self.badge_text_color = badge_text_color

        self.type = type
        self.ripple = ripple
        self.ripple_color = ripple_color
        self.animate = animate
        self.duration = duration
        self.haptic = haptic
        self.safe_area = safe_area
        self.native = native

        if on_change is not None:
            self.event_handlers["change"] = on_change

        # Layout hints for the native renderer. The bar draws its own
        # gesture inset and floating margin (see PydrudNavBar), so it opts
        # *out* of the generic safe-area padding to avoid doubling it.
        self.style.setdefault("width", "match")
        self.style.setdefault("height", self.height
                              if self.height is not None else _nav_height())
        self.style["safeAreaBottom"] = False

    # ── behaviour ───────────────────────────────────────────────────────

    @property
    def current(self) -> Optional[NavItem]:
        return self.items[self.selected] if self.items else None

    def select(self, index: int) -> "BottomNavigationBar":
        """Programmatically change the selected destination (chainable)."""
        if self.items:
            self.selected = max(0, min(int(index), len(self.items) - 1))
        return self

    def select_route(self, route: str) -> "BottomNavigationBar":
        """Select the destination whose ``route`` matches (chainable)."""
        for index, item in enumerate(self.items):
            if item.route == route:
                self.selected = index
                break
        return self

    def badge(self, index: int, value: Optional[Union[str, int]]) -> "BottomNavigationBar":
        """Set or clear a badge on one destination (chainable)."""
        if 0 <= index < len(self.items):
            self.items[index].badge = value
        return self

    # ── layout hint used by Scaffold ────────────────────────────────────

    @property
    def effective_height(self) -> float:
        """Height the bar occupies, including a floating margin."""
        from pydrud.widgets.tokens import Tokens

        height = self.height if self.height is not None else Tokens.nav_height
        if self.floating:
            height += (self.margin if self.margin is not None else 12) * 2
        return height

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "items": [i.to_dict() for i in self.items],
            "selected": self.selected,
            "bg": self.bg,
            "height": self.height,
            "elevation": self.elevation,
            "radius": self.radius,
            "floating": self.floating or None,
            "margin": self.margin,
            "borderColor": self.border_color,
            "borderWidth": self.border_width,
            "shadowColor": self.shadow_color,
            "topDivider": self.top_divider or None,
            "dividerColor": self.divider_color,
            "itemPadding": self.item_padding,
            "iconLabelGap": self.icon_label_gap,
            "indicator": self.indicator,
            "indicatorColor": self.indicator_color,
            "indicatorWidth": self.indicator_width,
            "indicatorHeight": self.indicator_height,
            "indicatorRadius": self.indicator_radius,
            "selectedColor": self.selected_color,
            "unselectedColor": self.unselected_color,
            "iconSize": self.icon_size,
            "selectedIconSize": self.selected_icon_size,
            "showLabels": self.show_labels,
            "labelBehavior": self.label_behavior,
            "labelSize": self.label_size,
            "selectedLabelSize": self.selected_label_size,
            "boldSelected": self.bold_selected,
            "maxLabelLines": self.max_label_lines,
            "badgeColor": self.badge_color,
            "badgeTextColor": self.badge_text_color,
            "type": self.type,
            "ripple": self.ripple,
            "rippleColor": self.ripple_color,
            "animate": self.animate,
            "duration": self.duration,
            "haptic": self.haptic or None,
            "safeArea": self.safe_area,
            "native": self.native or None,
        }))
        return props


#: Flutter calls the Material 3 version ``NavigationBar``.
NavigationBar = BottomNavigationBar
