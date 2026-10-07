"""
Responsive engine — real device-resolution detection and adaptive sizing.

Three layers, all driven by live metrics reported by the connected client:

- ``Breakpoints`` — the (fully customisable) window-size-class table.
- ``MediaQuery`` — metrics the client reports: logical size, pixel size,
  density, dpi, orientation, safe-area insets, font scale, diagonal,
  keyboard height, dark mode, …  Plus change listeners.
- ``Responsive`` — sizing helpers built on top: scaled dp/sp values,
  percent-of-screen units, breakpoint value pickers, grid maths.

The bridge sends a ``ready`` event on connect **and** a ``metrics``
event every time the window changes (rotation, split screen, folding
state, font-scale change, keyboard, insets). ``App`` feeds both into
:meth:`MediaQuery.update`, which refreshes :class:`Responsive`, notifies
listeners and re-renders the tree — so layouts genuinely follow the
current window instead of guessing once at startup.

Quick tour::

    from pydrud import MediaQuery, Responsive

    MediaQuery.width            # dp
    MediaQuery.height_px        # physical pixels
    MediaQuery.orientation      # "portrait" / "landscape"
    MediaQuery.device_type      # "phone" / "tablet" / "desktop" / "tv"
    MediaQuery.breakpoint       # "compact" / "medium" / "expanded" / ...
    MediaQuery.safe_area()      # {"top": 48, "bottom": 24, ...}

    Responsive.text(16)                     # scaled font size
    Responsive.wp(50)                       # 50% of screen width (dp)
    Responsive.value(compact=1, expanded=3) # pick per size class
    Responsive.columns(min_width=180)       # grid columns that fit

Everything degrades gracefully: with no device connected the metrics are
a 360x640 phone, so unit tests and desktop previews still work.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = ["Breakpoints", "MediaQuery", "Responsive", "ScreenInfo"]


# ──────────────────────────────────────────────────────────────────────────
# Breakpoints
# ──────────────────────────────────────────────────────────────────────────


class Breakpoints:
    """The window size-class table — customisable per app.

    Defaults follow Material 3 / Flutter adaptive guidance (dp)::

        compact   <  600    phones, portrait
        medium    >= 600    small tablets, unfolded foldables, landscape phones
        expanded  >= 840    tablets, split-screen desktops
        large     >= 1200   desktop windows
        xlarge    >= 1600   large desktop / TV

    Change them once at startup::

        Breakpoints.configure(medium=620, expanded=900)
    """

    medium: float = 600
    expanded: float = 840
    large: float = 1200
    xlarge: float = 1600

    #: Order, smallest first — used by value pickers and fallbacks.
    ORDER: Tuple[str, ...] = ("compact", "medium", "expanded", "large", "xlarge")

    #: Friendly aliases accepted by ``Responsive.value()``.
    ALIASES: Dict[str, str] = {
        "xs": "compact",
        "small": "compact",
        "phone": "compact",
        "mobile": "compact",
        "sm": "medium",
        "tablet": "medium",
        "md": "expanded",
        "lg": "large",
        "laptop": "large",
        "desktop": "large",
        "xl": "xlarge",
        "tv": "xlarge",
    }

    _DEFAULTS = {"medium": 600, "expanded": 840, "large": 1200, "xlarge": 1600}

    @classmethod
    def configure(cls, **kwargs: float) -> None:
        """Override one or more breakpoint widths (dp)."""
        for name, value in kwargs.items():
            if name not in cls._DEFAULTS:
                raise ValueError(
                    f"Unknown breakpoint {name!r}; "
                    f"expected one of {sorted(cls._DEFAULTS)}")
            setattr(cls, name, float(value))
        cls._validate()

    @classmethod
    def reset(cls) -> None:
        """Restore the Material 3 defaults."""
        for name, value in cls._DEFAULTS.items():
            setattr(cls, name, float(value))

    @classmethod
    def classify(cls, width_dp: float) -> str:
        """Return the size class name for *width_dp*."""
        if width_dp >= cls.xlarge:
            return "xlarge"
        if width_dp >= cls.large:
            return "large"
        if width_dp >= cls.expanded:
            return "expanded"
        if width_dp >= cls.medium:
            return "medium"
        return "compact"

    @classmethod
    def index(cls, name: str) -> int:
        """Index of a size class in :attr:`ORDER` (aliases allowed)."""
        key = cls.ALIASES.get(name, name)
        if key not in cls.ORDER:
            raise ValueError(f"Unknown size class {name!r}")
        return cls.ORDER.index(key)

    @classmethod
    def _validate(cls) -> None:
        values = [cls.medium, cls.expanded, cls.large, cls.xlarge]
        if any(b <= a for a, b in zip(values, values[1:])):
            raise ValueError(
                "Breakpoints must increase: medium < expanded < large < xlarge")


# ──────────────────────────────────────────────────────────────────────────
# ScreenInfo — an immutable snapshot
# ──────────────────────────────────────────────────────────────────────────


class ScreenInfo:
    """An immutable snapshot of the device metrics.

    Returned by :meth:`MediaQuery.info` and handed to
    :class:`~pydrud.widgets.responsive.ResponsiveBuilder` builders, so a
    build function can read metrics without touching global state.
    """

    __slots__ = ("_d",)

    def __init__(self, data: Dict[str, Any]):
        self._d = dict(data)

    # Dict-ish access keeps backwards compatibility with ``MediaQuery.of()``.
    def __getitem__(self, item: str) -> Any:
        return self._d[item]

    def get(self, item: str, default: Any = None) -> Any:
        return self._d.get(item, default)

    def as_dict(self) -> Dict[str, Any]:
        data = dict(self._d)
        data["sdk"] = _legacy_sdk_value(data)
        return data

    def __iter__(self):
        return iter(self._d)

    def __contains__(self, item) -> bool:
        return item in self._d

    def __eq__(self, other) -> bool:
        if isinstance(other, ScreenInfo):
            return self._d == other._d
        if isinstance(other, dict):
            return self._d == other
        return NotImplemented

    def __repr__(self) -> str:
        return (f"ScreenInfo({self.width}x{self.height}dp, "
                f"{self.breakpoint}, {self.orientation})")

    # Attribute access for every metric.
    def __getattr__(self, item: str) -> Any:
        if item == "sdk":
            return _legacy_sdk_value(self._d)
        try:
            return self._d[item]
        except KeyError:
            raise AttributeError(item) from None


# ──────────────────────────────────────────────────────────────────────────
# MediaQuery
# ──────────────────────────────────────────────────────────────────────────


def _whole(value: float):
    """Keep dp values as ints when they are whole, so UI text reads nicely."""
    return int(value) if float(value).is_integer() else value


def _legacy_sdk_value(data: Dict[str, Any]) -> int:
    """Numeric compatibility view of the old ``MediaQuery.sdk`` metric."""
    try:
        value = float(data.get("platform_version", ""))
    except (TypeError, ValueError):
        return 0
    return int(value) if value.is_integer() else 0


def _as_float(value: Any, fallback: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    if out != out:  # NaN
        return fallback
    return out


class _CallableStr(str):
    """A string that is also callable.

    ``MediaQuery.breakpoint`` is a metric *and* was a method before v1.5,
    so both ``MediaQuery.breakpoint`` and ``MediaQuery.breakpoint()``
    return the same value.
    """

    def __call__(self) -> str:
        return str(self)


class _MediaQueryMeta(type):
    """Exposes every metric as a read-only class attribute."""

    def __getattr__(cls, item: str) -> Any:
        data = cls.__dict__.get("_data") or {}
        if item == "sdk":
            return _legacy_sdk_value(data)
        if item in data:
            value = data[item]
            # ``MediaQuery.breakpoint`` used to be a method; returning a
            # callable string keeps both spellings working.
            if item in ("breakpoint", "orientation", "device_type"):
                return _CallableStr(value)
            return value
        raise AttributeError(item)


class MediaQuery(metaclass=_MediaQueryMeta):
    """Live device metrics — the single source of truth for responsiveness.

    Read metrics as class attributes (``MediaQuery.width``), as a dict
    (``MediaQuery.of()``) or as a snapshot (``MediaQuery.info()``).

    Available metrics:

    ===================== ==================================================
    ``width`` ``height``  Window size in **dp**
    ``width_px``          Window size in physical pixels
    ``height_px``
    ``density``           Pixels per dp (``2.0`` = xhdpi)
    ``dpi``               Physical dots per inch
    ``text_scale``        User font-size preference (1.0 = default)
    ``orientation``       ``"portrait"`` / ``"landscape"``
    ``breakpoint``        ``compact`` … ``xlarge`` (see :class:`Breakpoints`)
    ``device_type``       ``phone`` / ``tablet`` / ``desktop`` / ``tv``
    ``shortest_side``     Smaller of width/height, dp — the tablet test
    ``longest_side``      Larger of width/height, dp
    ``aspect_ratio``      ``width / height``
    ``diagonal``          Screen diagonal in inches (approx.)
    ``status_bar_height`` Inset heights in dp
    ``navigation_bar_height``
    ``padding_*``         Safe-area insets (top/bottom/left/right) in dp
    ``keyboard_height``   Visible IME height in dp (0 when hidden)
    ``dark``              True when the system is in dark mode
    ``refresh_rate``      Display refresh rate in Hz
    ``platform_version``   Optional client operating-system version
    ``sdk``                Deprecated numeric alias for older clients
    ===================== ==================================================
    """

    _DEFAULTS: Dict[str, Any] = {
        "width": 360,
        "height": 640,
        "width_px": 720,
        "height_px": 1280,
        "density": 2.0,
        "dpi": 320.0,
        "scale_factor": 1.0,
        "text_scale": 1.0,
        "status_bar_height": 24,
        "navigation_bar_height": 0,
        "padding_top": 0,
        "padding_bottom": 0,
        "padding_left": 0,
        "padding_right": 0,
        "keyboard_height": 0,
        "dark": False,
        "refresh_rate": 60.0,
        "platform_version": "",
        # Derived — recomputed by _derive().
        "orientation": "portrait",
        "breakpoint": "compact",
        "device_type": "phone",
        "shortest_side": 360,
        "longest_side": 640,
        "aspect_ratio": 0.5625,
        "diagonal": 5.0,
    }

    _data: Dict[str, Any] = dict(_DEFAULTS)
    _listeners: List[Callable[["ScreenInfo"], None]] = []

    #: A tablet is defined by its *shortest* logical side — a landscape
    #: phone is not a tablet.
    TABLET_SHORTEST_SIDE = 600
    DESKTOP_SHORTEST_SIDE = 900

    # ── ingest ──────────────────────────────────────────────────────────

    @classmethod
    def init(
        cls,
        width_dp: float = 360,
        height_dp: float = 640,
        density: float = 2.0,
        status_bar_height: float = 24,
        text_scale: float = 1.0,
        **kwargs: Any,
    ) -> bool:
        """Set the metrics from a ``ready``/``metrics`` payload.

        Returns ``True`` when anything actually changed.
        """
        return cls.update(
            width=width_dp,
            height=height_dp,
            density=density,
            status_bar_height=status_bar_height,
            text_scale=text_scale,
            **kwargs,
        )

    @classmethod
    def update(cls, **metrics: Any) -> bool:
        """Merge raw metrics in, re-derive, sync ``Responsive``, notify.

        Unknown keys are kept for forward compatibility. Returns ``True`` when
        the metrics snapshot changed.
        """
        before = dict(cls._data)
        data = cls._data

        # Accept both the bridge names and the public names.
        rename = {"width_dp": "width", "height_dp": "height"}
        # Accept ``sdk`` from legacy runtime handshakes while exposing only
        # the transport-neutral ``platform_version`` metric.
        rename["sdk"] = "platform_version"
        for key, value in metrics.items():
            if value is None:
                continue
            data[rename.get(key, key)] = value

        if "width_px" in metrics or "height_px" in metrics:
            cls._px_reported = True
        cls._coerce()
        cls._derive()

        changed = data != before
        if changed:
            Responsive._sync()
            cls._notify()
        return changed

    @classmethod
    def reset(cls) -> None:
        """Restore the default (360x640 phone) metrics — mainly for tests."""
        cls._data = dict(cls._DEFAULTS)
        cls._px_reported = False
        Responsive._sync()

    # ── derived values ──────────────────────────────────────────────────

    @classmethod
    def _coerce(cls) -> None:
        d = cls._data
        d["width"] = _whole(max(_as_float(d.get("width"), 360), 1))
        d["height"] = _whole(max(_as_float(d.get("height"), 640), 1))
        d["density"] = max(_as_float(d.get("density"), 2.0), 0.1)
        d["text_scale"] = max(_as_float(d.get("text_scale"), 1.0), 0.1)
        for key in ("status_bar_height", "navigation_bar_height",
                    "padding_top", "padding_bottom", "padding_left",
                    "padding_right", "keyboard_height"):
            d[key] = _whole(max(_as_float(d.get(key), 0), 0))
        d["dark"] = bool(d.get("dark", False))
        d["platform_version"] = str(d.get("platform_version", "") or "")[:100]

        # Pixels follow dp * density unless the device reported them.
        if not cls._px_reported:
            d["width_px"] = int(round(d["width"] * d["density"]))
            d["height_px"] = int(round(d["height"] * d["density"]))
        d["dpi"] = _as_float(d.get("dpi"), d["density"] * 160.0) or 160.0

    _px_reported: bool = False

    @classmethod
    def _derive(cls) -> None:
        d = cls._data
        width, height = d["width"], d["height"]
        d["orientation"] = "landscape" if width > height else "portrait"
        d["shortest_side"] = _whole(min(width, height))
        d["longest_side"] = _whole(max(width, height))
        d["aspect_ratio"] = width / height if height else 1.0
        d["breakpoint"] = Breakpoints.classify(width)
        d["scale_factor"] = width / Responsive._BASELINE_WIDTH

        short = d["shortest_side"]
        if short >= cls.DESKTOP_SHORTEST_SIDE:
            d["device_type"] = "desktop"
        elif short >= cls.TABLET_SHORTEST_SIDE:
            d["device_type"] = "tablet"
        else:
            d["device_type"] = "phone"
        if d.get("ui_mode") == "television":
            d["device_type"] = "tv"
        elif d.get("ui_mode") == "watch":
            d["device_type"] = "watch"

        dpi = d["dpi"] or 160.0
        inches_w = d["width_px"] / dpi
        inches_h = d["height_px"] / dpi
        d["diagonal"] = round((inches_w ** 2 + inches_h ** 2) ** 0.5, 2)

    # ── listeners ───────────────────────────────────────────────────────

    @classmethod
    def listen(cls, callback: Callable[["ScreenInfo"], None]) -> Callable[[], None]:
        """Call *callback* whenever the metrics change (rotation, resize).

        Returns a function that unsubscribes::

            stop = MediaQuery.listen(lambda info: print(info.breakpoint))
            stop()
        """
        if not callable(callback):
            raise TypeError("MediaQuery.listen() expects a callable")
        cls._listeners.append(callback)

        def _unsubscribe() -> None:
            try:
                cls._listeners.remove(callback)
            except ValueError:
                pass

        return _unsubscribe

    @classmethod
    def clear_listeners(cls) -> None:
        cls._listeners.clear()

    @classmethod
    def _notify(cls) -> None:
        info = cls.info()
        for callback in list(cls._listeners):
            try:
                callback(info)
            except Exception:  # A broken listener must not kill rendering.
                pass

    # ── reads ───────────────────────────────────────────────────────────

    @classmethod
    def of(cls) -> Dict[str, Any]:
        """A plain-dict snapshot of every metric, including the legacy ``sdk`` alias."""
        data = dict(cls._data)
        data["sdk"] = _legacy_sdk_value(data)
        return data

    @classmethod
    def info(cls) -> ScreenInfo:
        """An immutable snapshot with attribute access."""
        return ScreenInfo(cls._data)

    @classmethod
    def size(cls) -> Tuple[float, float]:
        """``(width_dp, height_dp)``."""
        return (cls._data["width"], cls._data["height"])

    @classmethod
    def resolution(cls) -> Tuple[int, int]:
        """``(width_px, height_px)`` — the physical resolution."""
        return (int(cls._data["width_px"]), int(cls._data["height_px"]))

    @classmethod
    def safe_area(cls) -> Dict[str, float]:
        """Insets (dp) occupied by system bars and display cutouts."""
        d = cls._data
        return {
            "top": d.get("padding_top", 0) or d.get("status_bar_height", 0),
            "bottom": d.get("padding_bottom", 0) or d.get("navigation_bar_height", 0),
            "left": d.get("padding_left", 0),
            "right": d.get("padding_right", 0),
        }

    @classmethod
    def viewport(cls) -> Tuple[float, float]:
        """Usable size (dp) after safe-area insets and the keyboard."""
        insets = cls.safe_area()
        width = cls._data["width"] - insets["left"] - insets["right"]
        height = (cls._data["height"] - insets["top"] - insets["bottom"]
                  - cls._data.get("keyboard_height", 0))
        return (max(width, 1), max(height, 1))

    # ── predicates ──────────────────────────────────────────────────────

    @classmethod
    def is_phone(cls) -> bool:
        return cls._data["device_type"] in ("phone", "watch")

    @classmethod
    def is_tablet(cls) -> bool:
        return cls._data["device_type"] in ("tablet", "desktop", "tv")

    @classmethod
    def is_desktop(cls) -> bool:
        return cls._data["device_type"] in ("desktop", "tv")

    @classmethod
    def is_landscape(cls) -> bool:
        return cls._data["orientation"] == "landscape"

    @classmethod
    def is_portrait(cls) -> bool:
        return cls._data["orientation"] == "portrait"

    @classmethod
    def is_dark(cls) -> bool:
        return bool(cls._data.get("dark", False))

    @classmethod
    def keyboard_visible(cls) -> bool:
        return cls._data.get("keyboard_height", 0) > 0

    @classmethod
    def breakpoint_name(cls) -> str:
        return cls._data["breakpoint"]

    @classmethod
    def at_least(cls, size_class: str) -> bool:
        """True when the window is *size_class* or wider."""
        return Breakpoints.index(cls._data["breakpoint"]) >= Breakpoints.index(size_class)

    @classmethod
    def at_most(cls, size_class: str) -> bool:
        """True when the window is *size_class* or narrower."""
        return Breakpoints.index(cls._data["breakpoint"]) <= Breakpoints.index(size_class)

    @classmethod
    def matches(cls, *, min_width: Optional[float] = None,
                max_width: Optional[float] = None,
                min_height: Optional[float] = None,
                max_height: Optional[float] = None,
                orientation: Optional[str] = None,
                device: Optional[str] = None) -> bool:
        """A CSS-style media query::

            if MediaQuery.matches(min_width=600, orientation="landscape"):
                ...
        """
        d = cls._data
        if min_width is not None and d["width"] < min_width:
            return False
        if max_width is not None and d["width"] > max_width:
            return False
        if min_height is not None and d["height"] < min_height:
            return False
        if max_height is not None and d["height"] > max_height:
            return False
        if orientation is not None and d["orientation"] != orientation:
            return False
        if device is not None and d["device_type"] != device:
            return False
        return True


# ──────────────────────────────────────────────────────────────────────────
# Responsive
# ──────────────────────────────────────────────────────────────────────────


class Responsive:
    """Screen-aware sizing built on :class:`MediaQuery`.

    Sizes scale with the window but are **clamped** (0.9x – 1.2x by
    default) so a tablet gets a tablet *layout* instead of a zoomed-in
    phone.  Layout changes come from breakpoints and percent units::

        Responsive.text(16)                      # scaled sp
        Responsive.w(56)                         # scaled dp
        Responsive.wp(50)                        # 50% of the screen width
        Responsive.hp(33.3)                      # a third of the height
        Responsive.sp(14)                        # honours the user font scale
        Responsive.value(compact=1, expanded=3)  # per size class
        Responsive.columns(min_width=180)        # grid columns that fit

    Tune the clamp with :meth:`configure`.
    """

    _BASELINE_WIDTH = 360
    _BASELINE_HEIGHT = 640

    _MIN_FACTOR = 0.9
    _MAX_FACTOR = 1.2
    _DEFAULT_MIN_FACTOR = 0.9
    _DEFAULT_MAX_FACTOR = 1.2

    #: ``"width"`` (default), ``"shortest"`` or ``"diagonal"``.
    _BASIS = "shortest"

    #: Material 3 window size classes (kept for backwards compatibility).
    BREAKPOINT_MEDIUM = 600
    BREAKPOINT_EXPANDED = 840

    # Mirrors of the MediaQuery metrics, kept in sync by ``_sync()``.
    _screen_width: float = 360
    _screen_height: float = 640
    _density: float = 2.0
    _scale_factor: float = 1.0
    _text_scale: float = 1.0

    # ── configuration ───────────────────────────────────────────────────

    @classmethod
    def configure(cls, *, min_factor: Optional[float] = None,
                  max_factor: Optional[float] = None,
                  basis: Optional[str] = None,
                  baseline_width: Optional[float] = None,
                  baseline_height: Optional[float] = None) -> None:
        """Tune how aggressively sizes scale.

        ``basis="width"`` scales with the window width (good for phones),
        ``"shortest"`` with the shortest side (stable across rotation,
        the default) and ``"diagonal"`` with the screen diagonal.
        """
        # Validate everything *before* mutating, so a rejected call leaves
        # the configuration exactly as it was.
        new_min = cls._MIN_FACTOR if min_factor is None else float(min_factor)
        new_max = cls._MAX_FACTOR if max_factor is None else float(max_factor)
        if new_min > new_max:
            raise ValueError("min_factor must be <= max_factor")
        if basis is not None and basis not in ("width", "shortest", "diagonal"):
            raise ValueError("basis must be width, shortest or diagonal")
        cls._MIN_FACTOR, cls._MAX_FACTOR = new_min, new_max
        if basis is not None:
            cls._BASIS = basis
        if baseline_width is not None:
            cls._BASELINE_WIDTH = float(baseline_width)
        if baseline_height is not None:
            cls._BASELINE_HEIGHT = float(baseline_height)
        cls._sync()

    @classmethod
    def configure_reset(cls) -> None:
        cls._MIN_FACTOR = cls._DEFAULT_MIN_FACTOR
        cls._MAX_FACTOR = cls._DEFAULT_MAX_FACTOR
        cls._BASIS = "shortest"
        cls._BASELINE_WIDTH = 360
        cls._BASELINE_HEIGHT = 640
        cls._sync()

    # ── initialisation ──────────────────────────────────────────────────

    @classmethod
    def init(cls, width_dp: float, height_dp: float, density: float,
             text_scale: float = 1.0, **kwargs: Any) -> None:
        """Set the device metrics (delegates to :meth:`MediaQuery.update`)."""
        MediaQuery.update(width=width_dp, height=height_dp, density=density,
                          text_scale=text_scale, **kwargs)

    @classmethod
    def reset(cls) -> None:
        """Restore the default (baseline) metrics — mainly for tests."""
        MediaQuery.reset()

    @classmethod
    def _sync(cls) -> None:
        """Copy the current MediaQuery metrics onto the class mirrors."""
        d = MediaQuery._data
        cls._screen_width = d["width"]
        cls._screen_height = d["height"]
        cls._density = d["density"]
        cls._text_scale = d["text_scale"]
        cls._scale_factor = d["width"] / cls._BASELINE_WIDTH

    # ── scaled sizes ────────────────────────────────────────────────────

    @classmethod
    def text(cls, size: float) -> int:
        """Scale a font size (sp), ignoring the user's font preference."""
        return cls._scale(size)

    @classmethod
    def sp(cls, size: float, *, max_scale: float = 1.3) -> int:
        """Scale a font size **and** honour the system font-size setting.

        ``max_scale`` caps accessibility scaling so huge system fonts do
        not destroy the layout (Flutter's ``textScaleFactor`` clamp).
        """
        scale = min(MediaQuery._data["text_scale"], max_scale)
        return int(round(size * cls._factor() * scale))

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

    # ── percent units ───────────────────────────────────────────────────

    @classmethod
    def wp(cls, percent: float) -> int:
        """*percent* of the screen **width**, in dp (``wp(50)`` = half)."""
        return int(round(MediaQuery._data["width"] * percent / 100.0))

    @classmethod
    def hp(cls, percent: float) -> int:
        """*percent* of the screen **height**, in dp."""
        return int(round(MediaQuery._data["height"] * percent / 100.0))

    @classmethod
    def vw(cls, percent: float) -> int:
        """CSS-style viewport width unit (safe area excluded)."""
        return int(round(MediaQuery.viewport()[0] * percent / 100.0))

    @classmethod
    def vh(cls, percent: float) -> int:
        """CSS-style viewport height unit (safe area and keyboard excluded)."""
        return int(round(MediaQuery.viewport()[1] * percent / 100.0))

    @classmethod
    def sw(cls, percent: float = 100) -> int:
        """*percent* of the **shortest** side, in dp."""
        return int(round(MediaQuery._data["shortest_side"] * percent / 100.0))

    @classmethod
    def px(cls, pixels: float) -> int:
        """Convert physical pixels to dp."""
        return int(round(pixels / MediaQuery._data["density"]))

    @classmethod
    def to_px(cls, dp: float) -> int:
        """Convert dp to physical pixels."""
        return int(round(dp * MediaQuery._data["density"]))

    # ── accessors ───────────────────────────────────────────────────────

    @classmethod
    def factor(cls) -> float:
        """The raw scale factor (``screen_width / baseline``)."""
        return cls._scale_factor

    @classmethod
    def screen_width(cls) -> float:
        return MediaQuery._data["width"]

    @classmethod
    def screen_height(cls) -> float:
        return MediaQuery._data["height"]

    @classmethod
    def density(cls) -> float:
        return MediaQuery._data["density"]

    @classmethod
    def text_scale(cls) -> float:
        return MediaQuery._data["text_scale"]

    @classmethod
    def orientation(cls) -> str:
        return MediaQuery._data["orientation"]

    @classmethod
    def device_type(cls) -> str:
        return MediaQuery._data["device_type"]

    @classmethod
    def is_landscape(cls) -> bool:
        return MediaQuery.is_landscape()

    @classmethod
    def is_portrait(cls) -> bool:
        return MediaQuery.is_portrait()

    @classmethod
    def is_phone(cls) -> bool:
        """True for compact widths (< 600 dp)."""
        return MediaQuery._data["width"] < Breakpoints.medium

    @classmethod
    def is_tablet(cls) -> bool:
        """True for medium and wider windows (>= 600 dp)."""
        return MediaQuery._data["width"] >= Breakpoints.medium

    @classmethod
    def is_desktop(cls) -> bool:
        return MediaQuery._data["width"] >= Breakpoints.large

    @classmethod
    def breakpoint(cls) -> str:
        """The window size class: compact/medium/expanded/large/xlarge."""
        return MediaQuery._data["breakpoint"]

    @classmethod
    def at_least(cls, size_class: str) -> bool:
        return MediaQuery.at_least(size_class)

    @classmethod
    def at_most(cls, size_class: str) -> bool:
        return MediaQuery.at_most(size_class)

    # ── adaptive pickers ────────────────────────────────────────────────

    @classmethod
    def value(cls, compact: Any = None, medium: Any = None,
              expanded: Any = None, **aliases: Any) -> Any:
        """Pick a value for the current window size class.

        ::

            columns = Responsive.value(compact=1, medium=2, expanded=3)
            pad     = Responsive.value(phone=16, tablet=32, desktop=48)
            gap     = Responsive.value(compact=8, portrait=8, landscape=16)

        Missing classes fall back to the next **smaller** one, so passing
        only ``compact`` always works.  ``portrait=`` / ``landscape=`` and
        ``phone=`` / ``tablet=`` / ``desktop=`` / ``tv=`` are accepted as
        aliases, and an explicit ``default=`` covers everything else.
        """
        default = aliases.pop("default", None)

        # Orientation overrides win when they match.
        orientation = MediaQuery._data["orientation"]
        if orientation in aliases and aliases[orientation] is not None:
            return aliases[orientation]
        aliases.pop("portrait", None)
        aliases.pop("landscape", None)

        resolved: Dict[str, Any] = {name: None for name in Breakpoints.ORDER}
        resolved["compact"] = compact
        resolved["medium"] = medium
        resolved["expanded"] = expanded
        for name, value in aliases.items():
            key = Breakpoints.ALIASES.get(name, name)
            if key not in resolved:
                raise TypeError(f"Responsive.value() got unexpected size {name!r}")
            if value is not None and resolved[key] is None:
                resolved[key] = value

        # Fill gaps upwards: each class inherits the next smaller value.
        last = default
        for name in Breakpoints.ORDER:
            if resolved[name] is None:
                resolved[name] = last
            else:
                last = resolved[name]

        current = resolved[MediaQuery._data["breakpoint"]]
        return current if current is not None else default

    @classmethod
    def when(cls, **cases: Any) -> Any:
        """Alias of :meth:`value` that reads better for layouts."""
        return cls.value(**cases)

    @classmethod
    def select(cls, options: Dict[str, Any], default: Any = None) -> Any:
        """Dict form of :meth:`value`: ``{"compact": ..., "expanded": ...}``."""
        return cls.value(default=default, **options)

    @classmethod
    def columns(cls, min_width: float = 160, *, max_columns: int = 12,
                gutter: float = 16) -> int:
        """How many grid columns of at least *min_width* dp fit."""
        usable = max(MediaQuery._data["width"] - gutter, 1)
        count = int(usable // max(min_width + gutter / 2, 1))
        return max(1, min(max_columns, count))

    @classmethod
    def grid(cls, min_width: float = 160, *, gutter: float = 16,
             max_columns: int = 12) -> Tuple[int, int]:
        """``(columns, item_width_dp)`` for a responsive grid."""
        cols = cls.columns(min_width, max_columns=max_columns, gutter=gutter)
        total_gutter = gutter * (cols + 1)
        width = max(1, int((MediaQuery._data["width"] - total_gutter) / cols))
        return cols, width

    @classmethod
    def content_width(cls, max_width: float = 560) -> int:
        """Page width capped on large screens (keeps line length sane)."""
        return int(min(MediaQuery._data["width"], max_width))

    @classmethod
    def gutter(cls) -> int:
        """Page side padding that grows sensibly with the window."""
        return int(cls.value(compact=16, medium=24, expanded=32, large=48))

    @classmethod
    def clamp(cls, value: float, minimum: float, maximum: float) -> int:
        """Scale *value*, then clamp the result into a dp range."""
        return int(round(max(minimum, min(maximum, value * cls._factor()))))

    @classmethod
    def raw(cls, value: float) -> int:
        """Unclamped linear scaling (``value * screen_width / baseline``)."""
        return round(value * cls._scale_factor)

    # ── internal ────────────────────────────────────────────────────────

    @classmethod
    def _basis_factor(cls) -> float:
        d = MediaQuery._data
        if cls._BASIS == "shortest":
            return d["shortest_side"] / cls._BASELINE_WIDTH
        if cls._BASIS == "diagonal":
            baseline = (cls._BASELINE_WIDTH ** 2 + cls._BASELINE_HEIGHT ** 2) ** 0.5
            current = (d["width"] ** 2 + d["height"] ** 2) ** 0.5
            return current / baseline
        return d["width"] / cls._BASELINE_WIDTH

    @classmethod
    def _factor(cls) -> float:
        """The clamped scale factor actually used for sizing."""
        return max(cls._MIN_FACTOR, min(cls._MAX_FACTOR, cls._basis_factor()))

    @classmethod
    def _scale(cls, value: float) -> int:
        return int(round(value * cls._factor()))


# Keep the mirrors correct at import time.
Responsive._sync()
