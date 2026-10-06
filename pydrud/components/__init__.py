"""
Composite widgets built from the public API — no native code required.

Every widget here is a *composition* of the primitives Pydrud already
ships (``Row``/``Column``/``Container``/``Card``/``Text``/``Icon``/…). They
exist so the catalogue can grow in pure Python: the community can add a
``pydrud.components``-style package without forking the framework or
touching the generated Java (PYDRUD §15.3).

::

    from pydrud.components import StatBlock, StatRow, SectionLabel

    Column(children=[
        SectionLabel("Today"),
        StatRow([
            StatBlock("Steps", "8,412", icon="trending_up"),
            StatBlock("Goal", "78%", icon="verified"),
        ]),
    ])

Because they are ordinary widgets, they diff, key and animate exactly like
the built-ins.
"""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from pydrud.widgets.base import Widget
from pydrud.widgets.basic import Button, Icon, LinearProgress, Text
from pydrud.widgets.layout import Card, Column, Container, Row
from pydrud.widgets.presets import Gap
from pydrud.widgets.theme import Colors, Icons, Spacing, Theme
from pydrud.widgets.tokens import Tokens

__all__ = [
    "EmptyPlaceholder",
    "FormRow",
    "GlassPanel",
    "InfoRow",
    "KeyValueRow",
    "PillButton",
    "ProgressRow",
    "SectionLabel",
    "StatBlock",
    "StatRow",
    "Toolbar",
]


def _gap(size: float) -> Gap:
    return Gap(size)


class SectionLabel(Row):
    """A small, muted section title with an optional trailing action.

    ::

        SectionLabel("Recent activity", action=Button("See all", variant="text"))
    """

    def __init__(self, text: str, *, action: Optional[Widget] = None,
                 uppercase: bool = True, **kwargs):
        label = text.upper() if uppercase else text
        children: list = [
            Text(label, size=12, weight=700, color=Theme.text_secondary,
                 expand=1),
        ]
        if action is not None:
            children.append(action)
        super().__init__(children=children, vertical_alignment="center",
                         spacing=8, **kwargs)


class StatBlock(Column):
    """A single stat: a large value over a muted label, with an optional icon.

    ::

        StatBlock("Steps", "8,412", icon="trending_up", color=Colors.GREEN)
    """

    def __init__(self, label: str, value: str, *, icon: Optional[str] = None,
                 color: Optional[str] = None, align: str = "start",
                 **kwargs):
        color = color or Theme.primary
        header: list = []
        if icon:
            header.append(Icon(icon, size=18, color=color))
        header.append(Text(value, size=22, weight=700, color=Theme.text))
        children: list = [
            Row(children=header, spacing=6, vertical_alignment="center"),
            Text(label, size=12, color=Theme.text_secondary),
        ]
        super().__init__(children=children, spacing=4,
                         horizontal_alignment=align, **kwargs)


class StatRow(Row):
    """A horizontal strip of equal-width :class:`StatBlock` values.

    Each block is weighted (``expand=1``) so the strip never collapses —
    the layout PB-007 made easy to get wrong.
    """

    def __init__(self, stats: Sequence[Widget], *, spacing: float = 12,
                 **kwargs):
        children = [s if getattr(s, "expand", None) else _weight(s)
                    for s in stats]
        super().__init__(children=children, spacing=spacing,
                         vertical_alignment="center", **kwargs)


def _weight(widget: Widget) -> Widget:
    widget.expand = widget.expand or 1
    return widget


class Toolbar(Row):
    """A leading widget, a title and trailing actions on one line.

    ::

        Toolbar(title="Inbox", leading=Icon("menu"), actions=[Icon("search")])
    """

    def __init__(self, *, title: str = "", leading: Optional[Widget] = None,
                 actions: Optional[Sequence[Widget]] = None,
                 spacing: float = 8, **kwargs):
        children: list = []
        if leading is not None:
            children.append(leading)
        children.append(Text(title, size=18, weight=600, expand=1,
                             color=Theme.text))
        children.extend(actions or ())
        super().__init__(children=children, spacing=spacing,
                         vertical_alignment="center", **kwargs)


class GlassPanel(Container):
    """A translucent, rounded panel — the "frosted glass" surface.

    ``opacity`` is applied to the fill colour so the panel reads as glass
    over a gradient background.
    """

    def __init__(self, *, child: Optional[Widget] = None,
                 bg: Optional[str] = None, opacity: float = 0.72,
                 border_radius: Optional[float] = None,
                 padding=None, **kwargs):
        fill = Colors.with_opacity(bg or Theme.surface, opacity)
        super().__init__(
            child=child,
            bg=fill,
            border_radius=(Tokens.radius_card if border_radius is None
                           else border_radius),
            padding=(Spacing.MD if padding is None else padding),
            **kwargs,
        )


class KeyValueRow(Row):
    """A label on the left and its value on the right, baseline-aligned."""

    def __init__(self, label: str, value: str, *, mono: bool = False,
                 value_color: Optional[str] = None, **kwargs):
        super().__init__(children=[
            Text(label, size=14, color=Theme.text_secondary, expand=1),
            Text(value, size=14, weight=600,
                 color=value_color or Theme.text,
                 family="monospace" if mono else None),
        ], spacing=12, vertical_alignment="center", **kwargs)


class InfoRow(Row):
    """An icon beside a title and optional subtitle — a settings/list row."""

    def __init__(self, icon: str, title: str, *, subtitle: str = "",
                 icon_color: Optional[str] = None,
                 trailing: Optional[Widget] = None, **kwargs):
        texts: list = [Text(title, size=15, weight=500, color=Theme.text)]
        if subtitle:
            texts.append(Text(subtitle, size=12, color=Theme.text_secondary))
        children: list = [
            Icon(icon, size=22, color=icon_color or Theme.primary),
            Column(children=texts, spacing=2, expand=1),
        ]
        if trailing is not None:
            children.append(trailing)
        super().__init__(children=children, spacing=14,
                         vertical_alignment="center", **kwargs)


class FormRow(Column):
    """A labelled control with an optional helper line.

    ::

        FormRow("Email", TextField(hint="you@example.com"),
                helper="We never share it.")
    """

    def __init__(self, label: str, control: Widget, *, helper: str = "",
                 **kwargs):
        children: list = [
            Text(label, size=13, weight=600, color=Theme.text_secondary),
            control,
        ]
        if helper:
            children.append(Text(helper, size=12, color=Theme.text_secondary))
        super().__init__(children=children, spacing=6, **kwargs)


class ProgressRow(Column):
    """A label, a progress bar and a percentage on one block.

    ``value`` is a fraction in ``0.0 – 1.0`` (like :class:`~pydrud.ProgressBar`).
    """

    def __init__(self, label: str, value: float, *,
                 color: Optional[str] = None, **kwargs):
        fraction = max(0.0, min(1.0, float(value)))
        super().__init__(children=[
            Row(children=[
                Text(label, size=13, color=Theme.text, expand=1),
                Text(f"{round(fraction * 100)}%", size=13, weight=600,
                     color=Theme.text_secondary),
            ], vertical_alignment="center"),
            LinearProgress(fraction, color=color or Theme.primary),
        ], spacing=6, **kwargs)


class PillButton(Button):
    """A pill-shaped tonal button with an optional leading icon."""

    def __init__(self, text: str, *, icon: Optional[str] = None,
                 variant: str = "tonal", **kwargs):
        super().__init__(text, icon=icon, variant=variant, pill=True, **kwargs)


class EmptyPlaceholder(Card):
    """A centred empty-state card: icon, title, message and an action.

    A richer alternative to :class:`~pydrud.EmptyState`, wrapped in a card
    so it reads as a deliberate placeholder rather than a broken screen.
    """

    def __init__(self, title: str = "Nothing here yet", *,
                 message: str = "", icon: str = Icons.INBOX,
                 action: Optional[str] = None,
                 on_action: Optional[Callable] = None, **kwargs):
        children: list = [
            Icon(icon, size=40, color=Theme.text_secondary),
            _gap(8),
            Text(title, size=16, weight=600, color=Theme.text,
                 text_align="center"),
        ]
        if message:
            children.append(_gap(4))
            children.append(Text(message, size=13, color=Theme.text_secondary,
                                 text_align="center"))
        if action:
            children.append(_gap(12))
            children.append(Button(action, variant="tonal",
                                   on_click=on_action))
        body = Column(children=children, spacing=0,
                      horizontal_alignment="center")
        super().__init__(child=body, padding=Spacing.LG, **kwargs)
