"""
The icon-name catalogue understood by the Android ``ViewFactory``.
"""

from __future__ import annotations

import re

from pydrud.widgets.theme._common import _ConstantsMeta, _token_name


class _IconsMeta(_ConstantsMeta):
    """Forgiving spellings, plus icons registered at runtime by a pack."""

    def __getattr__(cls, name: str):
        # ``Icons.favorite``, ``Icons.favoriteBorder`` and
        # ``Icons.FAVORITE_BORDER`` all resolve to the same documented value;
        # unknown names get the same "did you mean" error as the tokens.
        try:
            return super().__getattr__(name)
        except AttributeError:
            for key in (name, _token_name(name)):
                value = cls._external.get(key)
                if isinstance(value, str):
                    return value
            raise


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
        raw = str(name).replace("-", "_")
        token = raw if raw.isupper() else re.sub(r"(?<!^)([A-Z])", r"_\1", raw).upper()
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
            raw = str(name).replace("-", "_")
            token = raw if raw.isupper() else re.sub(r"(?<!^)([A-Z])", r"_\1", raw).upper()
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
        if not isinstance(value, str):
            value = cls._external.get(token)
        return value if isinstance(value, str) else raw.lower().replace("-", "_")

    @classmethod
    def builtins(cls) -> list[str]:
        """Renderer names the framework itself ships.

        Unlike :meth:`all` this excludes icons registered at runtime from
        optional packs, so generated-code checks (and documentation) can
        reason about the constants Pydrud itself guarantees — pack icons
        are only known after ``Icons.load_pack`` runs inside an app.
        """
        return sorted({
            value for name, value in vars(cls).items()
            if name.isupper() and isinstance(value, str)
        })

    @classmethod
    def all(cls) -> list[str]:
        return sorted({*cls.builtins(), *cls._external.values()})
