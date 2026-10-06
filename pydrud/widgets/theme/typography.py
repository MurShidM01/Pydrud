"""
The Material 3 type scale: named :class:`TextTheme` roles and
:class:`Typography` sizes.
"""

from __future__ import annotations

from pydrud.widgets.theme._common import _token_name


class _TextStyle(dict):
    """A named text style — a ``style=`` dict for :class:`~pydrud.Text`."""

    def __init__(self, size: float, weight: int = 400,
                 letter_spacing: float | None = None,
                 line_height: float | None = None):
        font: dict = {"size": size, "weight": weight}
        if letter_spacing is not None:
            font["letterSpacing"] = letter_spacing
        if line_height is not None:
            font["lineHeight"] = line_height
        super().__init__(font=font)

    @property
    def size(self) -> float:
        return self["font"]["size"]

    @property
    def weight(self) -> int:
        return self["font"]["weight"]

    def with_(self, **overrides) -> "_TextStyle":
        """A copy with some font fields overridden (colour, family, …)."""
        font = {**self["font"], **overrides}
        copy = _TextStyle(font.pop("size", self.size),
                          font.pop("weight", self.weight))
        copy["font"].update(font)
        return copy


class _TextThemeMeta(type):
    """Resolve ``TextTheme.titleLarge`` / ``.TITLE_LARGE`` / ``.title_large``."""

    def __getattr__(cls, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        value = vars(cls).get(_token_name(name))
        if isinstance(value, _TextStyle):
            return value
        available = ", ".join(sorted(k.lower() for k, v in vars(cls).items()
                                     if isinstance(v, _TextStyle)))
        raise AttributeError(f"TextTheme has no style {name!r}. "
                             f"Available: {available}")


class TextTheme(metaclass=_TextThemeMeta):
    """Named text styles, by role instead of magic numbers.

    Mirrors Flutter's ``TextTheme`` / Material 3's type scale::

        from pydrud import Text, TextTheme

        Text("Title", style=TextTheme.title_large)
        Text("Body", style=TextTheme.BODY_MEDIUM)      # any spelling works

    Each role is a ``style=`` dict, so it can be passed straight to
    :class:`~pydrud.Text` and refined with :meth:`_TextStyle.with_`.
    """

    DISPLAY_LARGE = _TextStyle(57, 400, letter_spacing=-0.25)
    DISPLAY_MEDIUM = _TextStyle(45, 400)
    DISPLAY_SMALL = _TextStyle(36, 400)
    HEADLINE_LARGE = _TextStyle(32, 500)
    HEADLINE_MEDIUM = _TextStyle(28, 500)
    HEADLINE_SMALL = _TextStyle(24, 500)
    TITLE_LARGE = _TextStyle(22, 500)
    TITLE_MEDIUM = _TextStyle(16, 600)
    TITLE_SMALL = _TextStyle(14, 600)
    BODY_LARGE = _TextStyle(16, 400)
    BODY_MEDIUM = _TextStyle(14, 400)
    BODY_SMALL = _TextStyle(12, 400)
    LABEL_LARGE = _TextStyle(14, 500)
    LABEL_MEDIUM = _TextStyle(12, 500)
    LABEL_SMALL = _TextStyle(11, 500)


class Typography:
    """The Material 3 type scale, in sp."""

    DISPLAY = {"size": 45, "weight": 400}
    HEADLINE = {"size": 32, "weight": 600}
    TITLE = {"size": 22, "weight": 600}
    TITLE_SMALL = {"size": 16, "weight": 600}
    BODY = {"size": 16, "weight": 400}
    BODY_SMALL = {"size": 14, "weight": 400}
    LABEL = {"size": 14, "weight": 500}
    CAPTION = {"size": 12, "weight": 400}

    @classmethod
    def scale(cls, factor: float) -> dict:
        """Return the whole scale multiplied by *factor* (accessibility)."""
        out = {}
        for name, spec in vars(cls).items():
            if name.isupper() and isinstance(spec, dict):
                out[name.lower()] = {"size": round(spec["size"] * factor, 1),
                                     "weight": spec["weight"]}
        return out
