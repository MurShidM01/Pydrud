"""
Lists: tiles and accordions.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence, Union
from pydrud.core.state import UNSET, read_reactive
from pydrud.widgets.base import Widget
from pydrud.widgets.layout import Column
from pydrud.widgets.material._common import _clean

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
        # Keys given by the caller are preserved — they are how events and
        # patches find the widget again.
        if isinstance(leading, Widget):
            if leading._auto_key:
                leading.key = f"{self.key}_leading"
                leading._auto_key = False
            self.children.append(leading)
        elif leading:
            self.leading_icon = str(leading)
        if isinstance(trailing, Widget):
            if trailing._auto_key:
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


class ExpansionPanel:
    """One header/body pair for :class:`ExpansionPanelList`.

    A plain value object, not a widget — it carries the *specification* of a
    panel; the list turns each one into a native :class:`ExpansionTile`.
    """

    __slots__ = ("title", "children", "subtitle", "leading", "expanded", "key")

    def __init__(self, title: str, *, children: Optional[list[Widget]] = None,
                 subtitle: Optional[str] = None,
                 leading: Optional[str] = None, expanded: bool = False,
                 key: Optional[str] = None):
        self.title = str(title)
        self.children = list(children or [])
        self.subtitle = subtitle
        self.leading = leading
        self.expanded = bool(expanded)
        self.key = key

    def __repr__(self) -> str:
        return (f"ExpansionPanel({self.title!r}, "
                f"{len(self.children)} children, expanded={self.expanded})")


class ExpansionPanelList(Column):
    """Flutter's ``ExpansionPanelList`` — a column of collapsible panels.

    Each :class:`ExpansionPanel` becomes a native ``ExpansionTile``, so the
    accordion needs no native code::

        ExpansionPanelList([
            ExpansionPanel("Shipping", children=[Text("3-5 days")]),
            ExpansionPanel("Returns",  children=[Text("30 days")]),
        ])

    With ``accordion=True`` at most one panel is open at a time. The list
    reads ``open_index`` — an int, a ``State``, a ``Computed`` or a callable
    — on every build and reports the tapped index through ``on_change``, so
    the app owns the state and one ``page.update()`` moves the highlight::

        open_panel = State(0)

        def main(page):
            def choose(event):
                open_panel.value = event["index"]
                page.update()

            page.add(ExpansionPanelList(
                panels, accordion=True, open_index=open_panel,
                on_change=choose))
    """

    #: Serialises as a plain ``Column`` — it *is* one, so the renderer needs
    #: to know nothing new about it.
    _widget_type = "Column"

    def __init__(self, panels: Optional[Sequence[ExpansionPanel]] = None, *,
                 accordion: bool = False, open_index: Any = UNSET,
                 on_change: Optional[Callable] = None, spacing: float = 0,
                 key: Optional[str] = None, style: Optional[dict] = None,
                 expand: Optional[int] = None, visible: bool = True,
                 **kwargs):
        self._panels = list(panels or [])
        self.accordion = bool(accordion)
        self._open_index = open_index
        self._on_change = on_change
        super().__init__(children=[], spacing=spacing, key=key, style=style,
                         expand=expand, visible=visible, **kwargs)
        self.rebuild()

    # ── public helpers ───────────────────────────────────────────────────

    @property
    def panels(self) -> list:
        return list(self._panels)

    def add(self, *panels: ExpansionPanel) -> "ExpansionPanelList":
        self._panels.extend(panels)
        self.rebuild()
        return self

    def open_index(self) -> Any:
        """The index currently reported open (``None`` when none is)."""
        if not self.accordion:
            return None
        current = read_reactive(self._open_index, default=UNSET)
        return None if current is UNSET else current

    # ── internals ────────────────────────────────────────────────────────

    def _is_open(self, index: int, panel: ExpansionPanel) -> bool:
        if self.accordion:
            current = self.open_index()
            if current is not None:
                return current == index
        return panel.expanded

    def _handler(self, index: int) -> Callable:
        def on_expand(event):
            if self._on_change is None:
                return
            payload = {"index": index}
            payload.update(dict(event) if isinstance(event, dict) else {})
            self._on_change(payload)

        return on_expand

    def rebuild(self) -> None:
        """Re-materialise the tiles from the panels and the current state."""
        self.children = [
            ExpansionTile(
                panel.title,
                children=panel.children,
                subtitle=panel.subtitle,
                leading=panel.leading,
                expanded=self._is_open(index, panel),
                on_expand=self._handler(index),
                key=panel.key or f"{self.key}.panel{index}",
            )
            for index, panel in enumerate(self._panels)
        ]

    def unwrap(self) -> Widget:
        # ``open_index`` may be a live State, so the panels are re-evaluated
        # on every serialisation — exactly like every other responsive or
        # state-driven composite in Pydrud.
        self.rebuild()
        return self
