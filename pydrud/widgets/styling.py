"""
Styling primitives for Pydrud widgets.

RTL support (start/end), per-corner border radius, M3 shape tokens.
"""

from __future__ import annotations
from typing import Optional, Sequence, Union


# ── helpers ──────────────────────────────────────────────────────────────────

class EdgeInsets:
    """Represents padding or margin. Immutable.

    Added ``start``/``end`` for RTL support.  ``left``/``right``
    remain for absolute positioning; ``start``/``end`` resolve relative
    to the current text direction.

    ::

        EdgeInsets.all(16)
        EdgeInsets.symmetric(horizontal=20, vertical=12)
        EdgeInsets.only(left=8, top=16)
        EdgeInsets.only(start=16, end=8)  # RTL-aware
    """

    def __init__(
        self,
        left: float = 0,
        top: float = 0,
        right: float = 0,
        bottom: float = 0,
        all: Optional[float] = None,  # noqa: A002
        horizontal: Optional[float] = None,
        vertical: Optional[float] = None,
        start: Optional[float] = None,
        end: Optional[float] = None,
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
        self.start = start
        self.end = end

    @classmethod
    def all(cls, value: float) -> "EdgeInsets":
        return cls(all=value)

    @classmethod
    def symmetric(cls, horizontal: float = 0, vertical: float = 0) -> "EdgeInsets":
        return cls(horizontal=horizontal, vertical=vertical)

    @classmethod
    def only(cls, left=0, top=0, right=0, bottom=0,
             start=None, end=None) -> "EdgeInsets":
        return cls(left=left, top=top, right=right, bottom=bottom,
                   start=start, end=end)

    def to_dict(self) -> dict:
        d = {"left": self.left, "top": self.top,
             "right": self.right, "bottom": self.bottom}
        if self.start is not None:
            d["start"] = self.start
        if self.end is not None:
            d["end"] = self.end
        return d


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
        weight: Optional[int] = None,
        italic: bool = False,
        family: Optional[str] = None,
        line_height: Optional[float] = None,
        letter_spacing: Optional[float] = None,
    ):
        self.size = size
        self.color = color
        self.weight = weight
        self.italic = italic
        self.family = family
        self.line_height = line_height
        self.letter_spacing = letter_spacing

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
        if self.line_height is not None:
            d["lineHeight"] = self.line_height
        if self.letter_spacing is not None:
            d["letterSpacing"] = self.letter_spacing
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
    """Rounded-corner radius with per-corner support.

    Supports per-corner radii for M3 filled text fields (top-only),
    bottom sheets (top-only), and other asymmetric shapes.

    ::

        BorderRadius(16)                          # uniform
        BorderRadius.only(top_left=4, top_right=4)  # filled text field
        BorderRadius.only(top_left=28, top_right=28) # bottom sheet
    """

    def __init__(
        self,
        radius: float = 0,
        *,
        top_left: Optional[float] = None,
        top_right: Optional[float] = None,
        bottom_left: Optional[float] = None,
        bottom_right: Optional[float] = None,
    ):
        self.radius = radius
        self.top_left = top_left if top_left is not None else radius
        self.top_right = top_right if top_right is not None else radius
        self.bottom_left = bottom_left if bottom_left is not None else radius
        self.bottom_right = bottom_right if bottom_right is not None else radius

    @classmethod
    def only(
        cls,
        *,
        top_left: float = 0,
        top_right: float = 0,
        bottom_left: float = 0,
        bottom_right: float = 0,
    ) -> "BorderRadius":
        """Per-corner radius — for M3 filled fields, bottom sheets, etc."""
        return cls(
            0, top_left=top_left, top_right=top_right,
            bottom_left=bottom_left, bottom_right=bottom_right,
        )

    def is_uniform(self) -> bool:
        """True when all four corners have the same radius."""
        return (self.top_left == self.top_right ==
                self.bottom_left == self.bottom_right)

    def to_dict(self) -> dict:
        if self.is_uniform():
            return {"radius": self.top_left}
        return {
            "topLeft": self.top_left,
            "topRight": self.top_right,
            "bottomLeft": self.bottom_left,
            "bottomRight": self.bottom_right,
        }


class Shape:
    """M3 shape categories — semantic radius tokens.

    Material 3 defines 5 shape categories that map to component families.
    Use these instead of raw numbers for M3-conformant styling.

    ::

        Shape.extra_small   # 4dp — chips, small controls
        Shape.small         # 8dp — buttons, text fields
        Shape.medium        # 12dp — cards, dialogs
        Shape.large         # 16dp — sheets, large cards
        Shape.extra_large   # 28dp — bottom sheets, full-screen dialogs
        Shape.full          # 999dp — pill/circle
    """

    NONE = 0
    EXTRA_SMALL = 4
    SMALL = 8
    MEDIUM = 12
    LARGE = 16
    LARGE_INCREASED = 20
    EXTRA_LARGE = 28
    EXTRA_LARGE_INCREASED = 32
    EXTRA_EXTRA_LARGE = 48
    FULL = 999

    # Component-specific defaults (M3 spec)
    BUTTON = 20
    FAB = 16
    FAB_LARGE = 28
    EXTENDED_FAB = 16
    CHIP = EXTRA_SMALL
    CARD = MEDIUM
    DIALOG = EXTRA_LARGE
    BOTTOM_SHEET = EXTRA_LARGE
    TEXT_FIELD_FILLED = EXTRA_SMALL     # top corners only
    TEXT_FIELD_OUTLINED = EXTRA_SMALL
    NAVIGATION_BAR = NONE
    NAVIGATION_DRAWER = LARGE
    MENU = EXTRA_SMALL
    SNACKBAR = EXTRA_SMALL
    TAB = NONE
    SWITCH = FULL
    CHECKBOX = 2
    RADIO = FULL
    SLIDER = FULL
    SEGMENTED_BUTTON = FULL
    SEARCH_BAR = FULL
    TOOLTIP = EXTRA_SMALL


# ── Gradient ─────────────────────────────────────────────────────────────────

class _Gradient:
    kind = "linear"

    def __init__(self, colors: Sequence[str]):
        values = [str(color) for color in colors]
        if len(values) < 2:
            raise ValueError("a gradient needs at least two colors")
        self.colors = values

    def to_dict(self) -> dict:
        return {"kind": self.kind, "colors": list(self.colors)}


class LinearGradient(_Gradient):
    def __init__(self, colors: Sequence[str], direction: str = "vertical"):
        if direction not in {"vertical", "horizontal", "diagonal",
                             "diagonal_up", "up"}:
            raise ValueError("unsupported linear gradient direction")
        super().__init__(colors)
        self.direction = direction

    def to_dict(self) -> dict:
        return {**super().to_dict(), "direction": self.direction}


class RadialGradient(_Gradient):
    kind = "radial"

    def __init__(self, colors: Sequence[str], radius: float = 160):
        super().__init__(colors)
        if radius <= 0:
            raise ValueError("radial gradient radius must be positive")
        self.radius = float(radius)

    def to_dict(self) -> dict:
        return {**super().to_dict(), "radius": self.radius}


class SweepGradient(_Gradient):
    kind = "sweep"


# ── Style builder ────────────────────────────────────────────────────────────

class Style:
    """Fluent builder for widget style dictionaries.

    Supports per-corner radius and M3 shape tokens.

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
        self._data["bg"] = self._normalise_color(color)
        return self

    def opacity(self, value: float) -> "Style":
        self._data["opacity"] = value
        return self

    def gradient(self, value: _Gradient | dict) -> "Style":
        self._data["gradient"] = value.to_dict() if hasattr(value, "to_dict") else dict(value)
        return self

    # --- size ---

    def width(self, value: Union[float, str]) -> "Style":
        self._data["width"] = value
        return self

    def height(self, value: Union[float, str]) -> "Style":
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
        """Set border radius. Accepts a scalar or per-corner BorderRadius."""
        if isinstance(value, BorderRadius):
            self._data["borderRadius"] = value.to_dict()
        else:
            self._data["borderRadius"] = value
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
        self._data["textAlign"] = align
        return self

    # --- layout ---

    def alignment(self, value: str) -> "Style":
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

    def blur(self, radius: float) -> "Style":
        self._data["blur"] = radius
        return self

    # --- image ---

    def fit(self, value: str) -> "Style":
        self._data["fit"] = value
        return self

    # --- shorthands ---

    def bg_image(self, src: str, fit: str = "cover") -> "Style":
        self._data["bgImage"] = {"src": src, "fit": fit}
        return self

    def elevation(self, value: float) -> "Style":
        self._data["elevation"] = value
        return self

    def build(self) -> dict:
        return dict(self._data)

    @staticmethod
    def _normalise_color(c: str) -> str:
        c = c.strip()
        if c.startswith("#"):
            c = c[1:]
        if len(c) == 6:
            c = "FF" + c
        return "#" + c.upper()