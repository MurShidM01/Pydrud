"""
The app-wide :class:`Theme`, its colour schemes and design extensions.

Full M3 colour roles via HCT tonal palettes, correct payload()
contract, and surface-container hierarchy.
"""

from __future__ import annotations

import contextlib

from pydrud.widgets.tokens import Tokens
from pydrud.widgets.theme.colors import Colors, ColorScheme, DynamicScheme
from pydrud.widgets.theme.hct import int_to_hex
from pydrud.widgets.theme.typography import Typography


class ThemeExtension:
    """A named bag of custom design values (Flutter's ``ThemeExtension``)."""

    __slots__ = ("name", "_values")

    def __init__(self, name: str, **values):
        if not isinstance(name, str) or not name.isidentifier():
            raise ValueError("ThemeExtension needs an identifier name")
        self.name = name
        self._values = dict(values)

    def __getattr__(self, item: str):
        try:
            return self._values[item]
        except KeyError:
            raise AttributeError(
                f"ThemeExtension {self.name!r} has no value {item!r}. "
                f"Available: {', '.join(sorted(self._values))}") from None

    def get(self, item: str, default=None):
        return self._values.get(item, default)

    def replace(self, **values) -> "ThemeExtension":
        return ThemeExtension(self.name, **{**self._values, **values})

    def as_dict(self) -> dict:
        return dict(self._values)

    def __repr__(self) -> str:
        body = ", ".join(f"{k}={v!r}" for k, v in sorted(self._values.items()))
        return f"ThemeExtension({self.name!r}, {body})"


class Theme:
    """App-wide colours **and** design tokens.

    Full M3 colour system with 30+ roles, HCT-based seed generation,
    surface-container hierarchy, and correct bridge payload contract.
    """

    # ── Primary roles ────────────────────────────────────────────────────
    primary: str = Colors.PRIMARY
    on_primary: str = Colors.ON_PRIMARY
    primary_container: str = Colors.PRIMARY_CONTAINER
    on_primary_container: str = Colors.ON_PRIMARY_CONTAINER

    # ── Secondary roles ──────────────────────────────────────────────────
    secondary: str = Colors.SECONDARY
    on_secondary: str = Colors.ON_SECONDARY
    secondary_container: str = Colors.SECONDARY_CONTAINER
    on_secondary_container: str = Colors.ON_SECONDARY_CONTAINER

    # ── Tertiary roles ───────────────────────────────────────────────────
    tertiary: str = Colors.TERTIARY
    on_tertiary: str = Colors.ON_TERTIARY
    tertiary_container: str = Colors.TERTIARY_CONTAINER
    on_tertiary_container: str = Colors.ON_TERTIARY_CONTAINER

    # ── Error roles ──────────────────────────────────────────────────────
    error: str = Colors.ERROR
    on_error: str = Colors.ON_ERROR
    error_container: str = Colors.ERROR_CONTAINER
    on_error_container: str = Colors.ON_ERROR_CONTAINER

    # ── Surface roles ────────────────────────────────────────────────────
    surface: str = Colors.SURFACE
    on_surface: str = Colors.ON_SURFACE
    surface_variant: str = Colors.SURFACE_VARIANT
    on_surface_variant: str = Colors.ON_SURFACE_VARIANT
    surface_dim: str = Colors.SURFACE_DIM
    surface_bright: str = Colors.SURFACE_BRIGHT
    surface_container_lowest: str = Colors.SURFACE_CONTAINER_LOWEST
    surface_container_low: str = Colors.SURFACE_CONTAINER_LOW
    surface_container: str = Colors.SURFACE_CONTAINER
    surface_container_high: str = Colors.SURFACE_CONTAINER_HIGH
    surface_container_highest: str = Colors.SURFACE_CONTAINER_HIGHEST

    # ── Background ───────────────────────────────────────────────────────
    background: str = Colors.BACKGROUND
    on_background: str = Colors.TEXT

    # ── Outline ──────────────────────────────────────────────────────────
    outline: str = Colors.OUTLINE
    outline_variant: str = Colors.OUTLINE_VARIANT

    # ── Inverse ──────────────────────────────────────────────────────────
    inverse_surface: str = Colors.INVERSE_SURFACE
    inverse_on_surface: str = Colors.INVERSE_ON_SURFACE
    inverse_primary: str = Colors.INVERSE_PRIMARY

    # ── Fixed accents (tone-locked; identical in light and dark) ─────────
    primary_fixed: str = Colors.PRIMARY_FIXED
    primary_fixed_dim: str = Colors.PRIMARY_FIXED_DIM
    on_primary_fixed: str = Colors.ON_PRIMARY_FIXED
    on_primary_fixed_variant: str = Colors.ON_PRIMARY_FIXED_VARIANT
    secondary_fixed: str = Colors.SECONDARY_FIXED
    secondary_fixed_dim: str = Colors.SECONDARY_FIXED_DIM
    on_secondary_fixed: str = Colors.ON_SECONDARY_FIXED
    on_secondary_fixed_variant: str = Colors.ON_SECONDARY_FIXED_VARIANT
    tertiary_fixed: str = Colors.TERTIARY_FIXED
    tertiary_fixed_dim: str = Colors.TERTIARY_FIXED_DIM
    on_tertiary_fixed: str = Colors.ON_TERTIARY_FIXED
    on_tertiary_fixed_variant: str = Colors.ON_TERTIARY_FIXED_VARIANT
    surface_tint: str = Colors.SURFACE_TINT

    # ── Shadow / Scrim ───────────────────────────────────────────────────
    shadow: str = Colors.SHADOW
    scrim: str = Colors.SCRIM

    # ── Legacy aliases ───────────────────────────────────────────────────
    text: str = Colors.TEXT
    text_secondary: str = Colors.TEXT_SECONDARY
    dark_mode: bool = False

    @classmethod
    def apply(
        cls,
        *,
        primary: str | None = None,
        background: str | None = None,
        surface: str | None = None,
        text: str | None = None,
        dark_mode: bool | None = None,
        **roles: str | None,
    ) -> None:
        """Override one or more theme values."""
        if primary is not None:
            cls.primary = primary
        if background is not None:
            cls.background = background
        if surface is not None:
            cls.surface = surface
        if text is not None:
            cls.text = text
            cls.on_surface = text
        if dark_mode is not None:
            cls.dark_mode = dark_mode
        # Apply any additional named roles
        for name, value in roles.items():
            if value is not None and hasattr(cls, name):
                setattr(cls, name, value)

    @classmethod
    def system(cls) -> None:
        """Use Android 12+ wallpaper-derived Material You colours."""
        cls._system_requested = True

    @classmethod
    def _uses_system(cls) -> bool:
        return bool(getattr(cls, "_system_requested", False))

    @classmethod
    def _apply_system_palette(cls, palette: dict) -> bool:
        """Adopt a palette returned by the Android Material You service."""
        if not isinstance(palette, dict) or not palette.get("available"):
            return False
        roles = {
            "primary": "primary", "secondary": "secondary",
            "tertiary": "tertiary",
            "background": "background", "surface": "surface",
            "on_surface": "on_surface", "surface_variant": "surface_variant",
            "outline": "outline", "on_primary": "on_primary",
            "on_secondary": "on_secondary", "on_tertiary": "on_tertiary",
            "error": "error", "on_error": "on_error",
            "surface_dim": "surface_dim",
            "surface_container": "surface_container",
        }
        for native_name, python_name in roles.items():
            value = palette.get(native_name)
            if isinstance(value, str) and value:
                setattr(cls, python_name, value)
        cls.dark_mode = bool(palette.get("dark", cls.dark_mode))
        cls._dynamic_scheme = None
        return True

    @classmethod
    def dark(cls) -> None:
        """Switch to a dark palette from the current seed."""
        cls._system_requested = False
        cls.use(ColorScheme.from_seed(cls._seed(), dark=True))

    @classmethod
    def light(cls) -> None:
        """Switch back to the light palette."""
        cls._system_requested = False
        cls.use(ColorScheme.from_seed(cls._seed(), dark=False))

    @classmethod
    def seed(cls, color: str) -> None:
        """Rebuild the whole palette from one brand colour using HCT."""
        cls._system_requested = False
        cls._seed_color = color
        cls.use(ColorScheme.from_seed(color, dark=cls.dark_mode))

    @classmethod
    def _seed(cls) -> str:
        return getattr(cls, "_seed_color", None) or Colors.PRIMARY

    @classmethod
    def configure(cls, **values) -> None:
        """Set colours and design tokens from Python, in one call."""
        color_roles = set(ColorScheme.ROLES) | {
            "primary", "background", "surface", "text", "secondary",
            "surface_variant", "outline", "error", "on_primary",
            "text_secondary", "on_surface", "on_surface_variant",
        }
        tokens = {}
        for name, value in values.items():
            if name in color_roles:
                setattr(cls, name, value)
            elif name == "dark_mode":
                cls.dark_mode = bool(value)
            else:
                tokens[name] = value
        if tokens:
            Tokens.update(**tokens)

    #: Colour roles that :meth:`configure` / :meth:`scope` understand.
    _ROLES = set(ColorScheme.ROLES) | {
        "primary", "background", "surface", "text", "secondary",
        "surface_variant", "outline", "error", "on_primary",
        "text_secondary", "on_surface", "on_surface_variant",
    }

    _extensions: dict = {}

    @classmethod
    def configure_reset(cls) -> None:
        """Restore every design token to the Pydrud default."""
        Tokens.reset()

    @classmethod
    @contextlib.contextmanager
    def scope(cls, **overrides):
        """Override theme roles/tokens for a subtree, then restore them."""
        saved_roles: dict = {}
        saved_tokens = None
        tokens: dict = {}
        for name, value in overrides.items():
            if name in cls._ROLES or name == "dark_mode":
                saved_roles[name] = getattr(cls, name)
                setattr(cls, name, value)
            else:
                tokens[name] = value
        if tokens:
            saved_tokens = Tokens.as_dict()
            Tokens.update(**tokens)
        try:
            yield cls
        finally:
            for name, value in saved_roles.items():
                setattr(cls, name, value)
            if saved_tokens is not None:
                Tokens.reset()
                Tokens.update(**saved_tokens)

    @classmethod
    def extend(cls, extension: ThemeExtension) -> ThemeExtension:
        cls._extensions[extension.name] = extension
        return extension

    @classmethod
    def extension(cls, name: str) -> ThemeExtension:
        try:
            return cls._extensions[name]
        except KeyError:
            known = ", ".join(sorted(cls._extensions)) or "none"
            raise KeyError(f"No ThemeExtension named {name!r}. "
                           f"Registered: {known}") from None

    @classmethod
    def extensions(cls) -> dict:
        return dict(cls._extensions)

    @classmethod
    def tokens(cls) -> dict:
        return Tokens.as_dict()

    @classmethod
    def as_dict(cls) -> dict:
        """All colour roles as a dict."""
        result = {}
        for role in ColorScheme.ROLES:
            if hasattr(cls, role):
                result[role] = getattr(cls, role)
        result["dark_mode"] = cls.dark_mode
        return result

    @classmethod
    def payload(cls) -> dict:
        """The palette in the shape the Android renderer expects.

        FIX: now forwards ALL M3 roles, not just a subset.
        Every role that exists on the scheme AND on Theme is included,
        so the native side never receives an incomplete palette.
        """
        scheme = getattr(cls, "_dynamic_scheme", None)
        legacy_scheme = getattr(cls, "scheme", None)

        data: dict = {"dark": bool(cls.dark_mode)}

        # Collect all M3 colour roles from the scheme or from Theme class attrs
        if scheme is not None:
            # Full DynamicScheme — serialize all int colours
            for key, value in scheme.to_dict().items():
                if isinstance(value, int) and key != "dark":
                    data[key] = int_to_hex(value)
        elif legacy_scheme is not None:
            # Legacy ColorScheme — serialize all roles
            for role in legacy_scheme.ROLES:
                value = getattr(legacy_scheme, role, None)
                if isinstance(value, str) and value:
                    data[role] = value
            data.setdefault("dark", legacy_scheme.dark)
        else:
            # No scheme — use Theme class attributes directly
            for role in ColorScheme.ROLES:
                value = getattr(cls, role, None)
                if isinstance(value, str) and value:
                    data[role] = value

        # Ensure critical roles are always present (bridge contract)
        data.setdefault("primary", cls.primary)
        data.setdefault("surface", cls.surface)
        data.setdefault("on_surface", cls.on_surface or cls.text)
        data.setdefault("background", cls.background)
        data.setdefault("on_background", cls.on_background or cls.text)

        # Design tokens
        data["tokens"] = Tokens.as_dict()
        return data


def _theme_use(cls, scheme) -> None:
    """Adopt a ColorScheme or DynamicScheme as the app theme."""
    if isinstance(scheme, DynamicScheme):
        # Full DynamicScheme — apply all roles
        for role in ColorScheme.ROLES:
            value = int_to_hex(getattr(scheme, role, 0))
            if hasattr(cls, role):
                setattr(cls, role, value)
        cls.dark_mode = scheme.dark
        cls._dynamic_scheme = scheme
        cls.scheme = None
    else:
        # Legacy ColorScheme
        cls.apply(
            primary=scheme.primary,
            background=scheme.background,
            surface=scheme.surface,
            text=scheme.on_surface,
            dark_mode=scheme.dark,
        )
        # Apply all available roles
        for role in scheme.ROLES:
            value = getattr(scheme, role, None)
            if value and hasattr(cls, role):
                setattr(cls, role, value)
        cls.text_secondary = ("#FF9BA6B8" if scheme.dark
                              else Colors.TEXT_SECONDARY)
        cls.scheme = scheme
        cls._dynamic_scheme = None


Theme.use = classmethod(_theme_use)
Theme.scheme = ColorScheme.from_seed()
Theme._dynamic_scheme = None
Theme.typography = Typography