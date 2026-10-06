"""
Tab bars.
"""

from __future__ import annotations

from typing import Callable, Optional, Union
from pydrud.widgets.base import Widget
from pydrud.widgets.material._common import _clean

class Tab:
    """One tab: a label, an optional icon, and the content to show.

    Every visual aspect can be overridden per tab — handy for a single
    highlighted tab in an otherwise uniform bar::

        Tab("Inbox", icon=Icons.EMAIL, badge=12, color="#FFEF4444")
    """

    def __init__(self, label: str = "", *, content: Optional[Widget] = None,
                 icon: Optional[str] = None, badge: Optional[Union[str, int]] = None,
                 enabled: bool = True,
                 active_icon: Optional[str] = None,
                 color: Optional[str] = None,
                 unselected_color: Optional[str] = None,
                 badge_color: Optional[str] = None,
                 badge_text_color: Optional[str] = None,
                 tooltip: Optional[str] = None):
        self.label = str(label)
        self.content = content
        self.icon = icon
        self.active_icon = active_icon
        self.badge = badge
        self.enabled = enabled
        self.color = color
        self.unselected_color = unselected_color
        self.badge_color = badge_color
        self.badge_text_color = badge_text_color
        self.tooltip = tooltip

    def to_dict(self) -> dict:
        return _clean({
            "label": self.label,
            "icon": self.icon,
            "activeIcon": self.active_icon,
            "badge": str(self.badge) if self.badge not in (None, "") else None,
            "enabled": None if self.enabled else False,
            "color": self.color,
            "unselectedColor": self.unselected_color,
            "badgeColor": self.badge_color,
            "badgeTextColor": self.badge_text_color,
            "tooltip": self.tooltip,
        })


class Tabs(Widget):
    """A fully customisable tab bar plus the body of the selected tab.

    Only the selected tab's content is serialised, which keeps the patch
    small and mirrors how a real ``ViewPager`` lazily builds pages.

    Every knob Flutter's ``TabBar`` exposes is available here::

        Tabs(
            [Tab("Today", icon=Icons.HOME, content=today),
             Tab("Week",  icon=Icons.CALENDAR, content=week)],
            mode="scrollable",            # or "fixed"
            indicator="pill",             # line | pill | dot | none
            indicator_color="#FF6366F1",
            indicator_height=3,
            indicator_radius=999,
            indicator_size="label",       # label | tab | full
            label_color="#FF111827",
            unselected_label_color="#FF6B7280",
            label_size=14, selected_label_size=14, bold_selected=True,
            icon_position="start",        # top | start
            tab_height=52, tab_min_width=96,
            bg="#FFFFFFFF", divider=True, divider_color="#1A000000",
            ripple_color="#1A6366F1", align="fill",
            animate=True, duration=220,
        )
    """

    _widget_type = "Tabs"

    INDICATORS = ("line", "pill", "dot", "none")
    MODES = ("fixed", "scrollable")
    ICON_POSITIONS = ("top", "start")
    ALIGNMENTS = ("fill", "start", "center", "end")

    def __init__(
        self,
        tabs: Optional[list[Tab]] = None,
        *,
        selected: int = 0,
        scrollable: bool = False,
        mode: Optional[str] = None,
        on_change: Optional[Callable] = None,
        # indicator
        indicator: str = "line",
        indicator_color: Optional[str] = None,
        indicator_height: Optional[float] = None,
        indicator_radius: Optional[float] = None,
        indicator_size: str = "label",
        # labels
        label_color: Optional[str] = None,
        unselected_label_color: Optional[str] = None,
        label_size: Optional[float] = None,
        selected_label_size: Optional[float] = None,
        bold_selected: bool = True,
        uppercase: bool = False,
        show_labels: bool = True,
        # icons
        icon_size: Optional[float] = None,
        icon_position: str = "top",
        icon_color: Optional[str] = None,
        selected_icon_color: Optional[str] = None,
        # surface
        bg: Optional[str] = None,
        elevation: Optional[float] = None,
        radius: Optional[float] = None,
        tab_height: Optional[float] = None,
        tab_min_width: Optional[float] = None,
        padding: Optional[float] = None,
        align: str = "fill",
        divider: bool = False,
        divider_color: Optional[str] = None,
        ripple: bool = True,
        ripple_color: Optional[str] = None,
        # motion
        animate: bool = True,
        duration: Optional[int] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        # Accept the convenient shorthands as well as Tab objects:
        #   Tabs(["One", "Two"])            — labels only
        #   Tabs([("Inbox", Icons.EMAIL)])  — label + icon
        #   Tabs([{"label": "A", "badge": 3}])
        self._pending_children = list(self.children)
        self.tabs: list[Tab] = [Tabs._as_tab(t) for t in (tabs or [])]
        self.selected = max(0, min(int(selected), max(0, len(self.tabs) - 1)))

        if mode is not None:
            if mode not in self.MODES:
                raise ValueError(f"Tabs mode must be one of {self.MODES}")
            self.scrollable = mode == "scrollable"
        else:
            self.scrollable = bool(scrollable)

        if indicator not in self.INDICATORS:
            raise ValueError(f"Tabs indicator must be one of {self.INDICATORS}")
        if indicator_size not in ("label", "tab", "full"):
            raise ValueError("indicator_size must be label, tab or full")
        if icon_position not in self.ICON_POSITIONS:
            raise ValueError(f"icon_position must be one of {self.ICON_POSITIONS}")
        if align not in self.ALIGNMENTS:
            raise ValueError(f"align must be one of {self.ALIGNMENTS}")

        self.indicator = indicator
        self.indicator_color = indicator_color
        self.indicator_height = indicator_height
        self.indicator_radius = indicator_radius
        self.indicator_size = indicator_size

        self.label_color = label_color
        self.unselected_label_color = unselected_label_color
        self.label_size = label_size
        self.selected_label_size = selected_label_size
        self.bold_selected = bold_selected
        self.uppercase = uppercase
        self.show_labels = show_labels

        self.icon_size = icon_size
        self.icon_position = icon_position
        self.icon_color = icon_color
        self.selected_icon_color = selected_icon_color

        self.bg = bg
        self.elevation = elevation
        self.radius = radius
        self.tab_height = tab_height
        self.tab_min_width = tab_min_width
        self.padding = padding
        self.align = align
        self.divider = divider
        self.divider_color = divider_color
        self.ripple = ripple
        self.ripple_color = ripple_color
        self.animate = animate
        self.duration = duration

        if on_change is not None:
            self.event_handlers["change"] = on_change
        self._sync_children()

    # ── behaviour ───────────────────────────────────────────────────────

    def select(self, index: int) -> "Tabs":
        """Programmatically switch tab (chainable)."""
        if self.tabs:
            self.selected = max(0, min(int(index), len(self.tabs) - 1))
            self._sync_children()
        return self

    @staticmethod
    def _as_tab(tab) -> Tab:
        """Coerce a label, tuple or dict into a :class:`Tab`."""
        if isinstance(tab, Tab):
            return tab
        if isinstance(tab, dict):
            return Tab(**tab)
        if isinstance(tab, (tuple, list)):
            label = tab[0] if tab else ""
            icon = tab[1] if len(tab) > 1 else None
            content = tab[2] if len(tab) > 2 else None
            return Tab(str(label), icon=icon, content=content)
        return Tab(str(tab))

    def _sync_children(self) -> None:
        # Tabs declared without content keep whatever children the caller
        # passed in, so `Tabs(["A", "B"], children=[body])` renders a body
        # instead of silently dropping it.
        self.children = list(getattr(self, "_pending_children", []))
        if not self.tabs:
            return
        content = self.tabs[self.selected].content
        if content is not None:
            if content._auto_key:
                content.key = f"{self.key}_body{self.selected}"
                content._auto_key = False
            self.children = [content]

    @property
    def current(self) -> Optional[Tab]:
        return self.tabs[self.selected] if self.tabs else None

    @property
    def effective_height(self) -> float:
        """Height the tab bar occupies."""
        return self.tab_height if self.tab_height is not None else 52.0

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "tabs": [t.to_dict() for t in self.tabs],
            "selected": self.selected,
            "scrollable": self.scrollable or None,
            "mode": "scrollable" if self.scrollable else "fixed",
            "indicator": self.indicator,
            "indicatorColor": self.indicator_color,
            "indicatorHeight": self.indicator_height,
            "indicatorRadius": self.indicator_radius,
            "indicatorSize": self.indicator_size,
            "labelColor": self.label_color,
            "unselectedLabelColor": self.unselected_label_color,
            "labelSize": self.label_size,
            "selectedLabelSize": self.selected_label_size,
            "boldSelected": self.bold_selected,
            "uppercase": self.uppercase or None,
            "showLabels": self.show_labels,
            "iconSize": self.icon_size,
            "iconPosition": self.icon_position,
            "iconColor": self.icon_color,
            "selectedIconColor": self.selected_icon_color,
            "bg": self.bg,
            "elevation": self.elevation,
            "radius": self.radius,
            "tabHeight": self.tab_height,
            "tabMinWidth": self.tab_min_width,
            "padding": self.padding,
            "align": self.align,
            "divider": self.divider or None,
            "dividerColor": self.divider_color,
            "ripple": self.ripple,
            "rippleColor": self.ripple_color,
            "animate": self.animate,
            "duration": self.duration,
        }))
        return props


#: ``TabBar`` reads better when the tabs have no inline content.
TabBar = Tabs
