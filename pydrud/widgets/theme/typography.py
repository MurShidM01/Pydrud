"""
The Material 3 type scale: named :class:`TextTheme` roles and
:class:`Typography` sizes.

Exact M3 baseline weights, line-heights and letter-spacing for
all 15 roles.
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
        font = {**self["font"], **overrides}
        copy = _TextStyle(font.pop("size", self.size),
                          font.pop("weight", self.weight))
        copy["font"].update(font)
        return copy


class _TextThemeMeta(type):
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
    """Named text styles — the complete M3 type scale.

    Exact M3 baseline metrics (size/weight/line-height/letter-spacing)
    for all 15 roles.  Previously headline and title weights deviated.

    ::

        Text("Title", style=TextTheme.title_large)
        Text("Body", style=TextTheme.BODY_MEDIUM)
    """

    # M3 baseline: Display — 57/45/36 sp, w400, tight tracking
    DISPLAY_LARGE = _TextStyle(57, 400, letter_spacing=-0.25, line_height=64)
    DISPLAY_MEDIUM = _TextStyle(45, 400, line_height=52)
    DISPLAY_SMALL = _TextStyle(36, 400, line_height=44)

    # M3 baseline: Headline — 32/28/24 sp, w400 (NOT w500)
    HEADLINE_LARGE = _TextStyle(32, 400, line_height=40)
    HEADLINE_MEDIUM = _TextStyle(28, 400, line_height=36)
    HEADLINE_SMALL = _TextStyle(24, 400, line_height=32)

    # M3 baseline: Title — 22/16/14 sp
    #   Large: w400 (NOT w500)
    #   Medium: w500 (NOT w600)
    #   Small: w500 (NOT w600)
    TITLE_LARGE = _TextStyle(22, 400, line_height=28)
    TITLE_MEDIUM = _TextStyle(16, 500, letter_spacing=0.15, line_height=24)
    TITLE_SMALL = _TextStyle(14, 500, letter_spacing=0.1, line_height=20)

    # M3 baseline: Body — 16/14/12 sp, w400
    BODY_LARGE = _TextStyle(16, 400, letter_spacing=0.5, line_height=24)
    BODY_MEDIUM = _TextStyle(14, 400, letter_spacing=0.25, line_height=20)
    BODY_SMALL = _TextStyle(12, 400, letter_spacing=0.4, line_height=16)

    # M3 baseline: Label — 14/12/11 sp, w500
    LABEL_LARGE = _TextStyle(14, 500, letter_spacing=0.1, line_height=20)
    LABEL_MEDIUM = _TextStyle(12, 500, letter_spacing=0.5, line_height=16)
    LABEL_SMALL = _TextStyle(11, 500, letter_spacing=0.5, line_height=16)


class Typography:
    """The Material 3 type scale, in sp.

    Updated to match the M3 baseline exactly.
    """

    DISPLAY = {"size": 45, "weight": 400, "lineHeight": 52}
    HEADLINE = {"size": 32, "weight": 400, "lineHeight": 40}
    TITLE = {"size": 22, "weight": 400, "lineHeight": 28}
    TITLE_SMALL = {"size": 16, "weight": 500, "lineHeight": 24}
    BODY = {"size": 16, "weight": 400, "lineHeight": 24}
    BODY_SMALL = {"size": 14, "weight": 400, "lineHeight": 20}
    LABEL = {"size": 14, "weight": 500, "lineHeight": 20}
    CAPTION = {"size": 12, "weight": 400, "lineHeight": 16}

    @classmethod
    def scale(cls, factor: float) -> dict:
        out = {}
        for name, spec in vars(cls).items():
            if name.isupper() and isinstance(spec, dict):
                out[name.lower()] = {
                    "size": round(spec["size"] * factor, 1),
                    "weight": spec["weight"],
                    "lineHeight": round(spec.get("lineHeight", spec["size"] * 1.32) * factor, 1),
                }
        return out