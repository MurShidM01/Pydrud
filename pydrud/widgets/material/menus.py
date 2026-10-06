"""
Overflow menus: MenuItem, MenuDivider and PopupMenu.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence
from pydrud.widgets.base import Widget
from pydrud.widgets.theme import Icons
from pydrud.widgets.material._common import _clean

class MenuItem:
    """One entry in a :class:`PopupMenu`.

    A plain value object, not a widget — it carries the *specification* of an
    entry; the menu turns each one into a native ``MenuItem``.

    ::

        MenuItem("Rename", icon=Icons.EDIT)
        MenuItem("Bold", checkable=True, checked=True)
        MenuItem("Delete", icon=Icons.DELETE, danger=True)
        MenuItem("Share", submenu=[MenuItem("Copy link"), MenuItem("Email")])
    """

    __slots__ = ("label", "icon", "value", "enabled", "checked", "checkable",
                 "danger", "divider", "submenu", "key")

    def __init__(
        self,
        label: str = "",
        *,
        icon: Optional[str] = None,
        value: Optional[str] = None,
        enabled: bool = True,
        checked: bool = False,
        checkable: bool = False,
        danger: bool = False,
        divider: bool = False,
        submenu: Optional[Sequence["MenuItem"]] = None,
        key: Optional[str] = None,
    ):
        self.label = str(label)
        self.icon = icon
        # ``value`` is what the ``select`` event reports; it defaults to the
        # label, so an app that only cares about names needs no extra wiring.
        self.value = self.label if value is None else str(value)
        self.enabled = bool(enabled)
        self.checked = bool(checked)
        # A checked item is implicitly checkable — that is the only way the
        # tick can ever show, so requiring both would be a footgun.
        self.checkable = bool(checkable) or self.checked
        self.danger = bool(danger)
        self.divider = bool(divider)
        self.submenu = [_as_menu_item(entry) for entry in (submenu or [])]
        self.key = key

    def to_dict(self) -> dict:
        if self.divider:
            return {"divider": True}
        data = _clean({
            "label": self.label,
            "icon": self.icon,
            "value": self.value,
            "enabled": None if self.enabled else False,
            "checked": self.checked or None,
            "checkable": self.checkable or None,
            "danger": self.danger or None,
        })
        if self.submenu:
            data["submenu"] = [entry.to_dict() for entry in self.submenu]
        return data

    def __repr__(self) -> str:
        if self.divider:
            return "MenuDivider()"
        return f"MenuItem({self.label!r})"


def MenuDivider() -> MenuItem:
    """A separator between groups of menu entries (a divider :class:`MenuItem`)."""
    return MenuItem(divider=True)


def _as_menu_item(item) -> MenuItem:
    """Coerce a label, dict, tuple or :class:`MenuItem` into a ``MenuItem``.

    ``PopupMenu(["Open", ("Share", Icons.SHARE), {"label": "Delete"}])`` and
    the fully explicit ``[MenuItem("Open")]`` are interchangeable.
    """
    if isinstance(item, MenuItem):
        return item
    if isinstance(item, dict):
        return MenuItem(**item)
    if isinstance(item, (tuple, list)):
        if not item:
            return MenuItem()
        label = item[0]
        icon = item[1] if len(item) > 1 else None
        value = item[2] if len(item) > 2 else None
        return MenuItem(str(label), icon=icon, value=value)
    return MenuItem(str(item))


class PopupMenu(Widget):
    """An overflow menu anchored to its trigger (native ``PopupMenu``).

    Tapping the trigger opens the menu; choosing an entry fires
    ``on_select`` with ``event["index"]`` (the entry's position) and
    ``event["value"]`` (its value, the label by default)::

        PopupMenu(
            [MenuItem("Rename", icon=Icons.EDIT),
             MenuItem("Duplicate", icon=Icons.COPY),
             MenuDivider(),
             MenuItem("Delete", icon=Icons.DELETE, danger=True)],
            on_select=lambda e: remove() if e["value"] == "Delete" else None,
        )

    By default the trigger is a 48dp overflow (⋮) button. Pass ``trigger=``
    to anchor the menu to your own widget instead — a ``ListTile``, an
    ``IconButton``, an ``Avatar``. An entry carrying ``submenu=`` becomes a
    real native submenu; a ``MenuDivider()`` separates two groups.
    """

    _widget_type = "PopupMenu"

    def __init__(
        self,
        items: Optional[Sequence[Any]] = None,
        *,
        trigger: Optional[Widget] = None,
        icon: str = Icons.MORE_VERT,
        label: Optional[str] = None,
        item_icons: bool = True,
        color: Optional[str] = None,
        on_select: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.items: list[MenuItem] = [_as_menu_item(i) for i in (items or [])]
        self.icon = icon
        self.label = label
        self.item_icons = bool(item_icons)
        self.color = color
        if trigger is not None:
            if trigger._auto_key:
                trigger.key = f"{self.key}_trigger"
                trigger._auto_key = False
            self.children = [trigger]
        if on_select is not None:
            self.event_handlers["select"] = on_select

    # ── behaviour ───────────────────────────────────────────────────────

    def add(self, *items) -> "PopupMenu":
        """Append menu entries (chainable)."""
        self.items.extend(_as_menu_item(item) for item in items)
        return self

    @property
    def has_custom_trigger(self) -> bool:
        """Whether a caller-supplied trigger is used instead of the default icon."""
        return bool(self.children)

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "items": [item.to_dict() for item in self.items],
            # With a custom trigger the native side renders no default icon,
            # so the icon/label hints are dropped rather than sent unused.
            "icon": None if self.children else self.icon,
            "label": None if self.children else self.label,
            "customTrigger": True if self.children else None,
            "itemIcons": None if self.item_icons else False,
            "color": self.color,
        }))
        return props


#: Flutter spells this ``PopupMenuButton``; Material 3 uses ``DropdownMenu``
#: for the anchored variant. All three build the same native node.
PopupMenuButton = PopupMenu
DropdownMenu = PopupMenu
