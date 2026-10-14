"""
Material 3 colour system — HCT-based palettes, 30+ semantic roles,
seed generation, dynamic colour, and the complete :class:`ColorScheme`.

The old 13-role scheme is preserved for backwards compatibility; the new
:class:`DynamicScheme` is the recommended entry point for M3 apps.
"""

from __future__ import annotations

from pydrud.widgets.theme._common import (
    _argb, _ConstantsMeta, _mix, _rgb,
)
from pydrud.widgets.theme.hct import (
    CorePalette, DynamicScheme, Hct, TonalPalette,
    int_to_hex, hex_to_int,
)

# ── Constants (backwards-compatible) ─────────────────────────────────────────

class Colors(metaclass=_ConstantsMeta):
    """A small, opinionated Material-ish palette (ARGB strings).

    Names are forgiving: ``AMBER``, ``amber`` and ``deepOrange`` all work.
    For full M3 conformance, use :class:`DynamicScheme` instead.
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

    #: Material-3 role aliases
    ON_PRIMARY = "#FFFFFFFF"
    PRIMARY_CONTAINER = "#FFE0E7FF"
    ON_PRIMARY_CONTAINER = "#FF312E81"
    ON_BACKGROUND = "#FF1F2937"
    SECONDARY_CONTAINER = "#FFCCFBF1"
    ON_SURFACE = "#FF1F2937"
    ON_SURFACE_VARIANT = "#FF6B7280"
    OUTLINE_STRONG = "#FFD1D5DB"
    #: Material 3's shadow and scrim roles are both plain black. The scrim is
    #: black *and* the component composites it at 32 %, which is where the
    #: dimming comes from — baking the opacity into the role did both at once
    #: and made the two roles impossible to tell apart from a tinted grey.
    SHADOW = "#FF000000"
    SCRIM = "#FF000000"

    #: Tertiary (M3 third accent)
    TERTIARY = "#FF7C3AED"
    ON_TERTIARY = "#FFFFFFFF"
    TERTIARY_CONTAINER = "#FFEDE9FE"
    ON_TERTIARY_CONTAINER = "#FF3B0764"

    #: Error container
    ON_ERROR = "#FFFFFFFF"
    ERROR_CONTAINER = "#FFFCE4EC"
    ON_ERROR_CONTAINER = "#FF450A0A"

    #: Secondary container
    ON_SECONDARY = "#FFFFFFFF"
    ON_SECONDARY_CONTAINER = "#FF002020"

    #: Inverse roles
    INVERSE_SURFACE = "#FF1F2937"
    INVERSE_ON_SURFACE = "#FFF9FAFB"
    INVERSE_PRIMARY = "#FF818CF8"

    #: Surface container hierarchy
    SURFACE_DIM = "#FFD5D8DC"
    SURFACE_BRIGHT = "#FFFFFFFF"
    SURFACE_CONTAINER_LOWEST = "#FFFFFFFF"
    SURFACE_CONTAINER_LOW = "#FFF1F3F5"
    SURFACE_CONTAINER = "#FFE8EAED"
    SURFACE_CONTAINER_HIGH = "#FFE2E4E7"
    SURFACE_CONTAINER_HIGHEST = "#FFD5D8DC"

    #: Outline variant
    OUTLINE_VARIANT = "#FFD1D5DB"

    #: M3 "fixed" accent roles. These are tone-locked: the spec pins them to
    #: the same tones in light and dark, so a colour picked from them stays
    #: legible on any surface. Values are the published baseline scheme.
    PRIMARY_FIXED = "#FFEADDFF"
    PRIMARY_FIXED_DIM = "#FFCFBCFF"
    ON_PRIMARY_FIXED = "#FF21005D"
    ON_PRIMARY_FIXED_VARIANT = "#FF4A4458"
    SECONDARY_FIXED = "#FFE8DEF8"
    SECONDARY_FIXED_DIM = "#FFCCC2DC"
    ON_SECONDARY_FIXED = "#FF1D192B"
    ON_SECONDARY_FIXED_VARIANT = "#FF4A4458"
    TERTIARY_FIXED = "#FFFFD8E4"
    TERTIARY_FIXED_DIM = "#FFEFB8C8"
    ON_TERTIARY_FIXED = "#FF31111D"
    ON_TERTIARY_FIXED_VARIANT = "#FF633B48"

    #: Surface tint — the primary tone a surface adopts when it elevates.
    SURFACE_TINT = "#FF6750A4"

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

    AMBER = "#FFF59E0B"
    DEEP_ORANGE = "#FFEA580C"
    DEEP_PURPLE = "#FF7C3AED"
    LIGHT_BLUE = "#FF38BDF8"
    LIGHT_GREEN = "#FF4ADE80"
    BLUE_GREY = "#FF64748B"
    GREY_LIGHT = "#FF9CA3AF"
    GREY_DARK = "#FF374151"
    GRAY = GREY
    GRAY_LIGHT = GREY_LIGHT
    GRAY_DARK = GREY_DARK
    BLUE_GRAY = BLUE_GREY

    CHART_PALETTE = ("#FF6366F1", "#FF14B8A6", "#FFF59E0B", "#FFEF4444",
                     "#FFA855F7", "#FF3B82F6", "#FF22C55E", "#FFEC4899")

    @staticmethod
    def with_opacity(color: str, opacity: float) -> str:
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
        return cls.mix(color, cls.WHITE, amount)

    @classmethod
    def darken(cls, color: str, amount: float = 0.2) -> str:
        return cls.mix(color, "#FF0B0F17", amount)

    @classmethod
    def on(cls, background: str) -> str:
        r, g, b = _rgb(background)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        return cls.TEXT if luminance > 0.62 else cls.WHITE

    @staticmethod
    def is_light(color: str) -> bool:
        r, g, b = _rgb(color)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0 > 0.62

    @staticmethod
    def relative_luminance(color: str) -> float:
        def _linear(channel: int) -> float:
            value = channel / 255.0
            return (value / 12.92 if value <= 0.03928
                    else ((value + 0.055) / 1.055) ** 2.4)
        r, g, b = _rgb(color)
        return (0.2126 * _linear(r) + 0.7152 * _linear(g)
                + 0.0722 * _linear(b))

    @classmethod
    def contrast(cls, color: str, other: str) -> float:
        a, b = cls.relative_luminance(color), cls.relative_luminance(other)
        lighter, darker = max(a, b), min(a, b)
        return (lighter + 0.05) / (darker + 0.05)

    @classmethod
    def meets_contrast(cls, color: str, background: str, *,
                       large: bool = False) -> bool:
        threshold = 3.0 if large else 4.5
        # FIX: compare unrounded ratio, round only for display
        return cls.contrast(color, background) >= threshold


# ── Legacy ColorScheme (backwards-compatible) ────────────────────────────────

class ColorScheme:
    """A Material 3 colour scheme generated from a single seed colour.

    This is the legacy 13-role scheme preserved for backwards compatibility.
    For the full 48-role M3 scheme, use :class:`DynamicScheme` from
    ``pydrud.widgets.theme.hct``.

    ::

        scheme = ColorScheme.from_seed(Colors.INDIGO, dark=True)
        Theme.use(scheme)
    """

    ROLES = (
        "primary", "on_primary", "primary_container", "on_primary_container",
        "secondary", "on_secondary", "secondary_container",
        "on_secondary_container",
        "tertiary", "on_tertiary", "tertiary_container",
        "on_tertiary_container",
        "surface", "on_surface", "surface_variant", "on_surface_variant",
        "background", "on_background",
        "error", "on_error", "error_container", "on_error_container",
        "outline", "outline_variant",
        "inverse_surface", "inverse_on_surface", "inverse_primary",
        "shadow", "scrim",
        "surface_dim", "surface_bright",
        "surface_container_lowest", "surface_container_low",
        "surface_container", "surface_container_high",
        "surface_container_highest",
        # Fixed accents — tone-locked across light and dark.
        "primary_fixed", "primary_fixed_dim", "on_primary_fixed",
        "on_primary_fixed_variant",
        "secondary_fixed", "secondary_fixed_dim", "on_secondary_fixed",
        "on_secondary_fixed_variant",
        "tertiary_fixed", "tertiary_fixed_dim", "on_tertiary_fixed",
        "on_tertiary_fixed_variant",
        "surface_tint",
    )

    def __init__(self, *, dark: bool = False, **roles: str):
        unknown = set(roles) - set(self.ROLES)
        if unknown:
            raise ValueError(f"Unknown colour roles: {sorted(unknown)}")
        for role in self.ROLES:
            # FIX: an unspecified role used to fall back to PRIMARY, a
            # saturated indigo, so a partly-specified scheme silently painted
            # unrelated roles indigo. Fall back to the role's own M3 default.
            value = roles.get(role) or getattr(Colors, role.upper(), None)
            setattr(self, role, value or Colors.PRIMARY)
        self.dark = bool(dark)

    @classmethod
    def from_seed(cls, seed: str = Colors.PRIMARY, *, dark: bool = False) -> "ColorScheme":
        """Generate a scheme using HCT tonal palettes (M3-correct)."""
        seed_int = hex_to_int(seed)
        dyn = DynamicScheme.from_seed(seed_int, dark=dark)
        return cls._from_dynamic(dyn)

    @classmethod
    def from_seed_variant(
        cls, seed: str = Colors.PRIMARY, *, variant: str = "tonal_spot", dark: bool = False
    ) -> "ColorScheme":
        """Generate using a specific M3 variant."""
        seed_int = hex_to_int(seed)
        dyn = DynamicScheme.from_seed_variant(seed_int, variant=variant, dark=dark)
        return cls._from_dynamic(dyn)

    @classmethod
    def _from_dynamic(cls, dyn: DynamicScheme) -> "ColorScheme":
        """Convert a DynamicScheme to a legacy ColorScheme."""
        scheme = cls(
            dark=dyn.dark,
            primary=int_to_hex(dyn.primary),
            on_primary=int_to_hex(dyn.on_primary),
            primary_container=int_to_hex(dyn.primary_container),
            secondary=int_to_hex(dyn.secondary),
            on_secondary=int_to_hex(dyn.on_secondary),
            secondary_container=int_to_hex(dyn.secondary_container),
            tertiary=int_to_hex(dyn.tertiary),
            on_tertiary=int_to_hex(dyn.on_tertiary),
            tertiary_container=int_to_hex(dyn.tertiary_container),
            surface=int_to_hex(dyn.surface),
            on_surface=int_to_hex(dyn.on_surface),
            surface_variant=int_to_hex(dyn.surface_variant),
            on_surface_variant=int_to_hex(dyn.on_surface_variant),
            background=int_to_hex(dyn.background),
            on_background=int_to_hex(dyn.on_background),
            error=int_to_hex(dyn.error),
            on_error=int_to_hex(dyn.on_error),
            error_container=int_to_hex(dyn.error_container),
            on_error_container=int_to_hex(dyn.on_error_container),
            outline=int_to_hex(dyn.outline),
            outline_variant=int_to_hex(dyn.outline_variant),
            inverse_surface=int_to_hex(dyn.inverse_surface),
            inverse_on_surface=int_to_hex(dyn.inverse_on_surface),
            inverse_primary=int_to_hex(dyn.inverse_primary),
            shadow=int_to_hex(dyn.shadow),
            scrim=int_to_hex(dyn.scrim),
            surface_dim=int_to_hex(dyn.surface_dim),
            surface_bright=int_to_hex(dyn.surface_bright),
            surface_container_lowest=int_to_hex(dyn.surface_container_lowest),
            surface_container_low=int_to_hex(dyn.surface_container_low),
            surface_container=int_to_hex(dyn.surface_container),
            surface_container_high=int_to_hex(dyn.surface_container_high),
            surface_container_highest=int_to_hex(dyn.surface_container_highest),
            primary_fixed=int_to_hex(dyn.primary_fixed),
            primary_fixed_dim=int_to_hex(dyn.primary_fixed_dim),
            on_primary_fixed=int_to_hex(dyn.on_primary_fixed),
            on_primary_fixed_variant=int_to_hex(dyn.on_primary_fixed_variant),
            secondary_fixed=int_to_hex(dyn.secondary_fixed),
            secondary_fixed_dim=int_to_hex(dyn.secondary_fixed_dim),
            on_secondary_fixed=int_to_hex(dyn.on_secondary_fixed),
            on_secondary_fixed_variant=int_to_hex(dyn.on_secondary_fixed_variant),
            tertiary_fixed=int_to_hex(dyn.tertiary_fixed),
            tertiary_fixed_dim=int_to_hex(dyn.tertiary_fixed_dim),
            on_tertiary_fixed=int_to_hex(dyn.on_tertiary_fixed),
            on_tertiary_fixed_variant=int_to_hex(dyn.on_tertiary_fixed_variant),
            surface_tint=int_to_hex(dyn.surface_tint),
        )
        # FIX: the three "on container" roles exist on the scheme and are
        # consumed by the Java theme + the web stylesheet, but were never
        # copied across — every consumer saw the placeholder default.
        scheme.on_primary_container = int_to_hex(dyn.on_primary_container)
        scheme.on_secondary_container = int_to_hex(dyn.on_secondary_container)
        scheme.on_tertiary_container = int_to_hex(dyn.on_tertiary_container)
        return scheme

    def to_dict(self) -> dict:
        d = {role: getattr(self, role) for role in self.ROLES}
        d["dark"] = self.dark
        return d

    @classmethod
    def lerp(cls, start: "ColorScheme", end: "ColorScheme", t: float) -> "ColorScheme":
        k = max(0.0, min(1.0, float(t)))
        roles = {role: _mix(getattr(start, role), getattr(end, role), k)
                 for role in cls.ROLES}
        roles["dark"] = end.dark if k >= 0.5 else start.dark
        return cls(**roles)

    def __repr__(self) -> str:
        return f"<ColorScheme primary={self.primary} dark={self.dark}>"


__all__ = [
    "Colors", "ColorScheme", "DynamicScheme", "CorePalette",
    "TonalPalette", "Hct",
]