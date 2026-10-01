"""
Theme helpers — a Material colour palette and an icon-name catalogue.

These constants keep app code readable and guarantee the values are
understood by the Android renderer::

    from pydrud import Colors, Icons, Text, Icon

    Text("Hi", color=Colors.PRIMARY)
    Icon(Icons.SETTINGS)
"""

from __future__ import annotations


def _argb(hex_rgb: str, alpha: str = "FF") -> str:
    return f"#{alpha}{hex_rgb.upper()}"


class Colors:
    """A small, opinionated Material-ish palette (ARGB strings)."""

    TRANSPARENT = "#00000000"
    BLACK = "#FF000000"
    WHITE = "#FFFFFFFF"

    PRIMARY = "#FF6366F1"
    PRIMARY_DARK = "#FF4F46E5"
    SECONDARY = "#FF14B8A6"
    ACCENT = "#FFF59E0B"

    SUCCESS = "#FF22C55E"
    WARNING = "#FFF97316"
    ERROR = "#FFEF4444"
    INFO = "#FF3B82F6"

    BACKGROUND = "#FFF9FAFB"
    SURFACE = "#FFFFFFFF"
    OUTLINE = "#FFE5E7EB"

    BORDER = "#FFE5E7EB"
    SURFACE_VARIANT = "#FFF3F4F6"

    TEXT = "#FF1F2937"
    TEXT_SECONDARY = "#FF6B7280"
    TEXT_DISABLED = "#FF9CA3AF"

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


class Icons:
    """Icon names understood by the Android ``ViewFactory``."""

    STAR = "star"
    HOME = "home"
    SEARCH = "search"
    SETTINGS = "settings"
    INFO = "info"
    EDIT = "edit"
    DELETE = "delete"
    ADD = "add"
    SHARE = "share"
    EMAIL = "email"
    CALL = "call"
    MENU = "menu"
    CLOSE = "close"
    BACK = "back"
    FORWARD = "forward"
    REFRESH = "refresh"
    SAVE = "save"
    UPLOAD = "upload"
    CAMERA = "camera"
    GALLERY = "gallery"
    LOCK = "lock"
    PERSON = "person"
    AGENDA = "agenda"
    SORT = "sort"
    HELP = "help"
    FAVORITE = "favorite"
    FAVORITE_BORDER = "favorite_border"
    BOOKMARK = "bookmark"
    NOTIFICATIONS = "notifications"
    CHECK = "check"
    CHECK_CIRCLE = "check_circle"
    CANCEL = "cancel"
    WARNING = "warning"
    ERROR = "error"
    DOWNLOAD = "download"
    FOLDER = "folder"
    FILE = "file"
    IMAGE = "image"
    VIDEO = "video"
    MUSIC = "music"
    MIC = "mic"
    PLAY = "play"
    PAUSE = "pause"
    STOP = "stop"
    SKIP_NEXT = "skip_next"
    SKIP_PREVIOUS = "skip_previous"
    VOLUME = "volume"
    LOCATION = "location"
    MAP = "map"
    CALENDAR = "calendar"
    CLOCK = "clock"
    FILTER = "filter"
    MORE_VERT = "more_vert"
    MORE_HORIZ = "more_horiz"
    EXPAND_MORE = "expand_more"
    EXPAND_LESS = "expand_less"
    CHEVRON_RIGHT = "chevron_right"
    CHEVRON_LEFT = "chevron_left"
    LOGOUT = "logout"
    LOGIN = "login"
    CART = "cart"
    PAYMENT = "payment"
    WIFI = "wifi"
    BLUETOOTH = "bluetooth"
    BATTERY = "battery"
    DARK_MODE = "dark_mode"
    LIGHT_MODE = "light_mode"
    VISIBILITY = "visibility"
    VISIBILITY_OFF = "visibility_off"
    COPY = "copy"
    PASTE = "paste"
    LINK = "link"
    SEND = "send"
    CHAT = "chat"
    GROUP = "group"
    DASHBOARD = "dashboard"
    LIST = "list"
    GRID = "grid"

    @classmethod
    def all(cls) -> list[str]:
        return sorted(
            value for name, value in vars(cls).items()
            if name.isupper() and isinstance(value, str)
        )


class Theme:
    """App-wide default colours used by widgets that opt in."""

    primary: str = Colors.PRIMARY
    background: str = Colors.BACKGROUND
    surface: str = Colors.SURFACE
    text: str = Colors.TEXT
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
    def dark(cls) -> None:
        """Switch to a sensible dark palette."""
        cls.apply(
            background="#FF111827",
            surface="#FF1F2937",
            text="#FFF9FAFB",
            dark_mode=True,
        )

    @classmethod
    def light(cls) -> None:
        """Switch back to the default light palette."""
        cls.apply(
            background=Colors.BACKGROUND,
            surface=Colors.SURFACE,
            text=Colors.TEXT,
            dark_mode=False,
        )

    @classmethod
    def as_dict(cls) -> dict:
        return {
            "primary": cls.primary,
            "background": cls.background,
            "surface": cls.surface,
            "text": cls.text,
            "dark_mode": cls.dark_mode,
        }


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
        if dark:
            scheme = cls(
                primary=_tone(r, g, b, 1.25),
                on_primary="#FF111827",
                primary_container=_tone(r, g, b, 0.45),
                secondary=_tone(b, r, g, 1.15),
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
                secondary=_tone(b, r, g, 0.95),
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

    def __repr__(self) -> str:
        return f"<ColorScheme primary={self.primary} dark={self.dark}>"


class Typography:
    """The Material 3 type scale, in sp."""

    DISPLAY = {"size": 45, "weight": 400}
    HEADLINE = {"size": 32, "weight": 600}
    TITLE = {"size": 22, "weight": 600}
    TITLE_SMALL = {"size": 16, "weight": 600}
    BODY = {"size": 16, "weight": 400}
    BODY_SMALL = {"size": 14, "weight": 400}
    LABEL = {"size": 14, "weight": 500}
    CAPTION = {"size": 12, "weight": 400}

    @classmethod
    def scale(cls, factor: float) -> dict:
        """Return the whole scale multiplied by *factor* (accessibility)."""
        out = {}
        for name, spec in vars(cls).items():
            if name.isupper() and isinstance(spec, dict):
                out[name.lower()] = {"size": round(spec["size"] * factor, 1),
                                     "weight": spec["weight"]}
        return out


def _rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    if len(c) == 8:
        c = c[2:]
    if len(c) != 6:
        raise ValueError(f"Unsupported colour format: {color!r}")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _tone(r: int, g: int, b: int, factor: float) -> str:
    """Lighten (>1) or darken (<1) a colour, clamped to the 8-bit range."""
    def _clamp(v: float) -> int:
        return max(0, min(255, int(round(v))))

    if factor >= 1:
        # Blend towards white so highlights do not clip to a flat colour.
        t = min(1.0, factor - 1.0)
        return _argb("%02X%02X%02X" % (_clamp(r + (255 - r) * t),
                                       _clamp(g + (255 - g) * t),
                                       _clamp(b + (255 - b) * t)))
    return _argb("%02X%02X%02X" % (_clamp(r * factor), _clamp(g * factor),
                                   _clamp(b * factor)))


def _theme_use(cls, scheme: "ColorScheme") -> None:
    """Adopt a :class:`ColorScheme` as the app theme."""
    cls.apply(primary=scheme.primary, background=scheme.background,
              surface=scheme.surface, text=scheme.on_surface,
              dark_mode=scheme.dark)
    cls.scheme = scheme


Theme.use = classmethod(_theme_use)
Theme.scheme = ColorScheme.from_seed()
Theme.typography = Typography
