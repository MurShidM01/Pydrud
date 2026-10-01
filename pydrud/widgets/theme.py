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
