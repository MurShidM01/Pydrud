"""
Responsive scaling and MediaQuery — adapts UI sizes to the device screen.

Provides two APIs:

- ``Responsive`` (unchanged from v1.0.0) — class-level scaling methods
  for text, width, height, padding, spacing, radius, and icon sizes.

- ``MediaQuery`` (new in v1.0.1) — rich query of cached device metrics
  including screen dimensions, density, scale factor, status bar height,
  and safe-area padding.

Usage::

    from pydrud import Responsive

    # All values auto-scale to the device screen width.
    # Baseline = 360 dp (typical phone width).

    text_size = Responsive.text(16)       # font size
    button_w  = Responsive.w(56)          # button width
    button_h  = Responsive.h(56)          # button height
    pad       = Responsive.padding(24)    # padding / margin
    gap       = Responsive.spacing(8)     # spacing between widgets
    r         = Responsive.radius(12)     # border radius
    icon_size = Responsive.icon(24)       # icon size

Scaling is deliberately **clamped** to 0.9x – 1.2x.  A tablet is twice
as wide as a small phone, but doubling every font and button turns the
UI into a zoomed-in phone app.  Sizes grow gently, and layouts adapt
through breakpoints instead::

    cols = Responsive.value(compact=1, medium=2, expanded=3)
    pad  = Responsive.value(phone=16, tablet=32)
    n    = Responsive.columns(min_width=180)     # grid columns that fit
    w    = Responsive.content_width(560)         # readable page width

Use ``Responsive.raw()`` for the old unclamped behaviour.

``Responsive.init()`` is called automatically when the Android bridge
sends screen dimensions in the ``ready`` event.  If no device is
connected (e.g. in tests) the scale factor defaults to 1.0.
"""

from __future__ import annotations


class Responsive:
    """Screen-aware size scaling (class-level API)."""

    # Reference baseline (360 dp = typical phone width).
    _BASELINE_WIDTH = 360

    # Scaling is *clamped*: a 10-inch tablet is 2.4x wider than a small
    # phone, but its buttons and text must not be 2.4x bigger — that is
    # what makes naive "responsive" UIs look like a zoomed-in phone app.
    # Sizes grow gently; layout adapts through breakpoints instead.
    _MIN_FACTOR = 0.9
    _MAX_FACTOR = 1.2

    # Material 3 window size classes (dp).
    BREAKPOINT_MEDIUM = 600
    BREAKPOINT_EXPANDED = 840

    # Current device metrics — populated by ``init()``.
    _screen_width: int = 360
    _screen_height: int = 640
    _density: float = 2.0
    _scale_factor: float = 1.0
    _text_scale: float = 1.0

    # ── initialisation ──────────────────────────────────────────────────

    @classmethod
    def init(cls, width_dp: int, height_dp: int, density: float,
             text_scale: float = 1.0) -> None:
        """Set the device screen dimensions and recompute the scale factor.

        Called automatically when Python receives the ``ready`` event
        from the Android bridge.
        """
        cls._screen_width = max(width_dp, 1)
        cls._screen_height = max(height_dp, 1)
        cls._density = density
        cls._text_scale = text_scale or 1.0
        cls._scale_factor = cls._screen_width / cls._BASELINE_WIDTH

    @classmethod
    def reset(cls) -> None:
        """Restore the default (baseline) metrics — mainly for tests."""
        cls._screen_width = 360
        cls._screen_height = 640
        cls._density = 2.0
        cls._scale_factor = 1.0
        cls._text_scale = 1.0

    # ── public scaling methods ──────────────────────────────────────────

    @classmethod
    def text(cls, size: float) -> int:
        """Scale a font size (sp)."""
        return cls._scale(size)

    @classmethod
    def w(cls, size: float) -> int:
        """Scale a width (dp)."""
        return cls._scale(size)

    @classmethod
    def h(cls, size: float) -> int:
        """Scale a height (dp)."""
        return cls._scale(size)

    @classmethod
    def padding(cls, size: float) -> int:
        """Scale a padding / margin value (dp)."""
        return cls._scale(size)

    @classmethod
    def spacing(cls, size: float) -> int:
        """Scale a gap between widgets (dp)."""
        return cls._scale(size)

    @classmethod
    def radius(cls, size: float) -> int:
        """Scale a border-radius value (dp)."""
        return cls._scale(size)

    @classmethod
    def icon(cls, size: float) -> int:
        """Scale an icon size (dp)."""
        return cls._scale(size)

    # ── accessors ───────────────────────────────────────────────────────

    @classmethod
    def factor(cls) -> float:
        """The current scale factor (screen_width / 360)."""
        return cls._scale_factor

    @classmethod
    def screen_width(cls) -> int:
        """Device screen width in dp."""
        return cls._screen_width

    @classmethod
    def screen_height(cls) -> int:
        """Device screen height in dp."""
        return cls._screen_height

    @classmethod
    def density(cls) -> float:
        """Device pixel density."""
        return cls._density

    @classmethod
    def text_scale(cls) -> float:
        """The user's system font-size preference (1.0 = default)."""
        return cls._text_scale

    @classmethod
    def is_landscape(cls) -> bool:
        """True when the screen is wider than it is tall."""
        return cls._screen_width > cls._screen_height

    @classmethod
    def is_phone(cls) -> bool:
        """True for compact widths (< 600 dp)."""
        return cls._screen_width < cls.BREAKPOINT_MEDIUM

    @classmethod
    def is_tablet(cls) -> bool:
        """True for medium and expanded widths (>= 600 dp)."""
        return cls._screen_width >= cls.BREAKPOINT_MEDIUM

    @classmethod
    def breakpoint(cls) -> str:
        """The Material 3 window size class: compact/medium/expanded."""
        if cls._screen_width >= cls.BREAKPOINT_EXPANDED:
            return "expanded"
        if cls._screen_width >= cls.BREAKPOINT_MEDIUM:
            return "medium"
        return "compact"

    # ── adaptive layout helpers ─────────────────────────────────────────

    @classmethod
    def value(cls, compact=None, medium=None, expanded=None, **aliases):
        """Pick a value for the current window size class.

        ::

            columns = Responsive.value(compact=1, medium=2, expanded=3)
            pad     = Responsive.value(phone=16, tablet=32)

        Missing sizes fall back to the next smaller one, so passing just
        ``compact`` (or just ``phone``) always works.
        """
        compact = compact if compact is not None else aliases.get("phone")
        medium = medium if medium is not None else aliases.get("tablet")
        expanded = expanded if expanded is not None else aliases.get("desktop")
        if medium is None:
            medium = compact
        if expanded is None:
            expanded = medium
        return {"compact": compact, "medium": medium,
                "expanded": expanded}[cls.breakpoint()]

    @classmethod
    def columns(cls, min_width: int = 160, *, max_columns: int = 6,
                gutter: int = 16) -> int:
        """How many grid columns fit at *min_width* dp each.

        Mirrors the native ``style.columns = "auto"`` behaviour so Python
        and Android agree on the layout.
        """
        usable = max(cls._screen_width - gutter, 1)
        count = int(usable // max(min_width + gutter / 2, 1))
        return max(1, min(max_columns, count))

    @classmethod
    def content_width(cls, max_width: int = 560) -> int:
        """Page width capped for large screens (keeps line length sane)."""
        return min(cls._screen_width, max_width)

    @classmethod
    def clamp(cls, value: float, minimum: float, maximum: float) -> int:
        """Scale *value*, then clamp the result into a dp range."""
        return int(round(max(minimum, min(maximum, value * cls._factor()))))

    @classmethod
    def raw(cls, value: float) -> int:
        """Unclamped linear scaling (``value * screen_width / 360``)."""
        return round(value * cls._scale_factor)

    # ── internal ────────────────────────────────────────────────────────

    @classmethod
    def _factor(cls) -> float:
        """The clamped scale factor actually used for sizing."""
        return max(cls._MIN_FACTOR, min(cls._MAX_FACTOR, cls._scale_factor))

    @classmethod
    def _scale(cls, value: float) -> int:
        return round(value * cls._factor())


class MediaQuery:
    """Query cached device metrics for Python-side responsiveness.

    ``MediaQuery`` is auto-populated when the Android bridge sends the
    ``ready`` event with screen dimensions.  Use ``MediaQuery.of()`` to
    get a snapshot of all metrics as a dict.

    Usage::

        from pydrud import MediaQuery

        info = MediaQuery.of()
        width = info["width"]          # screen width in dp
        height = info["height"]        # screen height in dp
        density = info["density"]      # pixel density
        factor = info["scale_factor"]  # width / 360
    """

    _DEFAULTS: dict = {
        "width": 360,
        "height": 640,
        "density": 2.0,
        "scale_factor": 1.0,
        "status_bar_height": 24,
        "text_scale": 1.0,
        "padding_top": 0,
        "padding_bottom": 0,
        "padding_left": 0,
        "padding_right": 0,
    }

    _data: dict = dict(_DEFAULTS)

    # ── initialisation ──────────────────────────────────────────────────

    @classmethod
    def init(
        cls,
        width_dp: int,
        height_dp: int,
        density: float,
        status_bar_height: int = 24,
        text_scale: float = 1.0,
        **kwargs,
    ) -> None:
        """Update the cached device metrics."""
        baseline = 360
        cls._data["width"] = max(width_dp, 1)
        cls._data["height"] = max(height_dp, 1)
        cls._data["density"] = density
        cls._data["scale_factor"] = cls._data["width"] / baseline
        cls._data["status_bar_height"] = status_bar_height
        cls._data["text_scale"] = text_scale
        for k, v in kwargs.items():
            cls._data[k] = v

    # ── public API ──────────────────────────────────────────────────────

    @classmethod
    def reset(cls) -> None:
        """Restore the default metrics — mainly for tests."""
        cls._data = dict(cls._DEFAULTS)

    @classmethod
    def of(cls) -> dict:
        """Return a snapshot of the current media query data."""
        return dict(cls._data)

    @classmethod
    def size(cls) -> tuple:
        """Return ``(width_dp, height_dp)``."""
        return (cls._data["width"], cls._data["height"])

    @classmethod
    def is_phone(cls) -> bool:
        """True for compact widths (< 600 dp)."""
        return cls._data["width"] < 600

    @classmethod
    def is_tablet(cls) -> bool:
        """True for medium and expanded widths (>= 600 dp)."""
        return cls._data["width"] >= 600

    @classmethod
    def is_landscape(cls) -> bool:
        """True when the screen is wider than it is tall."""
        return cls._data["width"] > cls._data["height"]

    @classmethod
    def breakpoint(cls) -> str:
        """The Material 3 window size class: compact/medium/expanded."""
        width = cls._data["width"]
        if width >= 840:
            return "expanded"
        if width >= 600:
            return "medium"
        return "compact"

    @classmethod
    def safe_area(cls) -> dict:
        """Insets (dp) that system bars and cutouts occupy."""
        return {
            "top": cls._data.get("padding_top", 0),
            "bottom": cls._data.get("padding_bottom", 0),
            "left": cls._data.get("padding_left", 0),
            "right": cls._data.get("padding_right", 0),
        }
