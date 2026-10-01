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

``Responsive.init()`` is called automatically when the Android bridge
sends screen dimensions in the ``ready`` event.  If no device is
connected (e.g. in tests) the scale factor defaults to 1.0.
"""

from __future__ import annotations


class Responsive:
    """Screen-aware size scaling (class-level API)."""

    # Reference baseline (360 dp = typical phone width).
    _BASELINE_WIDTH = 360

    # Current device metrics — populated by ``init()``.
    _screen_width: int = 360
    _screen_height: int = 640
    _density: float = 2.0
    _scale_factor: float = 1.0

    # ── initialisation ──────────────────────────────────────────────────

    @classmethod
    def init(cls, width_dp: int, height_dp: int, density: float) -> None:
        """Set the device screen dimensions and recompute the scale factor.

        Called automatically when Python receives the ``ready`` event
        from the Android bridge.
        """
        cls._screen_width = max(width_dp, 1)
        cls._screen_height = max(height_dp, 1)
        cls._density = density
        cls._scale_factor = cls._screen_width / cls._BASELINE_WIDTH

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

    # ── internal ────────────────────────────────────────────────────────

    @classmethod
    def _scale(cls, value: float) -> int:
        return round(value * cls._scale_factor)


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

    _data: dict = {
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
    def of(cls) -> dict:
        """Return a snapshot of the current media query data."""
        return dict(cls._data)

    @classmethod
    def size(cls) -> tuple:
        """Return ``(width_dp, height_dp)``."""
        return (cls._data["width"], cls._data["height"])

    @classmethod
    def is_phone(cls) -> bool:
        """True if the device width is ≤ 428 dp (typical phone)."""
        return cls._data["width"] <= 428

    @classmethod
    def is_tablet(cls) -> bool:
        """True if the device width is > 600 dp (typical tablet)."""
        return cls._data["width"] > 600
