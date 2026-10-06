"""Flutter-style convenience widgets built from Pydrud's native primitives.

These classes deliberately reuse renderer-backed widget types rather than
inventing one-off protocol nodes.  For example, :class:`Expanded` serialises
as a ``Container`` with a flex value and :class:`SwitchListTile` serialises as
a native ``ListTile`` containing a native ``Switch``.  They are therefore
fully compatible with diffing, testing, theming and older Android runtimes.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence, Union

from pydrud.widgets.base import Widget
from pydrud.widgets.basic import (
    Button, Checkbox, Icon, IconButton, Image, Radio, Switch, Text,
)
from pydrud.widgets.layout import (
    Card, Column, Container, Divider, GridView, ListView, Row, SizedBox,
)
from pydrud.widgets.material import (
    AssistChip, Avatar, CircularProgress, FilterChip, ListTile,
)
from pydrud.widgets.styling import Border
from pydrud.widgets.theme import Colors, Icons, Theme
from pydrud.widgets.tokens import Tokens

Size = Union[float, int, str]


# ── Layout ──────────────────────────────────────────────────────────────────


class Expanded(Container):
    """Make ``child`` consume the remaining space on a Row or Column axis."""

    def __init__(self, child: Optional[Widget] = None, *, flex: int = 1,
                 **kwargs):
        if flex < 1:
            raise ValueError("Expanded flex must be at least 1")
        super().__init__(child=child, expand=int(flex), **kwargs)


class Flexible(Container):
    """A flex child which may use the remaining Row/Column space."""

    def __init__(self, child: Optional[Widget] = None, *, flex: int = 1,
                 **kwargs):
        if flex < 1:
            raise ValueError("Flexible flex must be at least 1")
        super().__init__(child=child, expand=int(flex), **kwargs)


class Flex(Widget):
    """Flutter's ``Flex``: a :class:`Row` or :class:`Column` chosen by axis.

    ``Row`` and ``Column`` are the two axes of the same layout, so a widget
    that wants to switch between them (a responsive card, a segmented
    toolbar) had to duplicate its whole child list for each branch.
    ``Flex`` picks the axis at construction time and delegates::

        Flex(direction="horizontal", children=[a, b], spacing=12)
        Flex(direction="vertical", children=[a, b], main_alignment="center")

    ``direction`` accepts Flutter's ``Axis`` spelling as well as the words
    the rest of Pydrud uses (``"row"``/``"column"``, ``"x"``/``"y"``).
    ``main_alignment``/``cross_alignment`` are Flutter's
    ``mainAxisAlignment``/``crossAxisAlignment``; the Pydrud spellings
    (``horizontal_alignment``/``vertical_alignment``) work too.

    The result serialises as a plain ``Row``/``Column``, so it diffs,
    tests and themes exactly like the widget it stands for.
    """

    _widget_type = "Flex"

    #: Accepted ``direction`` spellings -> the axis they name.
    AXES = {
        "horizontal": "horizontal", "row": "horizontal", "x": "horizontal",
        "vertical": "vertical", "column": "vertical", "y": "vertical",
    }

    def __init__(self, *, direction: str = "horizontal",
                 children: Optional[list[Widget]] = None, spacing: float = 0,
                 main_axis_size: Optional[str] = None,
                 cross_axis_size: Optional[str] = None,
                 main_alignment: Optional[str] = None,
                 cross_alignment: Optional[str] = None,
                 horizontal_alignment: Optional[str] = None,
                 vertical_alignment: Optional[str] = None,
                 key: Optional[str] = None, style: Optional[dict] = None,
                 expand: Optional[int] = None, visible: bool = True,
                 scroll: bool = False, **kwargs):
        super().__init__(key=key, style=style, expand=expand,
                         visible=visible, **kwargs)
        axis = self.AXES.get(str(direction).strip().lower())
        if axis is None:
            raise ValueError(
                f"direction must be one of {sorted(self.AXES)}, "
                f"got {direction!r}")
        self.direction = axis
        self._items = list(children or [])
        self._spacing = spacing
        self._main_axis_size = main_axis_size
        self._cross_axis_size = cross_axis_size
        # Flutter's names win when both are given; the Pydrud spellings are
        # accepted because every other layout widget uses them.
        self._main_alignment = (main_alignment if main_alignment is not None
                                else (horizontal_alignment
                                      if axis == "horizontal"
                                      else vertical_alignment))
        self._cross_alignment = (cross_alignment if cross_alignment is not None
                                 else (vertical_alignment
                                       if axis == "horizontal"
                                       else horizontal_alignment))
        self._scroll = scroll
        self.rebuild()

    @property
    def is_horizontal(self) -> bool:
        return self.direction == "horizontal"

    def add(self, *widgets: Widget) -> "Flex":
        self._items.extend(widgets)
        self.rebuild()
        return self

    def rebuild(self) -> None:
        """(Re)build the underlying Row/Column from the current children."""
        builder = Row if self.is_horizontal else Column
        # Main axis is the direction; the other alignment names the cross one.
        if self.is_horizontal:
            alignments = {"horizontal_alignment": self._main_alignment,
                          "vertical_alignment": self._cross_alignment}
        else:
            alignments = {"vertical_alignment": self._main_alignment,
                          "horizontal_alignment": self._cross_alignment}
        alignments = {k: v for k, v in alignments.items() if v is not None}
        self.children = [builder(
            key=f"{self.key}._flex",
            children=self._items,
            spacing=self._spacing,
            main_axis_size=self._main_axis_size,
            cross_axis_size=self._cross_axis_size,
            style=dict(self.style),
            expand=self.expand,
            visible=self.visible,
            scroll=self._scroll,
            **alignments,
            **self._extra,
        )]

    def unwrap(self) -> Widget:
        self.rebuild()
        return self.children[0]


class FractionallySizedBox(Container):
    """Size a child as a fraction of its available width and/or height.

    Factors are expressed as values between zero and one.  ``None`` leaves
    that axis unconstrained, matching Flutter's FractionallySizedBox API.
    The factors are kept in the serialized style so the Android renderer can
    resolve them against the parent at layout time.
    """

    def __init__(self, child: Optional[Widget] = None, *,
                 width_factor: Optional[float] = None,
                 height_factor: Optional[float] = None,
                 alignment: Optional[str] = None, **kwargs):
        for name, value in (("width_factor", width_factor),
                            ("height_factor", height_factor)):
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        style = dict(kwargs.pop("style", {}) or {})
        if width_factor is not None:
            style["widthFactor"] = float(width_factor)
        if height_factor is not None:
            style["heightFactor"] = float(height_factor)
        super().__init__(child=child, alignment=alignment, style=style,
                         **kwargs)


class FittedBox(Container):
    """Scale and position a child to fit its available bounds.

    ``fit`` accepts the renderer's standard scale modes (for example
    ``contain``, ``cover``, ``fill`` and ``none``).
    """

    FITS = {"contain", "cover", "fill", "fit_width", "fit_height", "none"}

    def __init__(self, child: Optional[Widget] = None, *,
                 fit: str = "contain", alignment: Optional[str] = None,
                 **kwargs):
        if fit not in self.FITS:
            raise ValueError(f"fit must be one of {sorted(self.FITS)}")
        style = dict(kwargs.pop("style", {}) or {})
        style["fit"] = fit
        super().__init__(child=child, alignment=alignment, style=style,
                         **kwargs)


class MetricCard(Card):
    """A production dashboard metric with optional trend and icon.

    This is a composition of native ``Card``, ``Row`` and ``Text`` widgets,
    so it works on Android runtimes that predate the convenience class.
    """

    def __init__(self, label: str, value: Any, *,
                 trend: Optional[str] = None, icon: Optional[str] = None,
                 accent: Optional[str] = None, **kwargs):
        from pydrud.widgets.basic import Icon
        from pydrud.widgets.theme import Theme
        color = accent or Theme.primary
        top: list[Widget] = [Text(str(label), size=13, color=Theme.text_secondary)]
        if icon:
            top.append(Icon(icon, size=20, color=color))
        children: list[Widget] = [Row(children=top,
                                      horizontal_alignment="space_between")]
        children.append(Text(str(value), size=28, weight=700,
                             color=Theme.text))
        if trend:
            children.append(Text(str(trend), size=12, color=color))
        super().__init__(child=Column(children=children, spacing=6), **kwargs)


class DataTable(Card):
    """A responsive, scroll-friendly data table built from native layouts.

    ``rows`` may contain strings or arbitrary values.  The table validates
    row widths early and exposes a stable ``on_row_click(index)`` callback.
    """

    def __init__(self, columns: Sequence[str], rows: Sequence[Sequence[Any]], *,
                 on_row_click: Optional[Callable[[int], None]] = None,
                 striped: bool = False, compact: bool = False, **kwargs):
        from pydrud.widgets.theme import Theme
        labels = [str(column) for column in columns]
        if not labels:
            raise ValueError("DataTable requires at least one column")
        normalized = [list(row) for row in rows]
        if any(len(row) != len(labels) for row in normalized):
            raise ValueError("every DataTable row must match columns length")
        pad = 8 if compact else 14
        header = Row(children=[Text(label, weight=700, size=13,
                                     color=Theme.text) for label in labels],
                     spacing=pad, style={"tableRow": True, "header": True})
        body: list[Widget] = [header, Divider()]
        for index, row in enumerate(normalized):
            cells = [Text(str(value), size=13, color=Theme.text) for value in row]
            style = {"tableRow": True, "stripe": index % 2 == 1} if striped else {"tableRow": True}
            body.append(Row(children=cells, spacing=pad, style=style,
                            on_click=(lambda _event, i=index: on_row_click(i))
                            if on_row_click else None))
        super().__init__(child=Column(children=body, spacing=0, scroll=True), **kwargs)


class Timeline(Column):
    """A vertical activity timeline with native rows and dividers."""

    def __init__(self, events: Sequence[Any], *,
                 accent: Optional[str] = None, **kwargs):
        from pydrud.widgets.theme import Theme
        color = accent or Theme.primary
        children: list[Widget] = []
        for index, event in enumerate(events):
            if isinstance(event, dict):
                title = event.get("title", "")
                subtitle = event.get("subtitle", event.get("time", ""))
                icon = event.get("icon")
            else:
                title, subtitle = (list(event) + [""])[:2]
                icon = None
            marker = Text("●", size=18, color=color)
            content = Column(children=[Text(str(title), weight=600),
                                       Text(str(subtitle), size=12,
                                            color=Theme.text_secondary)],
                             spacing=3, expand=1)
            children.append(Row(children=[marker, content], spacing=12,
                                style={"timelineIndex": index, "timelineIcon": icon}))
            if index < len(events) - 1:
                children.append(Divider(indent=10, end_indent=10))
        super().__init__(children=children, spacing=0, **kwargs)


class Align(Container):
    """Place a child at a named :class:`~pydrud.Alignment` position."""

    def __init__(self, child: Optional[Widget] = None, *,
                 alignment: str = "center", **kwargs):
        super().__init__(child=child, alignment=alignment, **kwargs)


class ColoredBox(Container):
    """A lightweight box filled with ``color``."""

    def __init__(self, color: str, *, child: Optional[Widget] = None,
                 **kwargs):
        super().__init__(child=child, bg=color, **kwargs)


class DecoratedBox(Container):
    """A box with colour, border, radius and optional elevation."""

    def __init__(self, *, child: Optional[Widget] = None,
                 color: Optional[str] = None,
                 border: Optional[Union[Border, dict]] = None,
                 border_radius: Optional[float] = None,
                 elevation: Optional[float] = None, **kwargs):
        style = dict(kwargs.pop("style", {}) or {})
        if elevation is not None:
            style["elevation"] = float(elevation)
        super().__init__(child=child, bg=color, border=border,
                         border_radius=border_radius, style=style, **kwargs)


class ConstrainedBox(Container):
    """Apply minimum and maximum dimensions to a child."""

    def __init__(self, child: Optional[Widget] = None, *,
                 min_width: Optional[Size] = None,
                 max_width: Optional[Size] = None,
                 min_height: Optional[Size] = None,
                 max_height: Optional[Size] = None, **kwargs):
        style = dict(kwargs.pop("style", {}) or {})
        for name, value in (("minWidth", min_width), ("maxWidth", max_width),
                            ("minHeight", min_height),
                            ("maxHeight", max_height)):
            if value is not None:
                style[name] = value
        super().__init__(child=child, style=style, **kwargs)


class LimitedBox(ConstrainedBox):
    """Convenience max-width/max-height constraint."""

    def __init__(self, child: Optional[Widget] = None, *,
                 max_width: Optional[Size] = None,
                 max_height: Optional[Size] = None, **kwargs):
        super().__init__(child, max_width=max_width, max_height=max_height,
                         **kwargs)


class Gap(SizedBox):
    """A fixed horizontal, vertical or square layout gap."""

    def __init__(self, size: float = 0, *, axis: str = "vertical", **kwargs):
        if axis not in ("horizontal", "vertical", "both"):
            raise ValueError("Gap axis must be horizontal, vertical or both")
        super().__init__(width=size if axis != "vertical" else 0,
                         height=size if axis != "horizontal" else 0, **kwargs)


class VerticalDivider(Divider):
    """A vertical hairline for use inside a Row."""

    def __init__(self, *, color: Optional[str] = None,
                 thickness: Optional[float] = None,
                 height: Size = "match", **kwargs):
        super().__init__(color=color, thickness=thickness, **kwargs)
        width = self.style.get("thickness", 1)
        self.style.update({"width": width, "height": height})


class SingleChildScrollView(ListView):
    """A one-child vertical or horizontal native scroll view."""

    def __init__(self, child: Optional[Widget] = None, *,
                 horizontal: bool = False, **kwargs):
        super().__init__(children=[child] if child is not None else [],
                         horizontal=horizontal, **kwargs)


class Wrap(GridView):
    """Responsive wrapping layout backed by Pydrud's auto-column grid."""

    def __init__(self, *, children: Optional[list[Widget]] = None,
                 min_item_width: float = 120, max_columns: int = 6,
                 spacing: float = 8, **kwargs):
        if min_item_width <= 0:
            raise ValueError("Wrap min_item_width must be positive")
        super().__init__(children=children, columns=1, spacing=spacing, **kwargs)
        self.style["columns"] = "auto"
        self.style["minItemWidth"] = float(min_item_width)
        self.style["maxColumns"] = max(1, int(max_columns))


class ButtonBar(Row):
    """A trailing-aligned row for dialog/card actions."""

    def __init__(self, *, children: Optional[list[Widget]] = None,
                 spacing: float = 8, alignment: str = "end", **kwargs):
        super().__init__(children=children, spacing=spacing,
                         horizontal_alignment=alignment,
                         vertical_alignment="center", **kwargs)


# ── Typography and images ───────────────────────────────────────────────────


class Heading(Text):
    """Semantic-looking heading preset (levels 1 through 6)."""

    _SIZES = {1: 32, 2: 28, 3: 24, 4: 20, 5: 18, 6: 16}

    def __init__(self, value: str = "", *, level: int = 1, **kwargs):
        if level not in self._SIZES:
            raise ValueError("Heading level must be between 1 and 6")
        kwargs.setdefault("size", self._SIZES[level])
        kwargs.setdefault("weight", 700 if level <= 3 else 600)
        kwargs.setdefault("color", Theme.text)
        super().__init__(value, **kwargs)


class Title(Text):
    """20sp semibold title text."""

    def __init__(self, value: str = "", **kwargs):
        kwargs.setdefault("size", 20)
        kwargs.setdefault("weight", 600)
        kwargs.setdefault("color", Theme.text)
        super().__init__(value, **kwargs)


class Subtitle(Text):
    """Secondary 15sp supporting text."""

    def __init__(self, value: str = "", **kwargs):
        kwargs.setdefault("size", 15)
        kwargs.setdefault("color", Theme.text_secondary)
        super().__init__(value, **kwargs)


class Label(Text):
    """Compact semibold control/field label."""

    def __init__(self, value: str = "", **kwargs):
        kwargs.setdefault("size", 13)
        kwargs.setdefault("weight", 600)
        kwargs.setdefault("color", Theme.text)
        super().__init__(value, **kwargs)


class Caption(Text):
    """Small secondary caption text."""

    def __init__(self, value: str = "", **kwargs):
        kwargs.setdefault("size", 12)
        kwargs.setdefault("color", Theme.text_secondary)
        super().__init__(value, **kwargs)


class Link(Text):
    """Clickable text styled with the active theme colour."""

    def __init__(self, value: str = "", *,
                 on_click: Optional[Callable] = None, **kwargs):
        kwargs.setdefault("color", Theme.primary)
        kwargs.setdefault("weight", 600)
        super().__init__(value, on_click=on_click, **kwargs)


class NetworkImage(Image):
    """An image loaded from an HTTP(S) URL."""

    def __init__(self, url: str, **kwargs):
        if url and not url.lower().startswith(("http://", "https://")):
            raise ValueError("NetworkImage expects an http:// or https:// URL")
        super().__init__(url, **kwargs)


class AssetImage(Image):
    """An image loaded from the generated project's ``assets/`` directory."""

    def __init__(self, asset: str, **kwargs):
        super().__init__(asset, **kwargs)


class CircleImage(Image):
    """Square image clipped to a circle."""

    def __init__(self, src: str, *, size: float = 48, **kwargs):
        kwargs.setdefault("fit", "cover")
        kwargs.setdefault("width", size)
        kwargs.setdefault("height", size)
        kwargs.setdefault("border_radius", size / 2)
        super().__init__(src, **kwargs)


class Placeholder(Container):
    """Themed placeholder for media or content which has not loaded yet."""

    def __init__(self, label: str = "Content", *, icon: str = Icons.IMAGE,
                 width: Size = "match", height: Size = 120, **kwargs):
        child = Column(horizontal_alignment="center",
                       vertical_alignment="center", spacing=8, children=[
                           Icon(icon, size=28, color=Theme.text_secondary),
                           Caption(label),
                       ])
        style = dict(kwargs.pop("style", {}) or {})
        style.setdefault("border", Border(Theme.outline, 1).to_dict())
        super().__init__(child=child, width=width, height=height,
                         bg=Theme.surface_variant,
                         border_radius=Tokens.radius_card,
                         alignment="center", style=style, **kwargs)


# ── Material controls ───────────────────────────────────────────────────────


class SwitchListTile(ListTile):
    """List tile with its label on the left and a switch on the far right."""

    def __init__(self, title: str = "", *, value: bool = False,
                 subtitle: Optional[str] = None,
                 on_change: Optional[Callable] = None,
                 control_key: Optional[str] = None, **kwargs):
        control = Switch("", active=value, key=control_key, full_width=False)
        if on_change is not None:
            control.on_change(on_change)
        super().__init__(title, subtitle=subtitle, trailing=control, **kwargs)


class CheckboxListTile(ListTile):
    """List tile with a trailing native checkbox."""

    def __init__(self, title: str = "", *, value: bool = False,
                 subtitle: Optional[str] = None,
                 on_change: Optional[Callable] = None,
                 control_key: Optional[str] = None, **kwargs):
        control = Checkbox("", checked=value, key=control_key)
        if on_change is not None:
            control.on_change(on_change)
        super().__init__(title, subtitle=subtitle, trailing=control, **kwargs)


class RadioListTile(ListTile):
    """List tile with a trailing native radio control."""

    def __init__(self, title: str = "", *, value: Optional[str] = None,
                 group: str = "default", selected: bool = False,
                 subtitle: Optional[str] = None,
                 on_change: Optional[Callable] = None,
                 control_key: Optional[str] = None, **kwargs):
        control = Radio("", value=value or title, group=group,
                        selected=selected, key=control_key)
        if on_change is not None:
            control.on_change(on_change)
        super().__init__(title, subtitle=subtitle, trailing=control, **kwargs)


class ActionChip(AssistChip):
    """Flutter-compatible name for an assist/action chip."""


class ChoiceChip(FilterChip):
    """Flutter-compatible name for a single selectable filter chip."""


class CircleAvatar(Avatar):
    """Flutter-compatible name for Pydrud's native circular avatar."""


class BackButton(IconButton):
    """Standard back icon button."""

    def __init__(self, *, on_click: Optional[Callable] = None, **kwargs):
        super().__init__(Icons.BACK, text="", on_click=on_click, **kwargs)


class CloseButton(IconButton):
    """Standard close icon button."""

    def __init__(self, *, on_click: Optional[Callable] = None, **kwargs):
        super().__init__(Icons.CLOSE, text="", on_click=on_click, **kwargs)


class MenuButton(IconButton):
    """Standard overflow/menu icon button."""

    def __init__(self, *, on_click: Optional[Callable] = None, **kwargs):
        super().__init__(Icons.MORE_VERT, text="", on_click=on_click, **kwargs)


# ── Common app compositions ─────────────────────────────────────────────────


class SectionHeader(Row):
    """Section title with optional trailing action/widget."""

    def __init__(self, title: str, *, action: Optional[Widget] = None,
                 **kwargs):
        children: list[Widget] = [
            Text(title, size=13, weight=700, color=Theme.text_secondary,
                 expand=1),
        ]
        if action is not None:
            children.append(action)
        super().__init__(children=children, vertical_alignment="center",
                         **kwargs)


class EmptyState(Column):
    """Centered empty-content message with an optional action button."""

    def __init__(self, title: str = "Nothing here yet", *,
                 message: str = "", icon: str = Icons.INBOX,
                 action: Optional[str] = None,
                 on_action: Optional[Callable] = None, **kwargs):
        children: list[Widget] = [
            Icon(icon, size=44, color=Theme.text_secondary),
            Title(title, text_align="center"),
        ]
        if message:
            children.append(Subtitle(message, text_align="center"))
        if action:
            children.append(Button(action, variant="tonal",
                                   on_click=on_action))
        super().__init__(children=children, spacing=12,
                         horizontal_alignment="center", **kwargs)


class ErrorState(Column):
    """Centered error message with an optional retry action."""

    def __init__(self, title: str = "Something went wrong", *,
                 message: str = "", retry_label: Optional[str] = "Try again",
                 on_retry: Optional[Callable] = None, **kwargs):
        children: list[Widget] = [
            Icon(Icons.ERROR, size=44, color=Colors.ERROR),
            Title(title, text_align="center"),
        ]
        if message:
            children.append(Subtitle(message, text_align="center"))
        if retry_label:
            children.append(Button(retry_label, variant="tonal",
                                   on_click=on_retry))
        super().__init__(children=children, spacing=12,
                         horizontal_alignment="center", **kwargs)


class LoadingState(Column):
    """Centered circular progress indicator and status label."""

    def __init__(self, label: str = "Loading…", **kwargs):
        children: list[Widget] = [CircularProgress()]
        if label:
            children.append(Subtitle(label, text_align="center"))
        super().__init__(children=children, spacing=12,
                         horizontal_alignment="center", **kwargs)


class InfoCard(Card):
    """Icon, title and body arranged in a themed card."""

    def __init__(self, title: str, body: str = "", *,
                 icon: str = Icons.INFO, color: Optional[str] = None,
                 **kwargs):
        accent = color or Theme.primary
        content = Row(spacing=12, vertical_alignment="center", children=[
            Icon(icon, size=24, color=accent),
            Column(expand=1, spacing=4, children=[
                Text(title, size=15, weight=600, color=Theme.text),
                Text(body, size=13, color=Theme.text_secondary),
            ]),
        ])
        super().__init__(child=content, **kwargs)


class StatCard(Card):
    """Compact dashboard metric card."""

    def __init__(self, label: str, value: Union[str, int, float], *,
                 icon: Optional[str] = None, trend: Optional[str] = None,
                 **kwargs):
        children: list[Widget] = []
        if icon:
            children.append(Icon(icon, size=22, color=Theme.primary))
        children.extend([
            Caption(label),
            Text(str(value), size=28, weight=700, color=Theme.text),
        ])
        if trend:
            children.append(Text(trend, size=12, weight=600,
                                 color=Colors.SUCCESS if trend.startswith("+")
                                 else Theme.text_secondary))
        super().__init__(child=Column(spacing=6, children=children), **kwargs)


class SettingsTile(ListTile):
    """Settings row with an optional value or trailing control."""

    def __init__(self, title: str, *, value: Optional[str] = None,
                 leading: Optional[Union[str, Widget]] = Icons.SETTINGS,
                 trailing: Optional[Widget] = None, **kwargs):
        if trailing is None and value:
            trailing = Caption(value)
        super().__init__(title, leading=leading, trailing=trailing, **kwargs)


class NavigationTile(ListTile):
    """Tappable list row with a standard trailing chevron."""

    def __init__(self, title: str, *,
                 leading: Optional[Union[str, Widget]] = None, **kwargs):
        super().__init__(title, leading=leading,
                         trailing=Icons.CHEVRON_RIGHT, **kwargs)


class FormSection(Column):
    """Labelled vertical group for related form fields."""

    def __init__(self, title: str, *, children: Optional[list[Widget]] = None,
                 spacing: float = 12, **kwargs):
        section_children: list[Widget] = [Label(title)]
        section_children.extend(children or [])
        super().__init__(children=section_children, spacing=spacing, **kwargs)


__all__ = [
    "Expanded", "Flexible", "Flex", "FractionallySizedBox", "FittedBox", "Align",
    "MetricCard", "DataTable", "Timeline", "ColoredBox", "DecoratedBox",
    "ConstrainedBox", "LimitedBox", "Gap", "VerticalDivider",
    "SingleChildScrollView", "Wrap", "ButtonBar", "Heading", "Title",
    "Subtitle", "Label", "Caption", "Link", "NetworkImage", "AssetImage",
    "CircleImage", "Placeholder", "SwitchListTile", "CheckboxListTile",
    "RadioListTile", "ActionChip", "ChoiceChip", "CircleAvatar",
    "BackButton", "CloseButton", "MenuButton", "SectionHeader",
    "EmptyState", "ErrorState", "LoadingState", "InfoCard", "StatCard",
    "SettingsTile", "NavigationTile", "FormSection",
]
