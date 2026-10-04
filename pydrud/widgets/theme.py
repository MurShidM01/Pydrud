"""
Theme helpers — a Material colour palette and an icon-name catalogue.

These constants keep app code readable and guarantee the values are
understood by the Android renderer::

    from pydrud import Colors, Icons, Text, Icon

    Text("Hi", color=Colors.PRIMARY)
    Icon(Icons.SETTINGS)
"""

from __future__ import annotations

import re

from pydrud.widgets.tokens import Tokens


def _argb(hex_rgb: str, alpha: str = "FF") -> str:
    return f"#{alpha}{hex_rgb.upper()}"


class Colors:
    """A small, opinionated Material-ish palette (ARGB strings)."""

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


class _IconsMeta(type):
    """Offer forgiving Python spellings while keeping canonical constants."""

    def __getattr__(cls, name: str):
        # ``Icons.favorite``, ``Icons.favoriteBorder`` and
        # ``Icons.FAVORITE_BORDER`` all resolve to the same documented value.
        token = re.sub(r"(?<!^)([A-Z])", r"_\1", name).replace("-", "_").upper()
        value = vars(cls).get(token)
        if isinstance(value, str):
            return value
        value = cls._external.get(token)
        if isinstance(value, str):
            return value
        raise AttributeError(f"Icons has no icon named {name!r}")


class Icons(metaclass=_IconsMeta):
    """Icon names understood by the Android ``ViewFactory``.

    Applications may register icons from any optional pip package without
    making Pydrud depend on that package::

        from pydrud import Icons
        Icons.load_pack("simple_icons")
        Icon(Icons.BRAND_GITHUB)

    A pack is a mapping, a module exposing ``ICONS``/``icons``, or an object
    with public string attributes. Values should be Android drawable names;
    SVG/vector asset pipelines can register their own renderer names too.

    Constants are published in ``ALL_CAPS`` form, but attribute lookup is
    case-insensitive and accepts camelCase for compatibility with Flutter and
    other UI toolkits. Values remain lower-case renderer names.
    """

    _external: dict[str, str] = {}

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
    APPS = "apps"
    ACCOUNT = "account"
    PROFILE = "profile"
    PHONE = "phone"
    MESSAGE = "message"
    ATTACHMENT = "attachment"
    PRINT = "print"
    SCAN = "scan"
    QR = "qr_code"
    LOCATION_PIN = "location_pin"
    NAVIGATION = "navigation"
    COMPASS = "compass"
    SECURITY = "security"
    DATABASE = "database"
    SERVER = "server"
    API = "api"
    ANALYTICS = "analytics"
    WALLET = "wallet"
    GIFT = "gift"
    TROPHY = "trophy"
    HEART = "heart"
    HEART_BROKEN = "heart_broken"
    PLUS = "plus"
    MINUS = "minus"
    PLAY_CIRCLE = "play_circle"
    PAUSE_CIRCLE = "pause_circle"
    RECORD = "record"
    CAST = "cast"
    HOME_WORK = "home_work"
    SCHOOL = "school"
    WORK = "work"
    SHOP = "shop"
    RESTAURANT = "restaurant"
    DIRECTIONS_CAR = "directions_car"
    FLIGHT = "flight"
    HOTEL = "hotel"
    LANGUAGE = "language"
    PRINT_OUTLINE = "print_outline"

    # Developer / product icons
    CODE = "code"
    TERMINAL = "terminal"
    PYTHON = "python"
    ANDROID = "android"
    PALETTE = "palette"
    BRUSH = "brush"
    TUNE = "tune"
    LAYERS = "layers"
    ROCKET = "rocket"
    SPARKLE = "sparkle"
    LIGHTBULB = "lightbulb"
    VERIFIED = "verified"
    SHIELD = "shield"
    KEY = "key"
    LOCK_OPEN = "lock_open"
    DRAG = "drag"
    SWAP = "swap"
    SYNC = "sync"
    HISTORY = "history"
    TIMER = "timer"
    FLAG = "flag"
    TAG = "tag"
    BOOKMARK = "bookmark"
    FOLDER = "folder"
    FILE = "file"
    CLOUD = "cloud"
    DOWNLOAD = "download"
    CHART = "chart"
    PIE_CHART = "pie_chart"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    THUMB_UP = "thumb_up"
    THUMB_DOWN = "thumb_down"
    STAR_BORDER = "star_border"
    ADD_CIRCLE = "add_circle"
    REMOVE = "remove"
    QR_CODE = "qr_code"
    FINGERPRINT = "fingerprint"
    OPEN_IN_NEW = "open_in_new"
    FULLSCREEN = "fullscreen"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    UNDO = "undo"
    REDO = "redo"
    SORT = "sort"
    ARCHIVE = "archive"
    INBOX = "inbox"
    ALARM = "alarm"
    GLOBE = "globe"
    TRANSLATE = "translate"

    # Gaming & interaction icons
    ASTROPHYSICS = "astrophysics"
    GAMES = "games"
    GAMEPAD = "gamepad"
    CONTROLLER = "controller"
    JOYSTICK = "joystick"
    TOUCH_APP = "touch_app"
    TOUCH = "touch"
    ANIMATION = "animation"
    CANVAS = "canvas"
    STATE = "state"
    VIBRATION = "vibration"
    SCREEN_ROTATION = "screen_rotation"
    ARROW_BACK = "arrow_back"
    ARROW_FORWARD = "arrow_forward"
    ARROW_UP = "arrow_up"
    ARROW_DOWN = "arrow_down"
    SPARKLES = "sparkles"
    VOLUME_UP = "volume_up"
    VOLUME_OFF = "volume_off"
    VOLUME_MUTE = "volume_mute"
    MUTE = "mute"
    SOUND = "sound"
    FULLSCREEN_EXIT = "fullscreen_exit"

    # Common Flutter/Material spellings.  These aliases intentionally map to
    # renderer-backed names rather than emitting unsupported icon identifiers.
    PLAY_ARROW = PLAY
    EMOJI_EVENTS = TROPHY
    SKULL = WARNING
    LEADERBOARD = ANALYTICS
    TIMELAPSE = CLOCK
    COLLISION = CLOSE
    RESTART_ALT = UNDO
    STORAGE = DATABASE
    ARROW_BACK_IOS = ARROW_BACK
    MORE = MORE_VERT
    REFRESH_OUTLINED = REFRESH
    SETTINGS_OUTLINED = SETTINGS

    @classmethod
    def register(cls, name: str, value: str) -> str:
        """Register one optional-pack icon and return its renderer value.

        Registration is deliberately explicit: arbitrary pip packages are
        never imported during framework startup and a pack cannot overwrite a
        built-in icon constant.
        """
        token = re.sub(r"(?<!^)([A-Z])", r"_\1", str(name)).replace("-", "_").upper()
        if not token.isidentifier() or not token.isupper():
            raise ValueError("icon name must contain letters, digits or underscores")
        if token in vars(cls) and isinstance(vars(cls)[token], str):
            raise ValueError(f"cannot overwrite built-in icon {token}")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("icon value must be a non-empty string")
        cls._external[token] = value.strip()
        return cls._external[token]

    @classmethod
    def load_pack(cls, pack) -> int:
        """Load icons from a mapping, module, or installed pip icon package.

        The package is imported only when a string is supplied. Supported
        shapes are ``ICONS``/``icons`` mappings and public string attributes.
        Returns the number of newly registered icons.
        """
        if isinstance(pack, str):
            import importlib
            pack = importlib.import_module(pack)
        source = getattr(pack, "ICONS", getattr(pack, "icons", pack))
        if isinstance(source, dict):
            items = source.items()
        else:
            items = ((name, getattr(source, name)) for name in dir(source))
        added = 0
        for name, value in items:
            if str(name).startswith("_") or not isinstance(value, str):
                continue
            token = re.sub(r"(?<!^)([A-Z])", r"_\1", str(name)).replace("-", "_").upper()
            if token in vars(cls) or token in cls._external:
                continue
            cls.register(token, value)
            added += 1
        return added

    @classmethod
    def normalize(cls, name: str) -> str:
        """Normalise a constant spelling to the renderer's icon name.

        Arbitrary names are returned in a conservative lower-case form so
        generated apps can still use renderer aliases; Android performs the
        final alias lookup and supplies a visible fallback for unknown names.
        """
        raw = str(name).strip()
        token = re.sub(r"(?<!^)([A-Z])", r"_\1", raw).replace("-", "_").upper()
        value = vars(cls).get(token)
        return value if isinstance(value, str) else raw.lower().replace("-", "_")

    @classmethod
    def all(cls) -> list[str]:
        return sorted({
            *(value for name, value in vars(cls).items()
              if name.isupper() and isinstance(value, str)),
            *cls._external.values(),
        })


class Spacing:
    """The 4dp spacing scale every Pydrud layout is built on.

    Sticking to a scale is what makes a UI look designed rather than
    assembled::

        Column(spacing=Spacing.MD, children=[...])
        Container(padding=Spacing.LG, child=...)
    """

    NONE = 0
    XXS = 2
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32
    HUGE = 48

    #: Comfortable page gutter — 20dp on phones reads better than 16.
    GUTTER = 20

    @classmethod
    def scale(cls, steps: float) -> int:
        """``Spacing.scale(3)`` → 12dp. Handy for computed gaps."""
        return int(round(steps * 4))


class Radius:
    """Corner radii. Rounded-but-not-bubbly is the modern default."""

    NONE = 0
    XS = 6
    SM = 10
    MD = 14
    LG = 18
    XL = 24
    XXL = 32
    #: Fully rounded (pill) — clamped by the renderer.
    PILL = 999
    #: Semantic alias for circular avatars and square icon containers.
    #:
    #: The native renderer clamps large radii to half the shortest side, so
    #: this works for fixed and responsive containers alike.
    CIRCLE = PILL


class Elevation:
    """Shadow depths, named for intent rather than for a number."""

    FLAT = 0
    HAIRLINE = 1
    CARD = 2
    RAISED = 4
    FLOATING = 6
    DIALOG = 12
    MODAL = 16


class Motion:
    """Durations (ms) and curves — keep animations short and consistent."""

    INSTANT = 80
    FAST = 140
    NORMAL = 220
    SLOW = 320
    LAZY = 480

    STANDARD = "ease_in_out"
    ENTER = "decelerate"
    EXIT = "accelerate"
    SPRING = "overshoot"
    BOUNCE = "bounce"


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

    @classmethod
    def configure_reset(cls) -> None:
        """Restore every design token to the Pydrud default."""
        Tokens.reset()

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


def _rotate_hue(color: str, degrees: float, *, saturation: float = 1.0) -> str:
    """Rotate a colour around the hue wheel, keeping its lightness."""
    import colorsys

    r, g, b = (c / 255.0 for c in _rgb(color))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h = (h + degrees / 360.0) % 1.0
    s = max(0.0, min(1.0, s * saturation))
    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return _argb("%02X%02X%02X" % (round(nr * 255), round(ng * 255), round(nb * 255)))


def _lighten_hsl(color: str, amount: float) -> str:
    """Raise a colour's lightness without washing out its hue."""
    import colorsys

    r, g, b = (c / 255.0 for c in _rgb(color))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0.0, min(1.0, l + amount))
    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return _argb("%02X%02X%02X" % (round(nr * 255), round(ng * 255), round(nb * 255)))


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
