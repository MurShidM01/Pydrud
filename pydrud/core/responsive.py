"""
Responsive scaling — adapts UI sizes to the device screen.

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
