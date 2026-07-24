"""
Basic/interactive widgets: Text, Button, TextField, Image, Icon, Checkbox, Switch.
"""

from __future__ import annotations
from typing import Optional, Union

from pydrud.widgets.base import Widget
from pydrud.widgets.styling import FontStyle, Style


class Text(Widget):
    """Read-only text label."""

    _widget_type = "Text"

    def __init__(
        self,
        value: str = "",
        *,
        size: Optional[float] = None,
        color: Optional[str] = None,
        weight: Optional[int] = None,
        italic: bool = False,
        family: Optional[str] = None,
        text_align: Optional[str] = None,
        max_lines: Optional[int] = None,
        overflow: str = "ellipsis",
        selectable: bool = False,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self._value = str(value)
        if size or color or weight or italic or family:
            fs = FontStyle(size=size, color=color, weight=weight, italic=italic, family=family)
            self.style.setdefault("font", {}).update(fs.to_dict())
        if text_align:
            self.style["textAlign"] = text_align
        if max_lines is not None:
            self.style["maxLines"] = max_lines
        if overflow != "ellipsis":
            self.style["overflow"] = overflow
        if selectable:
            self.style["selectable"] = True

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, v: str):
        self._value = str(v)

    def _serialise_props(self) -> dict:
        return {"value": self._value}


class Button(Widget):
    """A clickable button (rendered as a Material Button on Android)."""

    _widget_type = "Button"

    def __init__(
        self,
        text: str = "",
        *,
        icon: Optional[str] = None,
        variant: str = "filled",   # "filled", "outlined", "text"
        color: Optional[str] = None,
        bg_color: Optional[str] = None,
        size: Optional[str] = None,  # "sm", "md", "lg"
        disabled: bool = False,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self._text = text
        self.style["variant"] = variant
        if icon:
            self.style["icon"] = icon
        if color:
            self.style.setdefault("font", {})["color"] = color
        if bg_color:
            self.style["bg"] = bg_color
        if size:
            self.style["buttonSize"] = size
        if disabled:
            self.style["disabled"] = True

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, v: str):
        self._text = v

    def _serialise_props(self) -> dict:
        return {"text": self._text}


class TextField(Widget):
    """Single- or multi-line text input."""

    _widget_type = "TextField"

    def __init__(
        self,
        value: str = "",
        *,
        hint: Optional[str] = None,
        label: Optional[str] = None,
        multiline: bool = False,
        max_lines: Optional[int] = None,
        password: bool = False,
        read_only: bool = False,
        keyboard: Optional[str] = None,  # "text", "number", "email", "phone", "url"
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self._value = value
        self._hint = hint
        self._label = label
        if multiline:
            self.style["multiline"] = True
        if max_lines is not None:
            self.style["maxLines"] = max_lines
        if password:
            self.style["password"] = True
        if read_only:
            self.style["readOnly"] = True
        if keyboard:
            self.style["keyboard"] = keyboard

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, v: str):
        self._value = v

    def _serialise_props(self) -> dict:
        d = {"value": self._value}
        if self._hint:
            d["hint"] = self._hint
        if self._label:
            d["label"] = self._label
        return d


class Image(Widget):
    """Displays an image from assets or a URL."""

    _widget_type = "Image"

    def __init__(
        self,
        src: str = "",
        *,
        fit: Optional[str] = None,   # "cover", "contain", "fill", "fitWidth", "fitHeight", "none"
        width: Optional[Union[float, str]] = None,
        height: Optional[Union[float, str]] = None,
        border_radius: Optional[float] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self._src = src
        if fit:
            self.style["fit"] = fit
        if width is not None:
            self.style["width"] = width
        if height is not None:
            self.style["height"] = height
        if border_radius is not None:
            self.style["borderRadius"] = border_radius

    @property
    def src(self) -> str:
        return self._src

    @src.setter
    def src(self, v: str):
        self._src = v

    def _serialise_props(self) -> dict:
        return {"src": self._src}


class Icon(Widget):
    """A Material icon glyph."""

    _widget_type = "Icon"

    def __init__(
        self,
        name: str = "star",
        *,
        size: Optional[float] = None,
        color: Optional[str] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self._icon_name = name
        if size:
            self.style.setdefault("font", {})["size"] = size
        if color:
            self.style.setdefault("font", {})["color"] = color

    def _serialise_props(self) -> dict:
        return {"name": self._icon_name}


class Checkbox(Widget):
    """A checkbox with a label."""

    _widget_type = "Checkbox"

    def __init__(
        self,
        label: str = "",
        *,
        checked: bool = False,
        tristate: bool = False,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self._label = label
        self._checked = checked
        if tristate:
            self.style["tristate"] = True

    @property
    def checked(self) -> bool:
        return self._checked

    @checked.setter
    def checked(self, v: bool):
        self._checked = v

    @property
    def label(self) -> str:
        return self._label

    def _serialise_props(self) -> dict:
        return {"label": self._label, "checked": self._checked}


class Switch(Widget):
    """A toggle switch with a label."""

    _widget_type = "Switch"

    def __init__(
        self,
        label: str = "",
        *,
        active: bool = False,
        active_color: Optional[str] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self._label = label
        self._active = active
        if active_color:
            self.style["activeColor"] = active_color

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, v: bool):
        self._active = v

    @property
    def label(self) -> str:
        return self._label

    def _serialise_props(self) -> dict:
        return {"label": self._label, "active": self._active}
