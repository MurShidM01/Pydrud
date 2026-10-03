"""
Basic/interactive widgets: Text, Button, TextField, Image, Icon, Checkbox, Switch.
"""

from __future__ import annotations
from typing import Optional, Union

from pydrud.widgets.base import Widget
from pydrud.widgets.styling import FontStyle


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
    """A clickable button, rendered as a native Material button.

    Five variants, all with the platform ripple, press-scale and
    disabled states::

        Button("Save")                          # filled   (default)
        Button("Save", variant="tonal")         # soft tinted fill
        Button("Save", variant="outlined")      # hairline outline
        Button("Save", variant="text")          # label only
        Button("Save", variant="elevated")      # filled + shadow

    ``size`` is ``"sm" | "md" | "lg"`` (36 / 48 / 56 dp tall — ``md``
    already meets the 48 dp touch-target guideline), ``pill=True`` makes
    the corners fully round and ``full_width=True`` stretches the button
    to its parent.
    """

    _widget_type = "Button"

    VARIANTS = ("filled", "tonal", "outlined", "text", "elevated")

    def __init__(
        self,
        text: str = "",
        *,
        icon: Optional[str] = None,
        variant: str = "filled",
        color: Optional[str] = None,
        bg_color: Optional[str] = None,
        size: Optional[str] = None,  # "sm", "md", "lg"
        pill: bool = False,
        full_width: bool = False,
        disabled: bool = False,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        if variant not in self.VARIANTS:
            raise ValueError(
                f"Unknown button variant {variant!r}; expected one of "
                + ", ".join(self.VARIANTS)
            )
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
        if pill:
            self.style["pill"] = True
        if full_width:
            self.style.setdefault("width", "match")
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


class FilledButton(Button):
    """Convenience alias for ``Button(..., variant="filled")``."""

    def __init__(self, text: str = "", **kwargs):
        kwargs.setdefault("variant", "filled")
        super().__init__(text, **kwargs)


class TonalButton(Button):
    """Soft filled Material button."""

    def __init__(self, text: str = "", **kwargs):
        kwargs.setdefault("variant", "tonal")
        super().__init__(text, **kwargs)


class OutlinedButton(Button):
    """Hairline-outline Material button."""

    def __init__(self, text: str = "", **kwargs):
        kwargs.setdefault("variant", "outlined")
        super().__init__(text, **kwargs)


class TextButton(Button):
    """Text-only Material button."""

    def __init__(self, text: str = "", **kwargs):
        kwargs.setdefault("variant", "text")
        super().__init__(text, **kwargs)


class ElevatedButton(Button):
    """Filled button with native elevation."""

    def __init__(self, text: str = "", **kwargs):
        kwargs.setdefault("variant", "elevated")
        super().__init__(text, **kwargs)


class IconButton(Button):
    """Compact button that shows an icon and optional accessible label."""

    def __init__(self, icon: str = "star", text: str = "", **kwargs):
        kwargs.setdefault("variant", "text")
        kwargs.setdefault("icon", icon)
        super().__init__(text, **kwargs)


class TextField(Widget):
    """Single- or multi-line text input.

    Two looks, both with a focus-reactive fill and border::

        TextField(hint="Search")                       # filled (default)
        TextField(hint="Email", variant="outlined")    # outlined

    ``icon`` shows a leading glyph and ``accent`` overrides the focus
    colour; everything else follows :class:`pydrud.Theme`.
    """

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
        variant: str = "filled",         # "filled" | "outlined"
        icon: Optional[str] = None,
        accent: Optional[str] = None,
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
        if variant and variant != "filled":
            self.style["variant"] = variant
        if icon:
            self.style["icon"] = icon
        if accent:
            self.style["accent"] = accent
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


class SearchField(TextField):
    """Text field preset for search bars and filters."""

    def __init__(self, value: str = "", **kwargs):
        kwargs.setdefault("hint", "Search")
        kwargs.setdefault("keyboard", "text")
        kwargs.setdefault("icon", "search")
        super().__init__(value, **kwargs)


class EmailField(TextField):
    """Text field with the email keyboard and mail icon."""

    def __init__(self, value: str = "", **kwargs):
        kwargs.setdefault("keyboard", "email")
        kwargs.setdefault("icon", "email")
        super().__init__(value, **kwargs)


class PasswordField(TextField):
    """Password field with obscured input."""

    def __init__(self, value: str = "", **kwargs):
        kwargs.setdefault("password", True)
        kwargs.setdefault("icon", "lock")
        super().__init__(value, **kwargs)


class NumberField(TextField):
    """Text field using Android's numeric keyboard."""

    def __init__(self, value: str = "", **kwargs):
        kwargs.setdefault("keyboard", "number")
        super().__init__(value, **kwargs)


class PhoneField(TextField):
    """Text field using Android's phone keypad."""

    def __init__(self, value: str = "", **kwargs):
        kwargs.setdefault("keyboard", "phone")
        kwargs.setdefault("icon", "call")
        super().__init__(value, **kwargs)


class UrlField(TextField):
    """Text field using Android's URL keyboard."""

    def __init__(self, value: str = "", **kwargs):
        kwargs.setdefault("keyboard", "url")
        kwargs.setdefault("icon", "link")
        super().__init__(value, **kwargs)


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


class SvgPicture(Image):
    """An SVG image from assets or HTTPS.

    ``Image(src="logo.svg")`` automatically takes the same vector path; this
    named form makes a vector asset explicit and catches accidental bitmap
    filenames before they reach Android.
    """

    def __init__(self, src: str, **kwargs):
        clean = str(src).split("?", 1)[0].split("#", 1)[0].lower()
        if not clean.endswith(".svg"):
            raise ValueError("SvgPicture src must end in .svg")
        super().__init__(src, **kwargs)


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
    """A toggle switch with an optional label.

    Labelled switches fill the available row by default, placing the label at
    the start and the native toggle at the end (the Material/Flutter
    ``SwitchListTile`` convention). An unlabelled switch stays compact. Pass
    ``full_width=False`` to opt a labelled switch back into the compact form.
    """

    _widget_type = "Switch"

    def __init__(
        self,
        label: str = "",
        *,
        active: bool = False,
        active_color: Optional[str] = None,
        full_width: Optional[bool] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self._label = label
        self._active = active
        if full_width is None:
            full_width = bool(label)
        if full_width:
            self.style.setdefault("width", "match")
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


class ProgressBar(Widget):
    """A determinate or indeterminate progress indicator."""

    _widget_type = "ProgressBar"

    def __init__(
        self,
        value: Optional[float] = None,
        *,
        indeterminate: Optional[bool] = None,
        circular: bool = False,
        color: Optional[str] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self._value = 0.0 if value is None else float(value)
        self._indeterminate = (value is None) if indeterminate is None else bool(indeterminate)
        self.style["circular"] = circular
        if color:
            self.style["color"] = color

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float):
        self._value = float(v)
        self._indeterminate = False

    def _serialise_props(self) -> dict:
        return {"value": self._value, "indeterminate": self._indeterminate}


class LinearProgress(ProgressBar):
    """Alias for :class:`ProgressBar` with Material naming."""


class Slider(Widget):
    """A draggable value slider."""

    _widget_type = "Slider"

    def __init__(
        self,
        value: float = 0,
        *,
        min: float = 0,          # noqa: A002
        max: float = 100,        # noqa: A002
        divisions: Optional[int] = None,
        color: Optional[str] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        if max <= min:
            raise ValueError("Slider max must be greater than min")
        self._min = float(min)
        self._max = float(max)
        self._value = _clamp(float(value), self._min, self._max)
        if divisions is not None:
            self.style["divisions"] = int(divisions)
        if color:
            self.style["color"] = color
        self.style.setdefault("width", "match")

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float):
        self._value = _clamp(float(v), self._min, self._max)

    def _serialise_props(self) -> dict:
        return {"value": self._value, "min": self._min, "max": self._max}


class Dropdown(Widget):
    """A dropdown (spinner) that lets the user pick one of several options."""

    _widget_type = "Dropdown"

    def __init__(
        self,
        options: Optional[list[str]] = None,
        *,
        value: Optional[str] = None,
        hint: Optional[str] = None,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self._options = [str(o) for o in (options or [])]
        self._value = value if value in self._options else (self._options[0] if self._options else "")
        self._hint = hint
        self.style.setdefault("width", "match")

    @property
    def options(self) -> list:
        return list(self._options)

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, v: str):
        self._value = str(v)

    @property
    def selected_index(self) -> int:
        try:
            return self._options.index(self._value)
        except ValueError:
            return -1

    def _serialise_props(self) -> dict:
        d = {
            "options": list(self._options),
            "value": self._value,
            "index": self.selected_index,
        }
        if self._hint:
            d["hint"] = self._hint
        return d


class Radio(Widget):
    """A single radio button. Group several with the same ``group`` name."""

    _widget_type = "Radio"

    def __init__(
        self,
        label: str = "",
        *,
        value: Optional[str] = None,
        group: str = "default",
        selected: bool = False,
        key: Optional[str] = None,
        style: Optional[dict] = None,
        expand: Optional[int] = None,
        visible: bool = True,
        **kwargs,
    ):
        super().__init__(key=key, style=style, expand=expand, visible=visible, **kwargs)
        self._label = label
        self._value = value if value is not None else label
        self._group = group
        self._selected = selected

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, v: bool):
        self._selected = bool(v)

    def _serialise_props(self) -> dict:
        return {
            "label": self._label,
            "value": self._value,
            "group": self._group,
            "selected": self._selected,
        }


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
