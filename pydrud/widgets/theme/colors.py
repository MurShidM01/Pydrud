"""
Material-style colour constants and a seed-derived :class:`ColorScheme`.
"""

from __future__ import annotations

from pydrud.widgets.theme._common import (
    _argb, _ConstantsMeta, _lighten_hsl, _mix, _rgb, _rotate_hue, _tone,
)


class Colors(metaclass=_ConstantsMeta):
    """A small, opinionated Material-ish palette (ARGB strings).

    Names are forgiving: ``AMBER``, ``amber`` and ``deepOrange`` all work.
    """

    TRANSPARENT = "#00000000"
    BLACK = "#FF000000"
    WHITE = "#FFFFFFFF"

    PRIMARY = "#FF6366F1"
    PRIMARY_DARK = "#FF4F46E5"
    PRIMARY_LIGHT = "#FF818CF8"
    SECONDARY = "#FF14B8A6"
    ACCENT = "#FFF59E0B"

    SUCCESS = "#FF22C55E"
    WARNING = "#FFF97316"
    ERROR = "#FFEF4444"
    INFO = "#FF3B82F6"

    BACKGROUND = "#FFF7F8FA"
    SURFACE = "#FFFFFFFF"
    OUTLINE = "#FFE5E7EB"

    BORDER = "#FFE5E7EB"
    SURFACE_VARIANT = "#FFF3F4F6"

    TEXT = "#FF1F2937"
    TEXT_SECONDARY = "#FF6B7280"
    TEXT_DISABLED = "#FF9CA3AF"

    #: Material-3 role aliases — handy when styling custom components.
    ON_PRIMARY = "#FFFFFFFF"
    PRIMARY_CONTAINER = "#FFE0E7FF"
    ON_PRIMARY_CONTAINER = "#FF312E81"
    SECONDARY_CONTAINER = "#FFCCFBF1"
    ON_SURFACE = "#FF1F2937"
    ON_SURFACE_VARIANT = "#FF6B7280"
    OUTLINE_STRONG = "#FFD1D5DB"
    SHADOW = "#33101828"
    SCRIM = "#99101828"

    RED = "#FFEF4444"
    PINK = "#FFEC4899"
    PURPLE = "#FFA855F7"
    INDIGO = "#FF6366F1"
    BLUE = "#FF3B82F6"
    CYAN = "#FF06B6D4"
    TEAL = "#FF14B8A6"
    GREEN = "#FF22C55E"
    LIME = "#FF84CC16"
    YELLOW = "#FFEAB308"
    ORANGE = "#FFF97316"
    BROWN = "#FF78716C"
    GREY = "#FF6B7280"

    #: The rest of the Material-style hue names developers reach for.
    AMBER = "#FFF59E0B"
    DEEP_ORANGE = "#FFEA580C"
    DEEP_PURPLE = "#FF7C3AED"
    LIGHT_BLUE = "#FF38BDF8"
    LIGHT_GREEN = "#FF4ADE80"
    BLUE_GREY = "#FF64748B"
    GREY_LIGHT = "#FF9CA3AF"
    GREY_DARK = "#FF374151"
    #: American spellings of the same neutrals.
    GRAY = GREY
    GRAY_LIGHT = GREY_LIGHT
    GRAY_DARK = GREY_DARK
    BLUE_GRAY = BLUE_GREY

    #: Default series colours for Chart and Canvas.pie().
    CHART_PALETTE = ("#FF6366F1", "#FF14B8A6", "#FFF59E0B", "#FFEF4444",
                     "#FFA855F7", "#FF3B82F6", "#FF22C55E", "#FFEC4899")

    @staticmethod
    def with_opacity(color: str, opacity: float) -> str:
        """Return *color* with the given opacity (0.0 – 1.0)."""
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0")
        c = color.lstrip("#")
        if len(c) == 8:
            c = c[2:]
        if len(c) != 6:
            raise ValueError(f"Unsupported colour format: {color!r}")
        alpha = format(round(opacity * 255), "02X")
        return _argb(c, alpha)

    @staticmethod
    def mix(color: str, other: str, amount: float = 0.5) -> str:
        """Blend two colours — ``amount`` 0 keeps *color*, 1 gives *other*."""
        t = max(0.0, min(1.0, amount))
        r1, g1, b1 = _rgb(color)
        r2, g2, b2 = _rgb(other)
        return _argb("%02X%02X%02X" % (
            round(r1 + (r2 - r1) * t),
            round(g1 + (g2 - g1) * t),
            round(b1 + (b2 - b1) * t),
        ))

    @classmethod
    def lighten(cls, color: str, amount: float = 0.2) -> str:
        """Move a colour towards white."""
        return cls.mix(color, cls.WHITE, amount)

    @classmethod
    def darken(cls, color: str, amount: float = 0.2) -> str:
        """Move a colour towards black."""
        return cls.mix(color, "#FF0B0F17", amount)

    @classmethod
    def on(cls, background: str) -> str:
        """A readable text colour for *background* (white or near-black)."""
        r, g, b = _rgb(background)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        return cls.TEXT if luminance > 0.62 else cls.WHITE

    @staticmethod
    def is_light(color: str) -> bool:
        """True when *color* is light enough to need dark content on top."""
        r, g, b = _rgb(color)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0 > 0.62

    # ── accessibility: WCAG 2.1 contrast (PYDRUD §14.7) ──────────────────

    @staticmethod
    def relative_luminance(color: str) -> float:
        """WCAG relative luminance of *color* (0.0 – 1.0)."""
        def _linear(channel: int) -> float:
            value = channel / 255.0
            return (value / 12.92 if value <= 0.03928
                    else ((value + 0.055) / 1.055) ** 2.4)

        r, g, b = _rgb(color)
        return (0.2126 * _linear(r) + 0.7152 * _linear(g)
                + 0.0722 * _linear(b))

    @classmethod
    def contrast(cls, color: str, other: str) -> float:
        """WCAG contrast ratio between two colours (1.0 – 21.0).

        ``Colors.contrast(Colors.WHITE, Colors.BLACK)`` is 21.0; identical
        colours give 1.0.
        """
        a, b = cls.relative_luminance(color), cls.relative_luminance(other)
        lighter, darker = max(a, b), min(a, b)
        return (lighter + 0.05) / (darker + 0.05)

    @classmethod
    def meets_contrast(cls, color: str, background: str, *,
                       large: bool = False) -> bool:
        """True when *color* over *background* passes WCAG AA.

        Normal text needs 4.5:1; large text (≥ 18 pt, or ≥ 14 pt bold)
        needs 3:1. Ratios are compared at one decimal place — the precision
        ``pydrud analyze`` reports — so a pair it prints as ``4.5:1`` is not
        then claimed to fail ``4.5:1``.
        """
        threshold = 3.0 if large else 4.5
        return round(cls.contrast(color, background), 1) >= threshold


class ColorScheme:
    """A Material 3 colour scheme generated from a single seed colour.

    Material You derives an entire palette from one colour by rotating tone.
    This is a pragmatic approximation: it keeps the seed's hue and produces
    the thirteen roles widgets actually reference, for both light and dark.

    ::

        scheme = ColorScheme.from_seed(Colors.INDIGO, dark=True)
        Theme.use(scheme)
    """

    ROLES = ("primary", "on_primary", "primary_container", "secondary",
             "on_secondary", "surface", "on_surface", "surface_variant",
             "background", "on_background", "error", "on_error", "outline")

    def __init__(self, *, dark: bool = False, **roles: str):
        unknown = set(roles) - set(self.ROLES)
        if unknown:
            raise ValueError(f"Unknown colour roles: {sorted(unknown)}")
        for role in self.ROLES:
            setattr(self, role, roles.get(role, Colors.PRIMARY))
        self.dark = bool(dark)

    @classmethod
    def from_seed(cls, seed: str = Colors.PRIMARY, *, dark: bool = False) -> "ColorScheme":
        r, g, b = _rgb(seed)
        # A harmonious secondary: the same colour rotated around the wheel,
        # not a channel swap (which lands on random hues).
        secondary = _rotate_hue(seed, 38, saturation=0.92)
        if dark:
            scheme = cls(
                primary=_tone(r, g, b, 1.25),
                on_primary="#FF111827",
                primary_container=_tone(r, g, b, 0.45),
                secondary=_lighten_hsl(secondary, 0.12),
                on_secondary="#FF111827",
                surface="#FF1F2937",
                on_surface="#FFF9FAFB",
                surface_variant="#FF374151",
                background="#FF111827",
                on_background="#FFF9FAFB",
                error="#FFFCA5A5",
                on_error="#FF450A0A",
                outline="#FF4B5563",
            )
        else:
            scheme = cls(
                primary=_argb(f"{r:02X}{g:02X}{b:02X}"),
                on_primary=Colors.WHITE,
                primary_container=_tone(r, g, b, 1.75),
                secondary=secondary,
                on_secondary=Colors.WHITE,
                surface=Colors.SURFACE,
                on_surface=Colors.TEXT,
                surface_variant="#FFF3F4F6",
                background=Colors.BACKGROUND,
                on_background=Colors.TEXT,
                error=Colors.ERROR,
                on_error=Colors.WHITE,
                outline=Colors.OUTLINE,
            )
        scheme.dark = dark
        return scheme

    def to_dict(self) -> dict:
        d = {role: getattr(self, role) for role in self.ROLES}
        d["dark"] = self.dark
        return d

    @classmethod
    def lerp(cls, start: "ColorScheme", end: "ColorScheme",
             t: float) -> "ColorScheme":
        """Blend two schemes role-by-role — the frame between two palettes.

        Every role (and the light/dark flag) moves through the same fraction,
        so a theme change can be animated instead of snapping.
        """
        k = max(0.0, min(1.0, float(t)))
        roles = {role: _mix(getattr(start, role), getattr(end, role), k)
                 for role in cls.ROLES}
        roles["dark"] = end.dark if k >= 0.5 else start.dark
        return cls(**roles)

    def __repr__(self) -> str:
        return f"<ColorScheme primary={self.primary} dark={self.dark}>"
