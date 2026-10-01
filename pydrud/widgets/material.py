"""
Material Design 3 component library.

Everything in this module maps onto a real Android view in ``ViewFactory``:
``ListTile`` becomes a ``LinearLayout`` with the standard 16dp/72dp metrics,
``Tabs`` becomes a ``TabLayout`` + ``ViewPager``-style content host,
``BottomNavigationBar`` becomes a ``BottomNavigationView``, and so on.

The Python side stays declarative: build the widget, hand it a callback,
return it from your page builder.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Union

from pydrud.widgets.base import Widget
from pydrud.widgets.theme import Colors


def _clean(d: dict) -> dict:
    """Drop None values so JSON payloads stay small and defaults stay native."""
    return {k: v for k, v in d.items() if v is not None}


# ──────────────────────────────────────────────────────────────────────────
# Lists
# ──────────────────────────────────────────────────────────────────────────


class ListTile(Widget):
    """A single row of a list: leading icon, title, subtitle, trailing widget.

    ::

        ListTile("Wi-Fi", subtitle="PyNet 5G", leading=Icons.SETTINGS,
                 trailing=Switch(value=True), on_click=open_wifi)
    """

    _widget_type = "ListTile"

    def __init__(
        self,
        title: str = "",
        *,
        subtitle: Optional[str] = None,
        leading: Optional[Union[str, Widget]] = None,
        trailing: Optional[Union[str, Widget]] = None,
        dense: bool = False,
        selected: bool = False,
        enabled: bool = True,
        three_line: bool = False,
        on_click: Optional[Callable] = None,
        on_long_press: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_click=on_click,
                         on_long_press=on_long_press, **kwargs)
        self.title = str(title)
        self.subtitle = subtitle
        self.dense = dense
        self.selected = selected
        self.enabled = enabled
        self.three_line = three_line

        self.leading_icon: Optional[str] = None
        self.trailing_icon: Optional[str] = None
        if isinstance(leading, Widget):
            leading.key = f"{self.key}_leading"
            leading._auto_key = False
            self.children.append(leading)
        elif leading:
            self.leading_icon = str(leading)
        if isinstance(trailing, Widget):
            trailing.key = f"{self.key}_trailing"
            trailing._auto_key = False
            self.children.append(trailing)
        elif trailing:
            self.trailing_icon = str(trailing)

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "title": self.title,
            "subtitle": self.subtitle,
            "leadingIcon": self.leading_icon,
            "trailingIcon": self.trailing_icon,
            "dense": self.dense or None,
            "selected": self.selected or None,
            "enabled": None if self.enabled else False,
            "threeLine": self.three_line or None,
        }))
        return props


class ExpansionTile(Widget):
    """A tile that expands to reveal its children (accordion / FAQ UIs)."""

    _widget_type = "ExpansionTile"

    def __init__(
        self,
        title: str = "",
        *,
        children: Optional[list[Widget]] = None,
        subtitle: Optional[str] = None,
        leading: Optional[str] = None,
        expanded: bool = False,
        on_expand: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.title = str(title)
        self.subtitle = subtitle
        self.leading = leading
        self.expanded = bool(expanded)
        self.children = list(children or [])
        if on_expand is not None:
            self.event_handlers["expand"] = on_expand

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "title": self.title,
            "subtitle": self.subtitle,
            "leadingIcon": self.leading,
            "expanded": self.expanded,
        }))
        return props


# ──────────────────────────────────────────────────────────────────────────
# Small informational widgets
# ──────────────────────────────────────────────────────────────────────────


class Chip(Widget):
    """A compact element for tags, filters and choices.

    ``variant`` is one of ``"assist"``, ``"filter"``, ``"input"``, ``"suggestion"``.
    Filter chips are selectable and emit ``change`` with ``{"selected": bool}``.
    """

    _widget_type = "Chip"

    VARIANTS = ("assist", "filter", "input", "suggestion")

    def __init__(
        self,
        label: str = "",
        *,
        icon: Optional[str] = None,
        variant: str = "assist",
        selected: bool = False,
        deletable: bool = False,
        color: Optional[str] = None,
        on_click: Optional[Callable] = None,
        on_change: Optional[Callable] = None,
        on_delete: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_click=on_click, **kwargs)
        if variant not in self.VARIANTS:
            raise ValueError(
                f"Chip variant must be one of {self.VARIANTS}, got {variant!r}")
        self.label = str(label)
        self.icon = icon
        self.variant = variant
        self.selected = bool(selected)
        self.deletable = bool(deletable)
        self.color = color
        if on_change is not None:
            self.event_handlers["change"] = on_change
        if on_delete is not None:
            self.event_handlers["delete"] = on_delete

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "label": self.label,
            "icon": self.icon,
            "variant": self.variant,
            "selected": self.selected,
            "deletable": self.deletable or None,
            "color": self.color,
        }))
        return props


class Badge(Widget):
    """A small count/dot overlaid on the top-right of its child."""

    _widget_type = "Badge"

    def __init__(
        self,
        label: Optional[Union[str, int]] = None,
        *,
        child: Optional[Widget] = None,
        color: str = Colors.ERROR,
        text_color: str = Colors.WHITE,
        max_count: int = 99,
        show: bool = True,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if isinstance(label, (int, float)):
            count = int(label)
            self.label = f"{max_count}+" if count > max_count else str(count)
            self.show = show and count > 0
        else:
            self.label = str(label) if label is not None else ""
            self.show = show
        self.color = color
        self.text_color = text_color
        if child is not None:
            self.children = [child]

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "label": self.label,
            "color": self.color,
            "textColor": self.text_color,
            "show": self.show,
        })
        return props


class Avatar(Widget):
    """A circular user image, icon or initials bubble."""

    _widget_type = "Avatar"

    def __init__(
        self,
        source: Optional[str] = None,
        *,
        initials: Optional[str] = None,
        icon: Optional[str] = None,
        size: float = 40,
        bg: str = Colors.PRIMARY,
        color: str = Colors.WHITE,
        on_click: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_click=on_click, **kwargs)
        self.source = source
        self.initials = (initials or "")[:2].upper()
        self.icon = icon
        self.size = float(size)
        self.bg = bg
        self.color = color

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "source": self.source,
            "initials": self.initials or None,
            "icon": self.icon,
            "size": self.size,
            "bg": self.bg,
            "color": self.color,
        }))
        return props


class Banner(Widget):
    """A prominent, dismissible message at the top of the content area."""

    _widget_type = "Banner"

    SEVERITIES = {"info": Colors.INFO, "success": Colors.SUCCESS,
                  "warning": Colors.WARNING, "error": Colors.ERROR}

    def __init__(
        self,
        message: str = "",
        *,
        severity: str = "info",
        icon: Optional[str] = None,
        action: Optional[str] = None,
        dismissible: bool = True,
        on_action: Optional[Callable] = None,
        on_dismiss: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if severity not in self.SEVERITIES:
            raise ValueError(
                f"Banner severity must be one of {sorted(self.SEVERITIES)}")
        self.message = str(message)
        self.severity = severity
        self.icon = icon
        self.action = action
        self.dismissible = dismissible
        if on_action is not None:
            self.event_handlers["click"] = on_action
        if on_dismiss is not None:
            self.event_handlers["dismiss"] = on_dismiss

    @property
    def color(self) -> str:
        return self.SEVERITIES[self.severity]

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "message": self.message,
            "severity": self.severity,
            "color": self.color,
            "icon": self.icon,
            "action": self.action,
            "dismissible": self.dismissible,
        }))
        return props


class Tooltip(Widget):
    """Wraps a child with a long-press tooltip (native Android tooltip)."""

    _widget_type = "Tooltip"

    def __init__(self, message: str = "", *, child: Optional[Widget] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(key=key, **kwargs)
        self.message = str(message)
        if child is not None:
            self.children = [child]

    def _serialise_props(self) -> dict:
        return {**self._extra, "message": self.message}


# ──────────────────────────────────────────────────────────────────────────
# Navigation
# ──────────────────────────────────────────────────────────────────────────


class Tab:
    """One tab: a label, an optional icon, and the content to show."""

    def __init__(self, label: str = "", *, content: Optional[Widget] = None,
                 icon: Optional[str] = None, badge: Optional[Union[str, int]] = None,
                 enabled: bool = True):
        self.label = str(label)
        self.content = content
        self.icon = icon
        self.badge = badge
        self.enabled = enabled

    def to_dict(self) -> dict:
        return _clean({
            "label": self.label,
            "icon": self.icon,
            "badge": str(self.badge) if self.badge not in (None, "") else None,
            "enabled": None if self.enabled else False,
        })


class Tabs(Widget):
    """A TabLayout plus the body of the selected tab.

    Only the selected tab's content is serialised, which keeps the patch
    small and mirrors how a real ``ViewPager`` lazily builds pages.
    """

    _widget_type = "Tabs"

    def __init__(
        self,
        tabs: Optional[list[Tab]] = None,
        *,
        selected: int = 0,
        scrollable: bool = False,
        indicator_color: Optional[str] = None,
        on_change: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.tabs: list[Tab] = list(tabs or [])
        self.selected = max(0, min(int(selected), max(0, len(self.tabs) - 1)))
        self.scrollable = scrollable
        self.indicator_color = indicator_color
        if on_change is not None:
            self.event_handlers["change"] = on_change
        self._sync_children()

    def _sync_children(self) -> None:
        self.children = []
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

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "tabs": [t.to_dict() for t in self.tabs],
            "selected": self.selected,
            "scrollable": self.scrollable or None,
            "indicatorColor": self.indicator_color,
        }))
        return props


class NavItem:
    """One destination in a :class:`BottomNavigationBar` or :class:`NavigationRail`."""

    def __init__(self, label: str = "", *, icon: str = "", route: Optional[str] = None,
                 badge: Optional[Union[str, int]] = None, enabled: bool = True):
        self.label = str(label)
        self.icon = icon
        self.route = route
        self.badge = badge
        self.enabled = enabled

    def to_dict(self) -> dict:
        return _clean({
            "label": self.label,
            "icon": self.icon,
            "route": self.route,
            "badge": str(self.badge) if self.badge not in (None, "") else None,
            "enabled": None if self.enabled else False,
        })


class BottomNavigationBar(Widget):
    """Material bottom navigation with 2-5 destinations."""

    _widget_type = "BottomNavigationBar"

    def __init__(
        self,
        items: Optional[list[NavItem]] = None,
        *,
        selected: int = 0,
        bg: Optional[str] = None,
        selected_color: Optional[str] = None,
        unselected_color: Optional[str] = None,
        show_labels: bool = True,
        on_change: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.items: list[NavItem] = list(items or [])
        self.selected = max(0, min(int(selected), max(0, len(self.items) - 1)))
        self.bg = bg
        self.selected_color = selected_color
        self.unselected_color = unselected_color
        self.show_labels = show_labels
        if on_change is not None:
            self.event_handlers["change"] = on_change

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "items": [i.to_dict() for i in self.items],
            "selected": self.selected,
            "bg": self.bg,
            "selectedColor": self.selected_color,
            "unselectedColor": self.unselected_color,
            "showLabels": self.show_labels,
        }))
        return props


class NavigationRail(Widget):
    """A vertical navigation bar for tablets and landscape layouts."""

    _widget_type = "NavigationRail"

    def __init__(
        self,
        items: Optional[list[NavItem]] = None,
        *,
        selected: int = 0,
        extended: bool = False,
        leading: Optional[Widget] = None,
        on_change: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.items = list(items or [])
        self.selected = max(0, min(int(selected), max(0, len(self.items) - 1)))
        self.extended = extended
        if leading is not None:
            self.children = [leading]
        if on_change is not None:
            self.event_handlers["change"] = on_change

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "items": [i.to_dict() for i in self.items],
            "selected": self.selected,
            "extended": self.extended,
        })
        return props


class Drawer(Widget):
    """A navigation drawer that slides in from the start edge.

    Pass it to ``Scaffold(drawer=...)``; open it with ``page.open_drawer()``
    or by tapping the AppBar's hamburger icon.
    """

    _widget_type = "Drawer"

    def __init__(
        self,
        *,
        children: Optional[list[Widget]] = None,
        header: Optional[Widget] = None,
        width: float = 300,
        bg: Optional[str] = None,
        side: str = "start",
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if side not in ("start", "end"):
            raise ValueError("Drawer side must be 'start' or 'end'")
        self.width = float(width)
        self.bg = bg
        self.side = side
        self.children = []
        if header is not None:
            if header._auto_key:
                header.key = f"{self.key}_header"
                header._auto_key = False
            self.children.append(header)
        self.children.extend(children or [])

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({"width": self.width, "bg": self.bg,
                             "side": self.side}))
        return props


class SegmentedButton(Widget):
    """A row of connected buttons behaving like a single/multi choice group."""

    _widget_type = "SegmentedButton"

    def __init__(
        self,
        options: Optional[list[str]] = None,
        *,
        selected: Optional[Union[int, list[int]]] = 0,
        multi: bool = False,
        icons: Optional[list[str]] = None,
        on_change: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.options = [str(o) for o in (options or [])]
        self.multi = multi
        if multi:
            self.selected = list(selected) if isinstance(selected, (list, tuple)) \
                else ([selected] if isinstance(selected, int) else [])
        else:
            self.selected = selected if isinstance(selected, int) else 0
        self.icons = list(icons or [])
        if on_change is not None:
            self.event_handlers["change"] = on_change

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "options": self.options,
            "selected": self.selected,
            "multi": self.multi or None,
            "icons": self.icons or None,
        }))
        return props


# ──────────────────────────────────────────────────────────────────────────
# Input & feedback
# ──────────────────────────────────────────────────────────────────────────


class SearchBar(Widget):
    """A rounded search field with leading search icon and clear button."""

    _widget_type = "SearchBar"

    def __init__(
        self,
        value: str = "",
        *,
        hint: str = "Search",
        suggestions: Optional[list[str]] = None,
        autofocus: bool = False,
        on_change: Optional[Callable] = None,
        on_submit: Optional[Callable] = None,
        on_clear: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.value = str(value)
        self.hint = hint
        self.suggestions = list(suggestions or [])
        self.autofocus = autofocus
        if on_change is not None:
            self.event_handlers["change"] = on_change
        if on_submit is not None:
            self.event_handlers["submit"] = on_submit
        if on_clear is not None:
            self.event_handlers["clear"] = on_clear

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "value": self.value,
            "hint": self.hint,
            "suggestions": self.suggestions or None,
            "autofocus": self.autofocus or None,
        }))
        return props


class Rating(Widget):
    """A star rating bar (read-only when ``on_change`` is omitted)."""

    _widget_type = "Rating"

    def __init__(
        self,
        value: float = 0,
        *,
        count: int = 5,
        size: float = 24,
        color: str = Colors.ACCENT,
        half: bool = True,
        on_change: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.count = int(count)
        self.value = max(0.0, min(float(value), float(self.count)))
        self.size = float(size)
        self.color = color
        self.half = half
        self.readonly = on_change is None
        if on_change is not None:
            self.event_handlers["change"] = on_change

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "value": self.value,
            "count": self.count,
            "size": self.size,
            "color": self.color,
            "half": self.half,
            "readonly": self.readonly,
        })
        return props


class CircularProgress(Widget):
    """An indeterminate spinner, or a determinate ring when ``value`` is set."""

    _widget_type = "CircularProgress"

    def __init__(
        self,
        value: Optional[float] = None,
        *,
        size: float = 36,
        stroke: float = 4,
        color: Optional[str] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.value = None if value is None else max(0.0, min(float(value), 1.0))
        self.size = float(size)
        self.stroke = float(stroke)
        self.color = color

    @property
    def indeterminate(self) -> bool:
        return self.value is None

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "value": self.value,
            "size": self.size,
            "stroke": self.stroke,
            "color": self.color,
            "indeterminate": self.indeterminate,
        }))
        return props


class Skeleton(Widget):
    """A shimmering placeholder shown while data loads."""

    _widget_type = "Skeleton"

    def __init__(self, *, width: Union[float, str] = "match", height: float = 16,
                 radius: float = 8, lines: int = 1, key: Optional[str] = None,
                 **kwargs):
        super().__init__(key=key, **kwargs)
        self.width = width
        self.height = float(height)
        self.radius = float(radius)
        self.lines = max(1, int(lines))

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({"width": self.width, "height": self.height,
                      "radius": self.radius, "lines": self.lines})
        return props


class RefreshIndicator(Widget):
    """Pull-to-refresh wrapper (``SwipeRefreshLayout``).

    The handler receives the event and should call ``page.end_refresh()``
    (or set ``refreshing=False`` and update) when the work is done.
    """

    _widget_type = "RefreshIndicator"

    def __init__(self, *, child: Optional[Widget] = None,
                 on_refresh: Optional[Callable] = None,
                 refreshing: bool = False, color: Optional[str] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(key=key, **kwargs)
        self.refreshing = bool(refreshing)
        self.color = color
        if child is not None:
            self.children = [child]
        if on_refresh is not None:
            self.event_handlers["refresh"] = on_refresh

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({"refreshing": self.refreshing, "color": self.color}))
        return props


class Stepper(Widget):
    """A horizontal or vertical step indicator for wizards and checkouts."""

    _widget_type = "Stepper"

    def __init__(
        self,
        steps: Optional[list[str]] = None,
        *,
        current: int = 0,
        orientation: str = "horizontal",
        content: Optional[Widget] = None,
        on_step: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if orientation not in ("horizontal", "vertical"):
            raise ValueError("Stepper orientation must be horizontal or vertical")
        self.steps = [str(s) for s in (steps or [])]
        self.current = max(0, min(int(current), max(0, len(self.steps) - 1)))
        self.orientation = orientation
        if content is not None:
            self.children = [content]
        if on_step is not None:
            self.event_handlers["change"] = on_step

    @property
    def is_last(self) -> bool:
        return self.current >= len(self.steps) - 1

    @property
    def progress(self) -> float:
        if len(self.steps) < 2:
            return 1.0
        return self.current / (len(self.steps) - 1)

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "steps": self.steps,
            "current": self.current,
            "orientation": self.orientation,
            "progress": round(self.progress, 4),
        })
        return props


class WebView(Widget):
    """An embedded browser view.

    ``on_message`` receives ``postMessage`` calls from the page, so you can
    host a chart library or a rich editor and still drive it from Python.
    """

    _widget_type = "WebView"

    def __init__(
        self,
        url: Optional[str] = None,
        *,
        html: Optional[str] = None,
        javascript: bool = True,
        zoom: bool = False,
        on_load: Optional[Callable] = None,
        on_message: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if not url and not html:
            raise ValueError("WebView needs either url= or html=")
        self.url = url
        self.html = html
        self.javascript = javascript
        self.zoom = zoom
        if on_load is not None:
            self.event_handlers["load"] = on_load
        if on_message is not None:
            self.event_handlers["message"] = on_message

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "url": self.url,
            "html": self.html,
            "javascript": self.javascript,
            "zoom": self.zoom or None,
        }))
        return props


class VideoPlayer(Widget):
    """A native video surface with the standard media controls."""

    _widget_type = "VideoPlayer"

    def __init__(self, source: str = "", *, autoplay: bool = False,
                 loop: bool = False, muted: bool = False, controls: bool = True,
                 aspect_ratio: float = 16 / 9, on_complete: Optional[Callable] = None,
                 key: Optional[str] = None, **kwargs):
        super().__init__(key=key, **kwargs)
        self.source = str(source)
        self.autoplay = autoplay
        self.loop = loop
        self.muted = muted
        self.controls = controls
        self.aspect_ratio = float(aspect_ratio)
        if on_complete is not None:
            self.event_handlers["complete"] = on_complete

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "source": self.source,
            "autoplay": self.autoplay,
            "loop": self.loop,
            "muted": self.muted,
            "controls": self.controls,
            "aspectRatio": round(self.aspect_ratio, 4),
        })
        return props


class Chart(Widget):
    """A lightweight line/bar/pie chart drawn natively on a Canvas.

    ``series`` is a list of numbers, or a list of ``{"label", "value"}`` dicts.
    """

    _widget_type = "Chart"
    KINDS = ("line", "bar", "pie", "area")

    def __init__(
        self,
        series: Optional[list] = None,
        *,
        kind: str = "line",
        labels: Optional[list[str]] = None,
        colors: Optional[list[str]] = None,
        height: float = 180,
        show_grid: bool = True,
        show_values: bool = False,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        if kind not in self.KINDS:
            raise ValueError(f"Chart kind must be one of {self.KINDS}")
        self.kind = kind
        self.height = float(height)
        self.show_grid = show_grid
        self.show_values = show_values
        self.colors = list(colors or [Colors.PRIMARY, Colors.TEAL, Colors.ACCENT,
                                      Colors.PINK, Colors.GREEN])
        raw = list(series or [])
        self.values: list[float] = []
        self.labels: list[str] = list(labels or [])
        for index, point in enumerate(raw):
            if isinstance(point, dict):
                self.values.append(float(point.get("value", 0)))
                if not labels:
                    self.labels.append(str(point.get("label", index)))
            elif isinstance(point, (list, tuple)) and len(point) == 2:
                self.values.append(float(point[1]))
                if not labels:
                    self.labels.append(str(point[0]))
            else:
                self.values.append(float(point))

    @property
    def max_value(self) -> float:
        return max(self.values) if self.values else 0.0

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "kind": self.kind,
            "values": self.values,
            "labels": self.labels,
            "colors": self.colors,
            "height": self.height,
            "showGrid": self.show_grid,
            "showValues": self.show_values,
            "max": self.max_value,
        })
        return props
