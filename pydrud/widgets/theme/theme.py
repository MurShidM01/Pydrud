"""
The app-wide :class:`Theme`, its colour schemes and design extensions.
"""

from __future__ import annotations

import contextlib

from pydrud.widgets.tokens import Tokens
from pydrud.widgets.theme.colors import Colors, ColorScheme
from pydrud.widgets.theme.typography import Typography


class ThemeExtension:
    """A named bag of custom design values (Flutter's ``ThemeExtension``).

    Carries app-specific roles alongside the theme so they travel together::

        Theme.extend(ThemeExtension("brand", accent="#FF22D3EE", hero_radius=28))
        brand = Theme.extension("brand")
        Container(border_radius=brand.hero_radius, bg=brand.accent)
    """

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
        """A copy with some values replaced."""
        return ThemeExtension(self.name, **{**self._values, **values})

    def as_dict(self) -> dict:
        return dict(self._values)

    def __repr__(self) -> str:
        body = ", ".join(f"{k}={v!r}" for k, v in sorted(self._values.items()))
        return f"ThemeExtension({self.name!r}, {body})"


class Theme:
    """App-wide colours **and** design tokens.

    Colours live on the class itself (``Theme.primary``); every metric —
    radii, control heights, depth, motion, the type ramp — lives on
    :class:`Tokens` and is reachable through :meth:`configure`.
    """

    primary: str = Colors.PRIMARY
    background: str = Colors.BACKGROUND
    surface: str = Colors.SURFACE
    text: str = Colors.TEXT
    dark_mode: bool = False

    #: Derived roles, refreshed whenever a :class:`ColorScheme` is applied.
    secondary: str = Colors.SECONDARY
    surface_variant: str = Colors.SURFACE_VARIANT
    outline: str = Colors.OUTLINE
    error: str = Colors.ERROR
    on_primary: str = Colors.WHITE
    text_secondary: str = Colors.TEXT_SECONDARY

    @classmethod
    def apply(
        cls,
        *,
        primary: str | None = None,
        background: str | None = None,
        surface: str | None = None,
        text: str | None = None,
        dark_mode: bool | None = None,
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
        if dark_mode is not None:
            cls.dark_mode = dark_mode

    @classmethod
    def system(cls) -> None:
        """Use Android 12+ wallpaper-derived Material You colours.

        The actual palette lives on the device, so this marks the next
        connected :class:`~pydrud.App` theme push for a native query. On older
        Android versions the current Python palette remains the graceful
        fallback. Call ``app.apply_theme()`` when switching after startup.
        """
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
            "background": "background", "surface": "surface",
            "on_surface": "text", "surface_variant": "surface_variant",
            "outline": "outline", "on_primary": "on_primary",
        }
        for native_name, python_name in roles.items():
            value = palette.get(native_name)
            if isinstance(value, str) and value:
                setattr(cls, python_name, value)
        cls.dark_mode = bool(palette.get("dark", cls.dark_mode))
        # The system palette is complete enough that it should take precedence
        # over a stale generated seed scheme in payload().
        cls.scheme = None
        return True

    @classmethod
    def dark(cls) -> None:
        """Switch to a sensible dark palette derived from the current seed.

        The primary colour is lifted so it keeps its contrast on a dark
        surface — the same correction Material You applies.
        """
        cls._system_requested = False
        cls.use(ColorScheme.from_seed(cls._seed(), dark=True))

    @classmethod
    def light(cls) -> None:
        """Switch back to the light palette for the current seed."""
        cls._system_requested = False
        cls.use(ColorScheme.from_seed(cls._seed(), dark=False))

    @classmethod
    def seed(cls, color: str) -> None:
        """Rebuild the whole palette from one brand colour.

        ::

            Theme.seed(Colors.TEAL)          # light palette
            Theme.dark()                     # same brand, dark surfaces
        """
        cls._system_requested = False
        cls._seed_color = color
        cls.use(ColorScheme.from_seed(color, dark=cls.dark_mode))

    @classmethod
    def _seed(cls) -> str:
        return getattr(cls, "_seed_color", None) or Colors.PRIMARY

    @classmethod
    def configure(cls, **values) -> None:
        """Set colours and design tokens from Python, in one call.

        Colour roles (``primary``, ``surface``, …) and any design token
        (``radius_card``, ``app_bar_height``, ``font_family``, …) are
        accepted::

            Theme.configure(primary="#FF0EA5E9", radius_card=24,
                            app_bar_height=64, font_family="serif")

        The change reaches the device with the next ``theme`` push —
        ``app.apply_theme()`` sends one immediately.
        """
        roles = ("primary", "background", "surface", "text", "secondary",
                 "surface_variant", "outline", "error", "on_primary",
                 "text_secondary")
        tokens = {}
        for name, value in values.items():
            if name in roles:
                setattr(cls, name, value)
            elif name == "dark_mode":
                cls.dark_mode = bool(value)
            else:
                tokens[name] = value
        if tokens:
            Tokens.update(**tokens)

    #: Colour roles that :meth:`configure` / :meth:`scope` understand.
    _ROLES = ("primary", "background", "surface", "text", "secondary",
              "surface_variant", "outline", "error", "on_primary",
              "text_secondary")

    #: Custom :class:`ThemeExtension` bags registered with :meth:`extend`.
    _extensions: dict = {}

    @classmethod
    def configure_reset(cls) -> None:
        """Restore every design token to the Pydrud default."""
        Tokens.reset()

    @classmethod
    @contextlib.contextmanager
    def scope(cls, **overrides):
        """Override theme roles/tokens for a subtree, then restore them.

        Flutter's ``Theme(data: …)``: a screen, card or dialog can restyle
        itself without touching globals. Pydrud resolves theme values at
        build time, so wrap the widgets you construct::

            with Theme.scope(primary="#FFEC4899", radius_card=4):
                Column(children=[Button("Scoped"), Card(child=Text("…"))])

        Colour roles and design tokens are both accepted. Nesting works.
        """
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
        """Register a :class:`ThemeExtension` under its name."""
        cls._extensions[extension.name] = extension
        return extension

    @classmethod
    def extension(cls, name: str) -> ThemeExtension:
        """Look up a registered :class:`ThemeExtension` by name."""
        try:
            return cls._extensions[name]
        except KeyError:
            known = ", ".join(sorted(cls._extensions)) or "none"
            raise KeyError(f"No ThemeExtension named {name!r}. "
                           f"Registered: {known}") from None

    @classmethod
    def extensions(cls) -> dict:
        """Every registered extension, keyed by name."""
        return dict(cls._extensions)

    @classmethod
    def tokens(cls) -> dict:
        """The current design tokens as a plain dict."""
        return Tokens.as_dict()

    @classmethod
    def as_dict(cls) -> dict:
        return {
            "primary": cls.primary,
            "background": cls.background,
            "surface": cls.surface,
            "text": cls.text,
            "dark_mode": cls.dark_mode,
        }

    @classmethod
    def payload(cls) -> dict:
        """The palette in the shape the Android renderer expects.

        Sent once when the app connects so native widgets (buttons, inputs,
        switches, ripples, the status bar) use the same colours as the
        widgets Pydrud draws itself.
        """
        scheme = getattr(cls, "scheme", None)
        data = {
            "primary": cls.primary,
            "background": cls.background,
            "surface": cls.surface,
            "on_surface": cls.text,
            "dark": bool(cls.dark_mode),
        }
        if scheme is not None:
            for role in ("secondary", "on_primary", "surface_variant",
                         "primary_container", "on_surface_variant",
                         "outline", "error"):
                value = getattr(scheme, role, None)
                if value:
                    data[role] = value
        else:
            for role in ("secondary", "surface_variant", "outline", "error",
                         "on_primary", "on_surface_variant"):
                value = getattr(cls, role if role != "on_surface_variant"
                                else "text_secondary", None)
                if value:
                    data[role] = value
        # Every metric the renderer draws with — shape, size, depth,
        # motion and type — so Java never has an opinion of its own.
        data["tokens"] = Tokens.as_dict()
        return data


def _theme_use(cls, scheme: "ColorScheme") -> None:
    """Adopt a :class:`ColorScheme` as the app theme."""
    cls.apply(primary=scheme.primary, background=scheme.background,
              surface=scheme.surface, text=scheme.on_surface,
              dark_mode=scheme.dark)
    cls.secondary = scheme.secondary
    cls.surface_variant = scheme.surface_variant
    cls.outline = scheme.outline
    cls.error = scheme.error
    cls.on_primary = scheme.on_primary
    #: Muted text colour that stays readable on the current surface.
    cls.text_secondary = ("#FF9BA6B8" if scheme.dark
                          else Colors.TEXT_SECONDARY)
    cls.scheme = scheme


Theme.use = classmethod(_theme_use)
Theme.scheme = ColorScheme.from_seed()
Theme.typography = Typography
