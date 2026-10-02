"""
Styling primitives for Pydrud widgets.

Styles are plain dicts serialised to JSON. The helper classes below
provide a more ergonomic builder API.
"""

from __future__ import annotations
from typing import Optional, Union


# ── helpers ──────────────────────────────────────────────────────────────────


class EdgeInsets:
    """Represents padding or margin. Immutable."""

    def __init__(
        self,
        left: float = 0,
        top: float = 0,
        right: float = 0,
        bottom: float = 0,
        all: Optional[float] = None,  # noqa: A002
        horizontal: Optional[float] = None,
        vertical: Optional[float] = None,
    ):
        if all is not None:
            left = top = right = bottom = all
        if horizontal is not None:
            left = right = horizontal
        if vertical is not None:
            top = bottom = vertical
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    @classmethod
    def all(cls, value: float) -> "EdgeInsets":
        return cls(all=value)

    @classmethod
    def symmetric(cls, horizontal: float = 0, vertical: float = 0) -> "EdgeInsets":
        return cls(horizontal=horizontal, vertical=vertical)

    @classmethod
    def only(cls, left=0, top=0, right=0, bottom=0) -> "EdgeInsets":
        return cls(left=left, top=top, right=right, bottom=bottom)

    def to_dict(self) -> dict:
        return {"left": self.left, "top": self.top, "right": self.right, "bottom": self.bottom}


class Alignment:
    """Named alignment constants."""

    top_left = "topLeft"
    top_center = "topCenter"
    top_right = "topRight"
    center_left = "centerLeft"
    center = "center"
    center_right = "centerRight"
    bottom_left = "bottomLeft"
    bottom_center = "bottomCenter"
    bottom_right = "bottomRight"


class FontStyle:
    """Font configuration helper."""

    def __init__(
        self,
        size: Optional[float] = None,
        color: Optional[str] = None,
        weight: Optional[int] = None,  # 100-900
        italic: bool = False,
        family: Optional[str] = None,
    ):
        self.size = size
        self.color = color
        self.weight = weight
        self.italic = italic
        self.family = family

    def to_dict(self) -> dict:
        d: dict = {}
        if self.size is not None:
            d["size"] = self.size
        if self.color is not None:
            d["color"] = self.color
        if self.weight is not None:
            d["weight"] = self.weight
        if self.italic:
            d["italic"] = True
        if self.family is not None:
            d["family"] = self.family
        return d


class BorderSide:
    def __init__(self, color: str = "#FF000000", width: float = 1.0):
        self.color = color
        self.width = width

    def to_dict(self) -> dict:
        return {"color": self.color, "width": self.width}


class Border:
    """Four-sided border (every side currently receives the same style)."""

    def __init__(
        self,
        color: str = "#FF000000",
        width: float = 1.0,
        *,
        left: Optional[BorderSide] = None,
        top: Optional[BorderSide] = None,
        right: Optional[BorderSide] = None,
        bottom: Optional[BorderSide] = None,
    ):
        self.left = left or BorderSide(color, width)
        self.top = top or BorderSide(color, width)
        self.right = right or BorderSide(color, width)
        self.bottom = bottom or BorderSide(color, width)

    @classmethod
    def only(
        cls,
        *,
        color: str = "#FFE5E7EB",
        width: float = 1.0,
        left: bool = False,
        top: bool = False,
        right: bool = False,
        bottom: bool = False,
    ) -> "Border":
        """A border on selected edges only — e.g. a bottom hairline::

            Border.only(bottom=True, color=Colors.OUTLINE)
        """
        none = BorderSide(color, 0)
        border = cls(color, width)
        border.left = BorderSide(color, width) if left else none
        border.top = BorderSide(color, width) if top else none
        border.right = BorderSide(color, width) if right else none
        border.bottom = BorderSide(color, width) if bottom else none
        return border

    def to_dict(self) -> dict:
        return {
            "left": self.left.to_dict(),
            "top": self.top.to_dict(),
            "right": self.right.to_dict(),
            "bottom": self.bottom.to_dict(),
        }


class BorderRadius:
    """Rounded-corner radius."""

    def __init__(self, radius: float = 0):
        self.radius = radius

    def to_dict(self) -> dict:
        return {"radius": self.radius}


# ── Style builder ────────────────────────────────────────────────────────────


class Style:
    """Fluent builder for widget style dictionaries.

    Usage::

        Style()
            .bg("#FFFFFF")
            .padding(EdgeInsets.all(16))
            .border(Border("#CCCCCC", 1))
            .border_radius(8)
            .font(FontStyle(size=16, color="#FF0000"))
            .width(200)
            .height(48)
            .alignment(Alignment.center)
            .build()
    """

    def __init__(self):
        self._data: dict = {}

    # --- background ---

    def bg(self, color: str) -> "Style":
        """Background colour (hex ARGB or RGB)."""
        self._data["bg"] = self._normalise_color(color)
        return self

    def opacity(self, value: float) -> "Style":
        """Opacity 0.0 – 1.0."""
        self._data["opacity"] = value
        return self

    # --- size ---

    def width(self, value: Union[float, str]) -> "Style":
        """Fixed width in dp, or a string like "match", "wrap"."""
        self._data["width"] = value
        return self

    def height(self, value: Union[float, str]) -> "Style":
        """Fixed height in dp, or a string like "match", "wrap"."""
        self._data["height"] = value
        return self

    def min_width(self, value: float) -> "Style":
        self._data["minWidth"] = value
        return self

    def max_width(self, value: float) -> "Style":
        self._data["maxWidth"] = value
        return self

    def min_height(self, value: float) -> "Style":
        self._data["minHeight"] = value
        return self

    def max_height(self, value: float) -> "Style":
        self._data["maxHeight"] = value
        return self

    # --- spacing ---

    def padding(self, value: Union[EdgeInsets, float]) -> "Style":
        self._data["padding"] = value.to_dict() if isinstance(value, EdgeInsets) else {"all": value}
        return self

    def margin(self, value: Union[EdgeInsets, float]) -> "Style":
        self._data["margin"] = value.to_dict() if isinstance(value, EdgeInsets) else {"all": value}
        return self

    # --- border ---

    def border(self, value: Border) -> "Style":
        self._data["border"] = value.to_dict()
        return self

    def border_radius(self, value: Union[float, BorderRadius]) -> "Style":
        self._data["borderRadius"] = value if isinstance(value, (int, float)) else value.radius
        return self

    # --- font ---

    def font(self, value: FontStyle) -> "Style":
        self._data["font"] = value.to_dict()
        return self

    def text_color(self, color: str) -> "Style":
        self._data.setdefault("font", {})["color"] = self._normalise_color(color)
        return self

    def text_size(self, size: float) -> "Style":
        self._data.setdefault("font", {})["size"] = size
        return self

    def text_align(self, align: str) -> "Style":
        """One of "left", "center", "right"."""
        self._data["textAlign"] = align
        return self

    # --- layout ---

    def alignment(self, value: str) -> "Style":
        """Use one of the ``Alignment`` constants."""
        self._data["alignment"] = value
        return self

    def expand(self, value: int = 1) -> "Style":
        self._data["expand"] = value
        return self

    def visible(self, value: bool = True) -> "Style":
        self._data["visible"] = value
        return self

    def tooltip(self, value: str) -> "Style":
        self._data["tooltip"] = value
        return self

    # --- transform ---

    def rotate(self, degrees: float) -> "Style":
        self._data["rotate"] = degrees
        return self

    # --- image ---

    def fit(self, value: str) -> "Style":
        """Image scale type: "cover", "contain", "fill", "fitWidth", "fitHeight", "none"."""
        self._data["fit"] = value
        return self

    # --- shorthands ---

    def bg_image(self, src: str, fit: str = "cover") -> "Style":
        """Set background image."""
        self._data["bgImage"] = {"src": src, "fit": fit}
        return self

    def elevation(self, value: float) -> "Style":
        """Android elevation / shadow."""
        self._data["elevation"] = value
        return self

    def build(self) -> dict:
        """Return the accumulated style dict."""
        return dict(self._data)

    @staticmethod
    def _normalise_color(c: str) -> str:
        c = c.strip()
        if c.startswith("#"):
            c = c[1:]
        if len(c) == 6:
            c = "FF" + c
        return "#" + c.upper()
