"""
Facades over the native bridge commands.

Each class here owns one area of the Android platform and translates Python
keyword arguments into the JSON command the ``BridgeService`` dispatches.
They are deliberately *thin*: validation and defaults live here (so mistakes
surface as Python exceptions, not silent no-ops on the device), while all
I/O goes through a single ``invoke`` callable supplied by the page.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from pydrud.core.results import Result

Invoke = Callable[..., Result]


class _Service:
    """Base class holding the page's ``invoke`` function."""

    def __init__(self, invoke: Invoke):
        self._invoke = invoke


# ──────────────────────────────────────────────────────────────────────────
# Dialogs, sheets and pickers
# ──────────────────────────────────────────────────────────────────────────


class Dialogs(_Service):
    """Material dialogs, bottom sheets and the date/time pickers."""

    def alert(self, message: str, *, title: str = "", ok: str = "OK") -> Result:
        """Show a one-button dialog. Resolves with ``True`` when dismissed."""
        return self._invoke("dialog", kind="alert", title=title,
                            message=str(message), ok=ok)

    def confirm(self, message: str, *, title: str = "", ok: str = "OK",
                cancel: str = "Cancel", destructive: bool = False) -> Result:
        """Ask a yes/no question. Resolves with ``True`` or ``False``."""
        return self._invoke("dialog", kind="confirm", title=title,
                            message=str(message), ok=ok, cancel=cancel,
                            destructive=bool(destructive))

    def prompt(self, message: str, *, title: str = "", value: str = "",
               hint: str = "", ok: str = "OK", cancel: str = "Cancel",
               obscure: bool = False) -> Result:
        """Ask for text. Resolves with the string, or ``None`` if cancelled."""
        return self._invoke("dialog", kind="prompt", title=title,
                            message=str(message), value=value, hint=hint,
                            ok=ok, cancel=cancel, obscure=bool(obscure))

    def choose(self, options: Sequence[str], *, title: str = "",
               selected: int = -1, multi: bool = False) -> Result:
        """Single- or multi-choice list. Resolves with index/list of indices."""
        items = [str(o) for o in options]
        if not items:
            raise ValueError("choose() needs at least one option")
        return self._invoke("dialog", kind="choose", title=title,
                            options=items, selected=int(selected),
                            multi=bool(multi))

    def bottom_sheet(self, options: Sequence[str], *, title: str = "",
                     icons: Optional[Sequence[str]] = None) -> Result:
        """A modal bottom sheet menu. Resolves with the chosen index."""
        return self._invoke("bottom_sheet", title=title,
                            options=[str(o) for o in options],
                            icons=list(icons or []))

    def date(self, *, initial: Optional[str] = None, min: Optional[str] = None,
             max: Optional[str] = None) -> Result:
        """Date picker. Resolves with an ISO ``YYYY-MM-DD`` string or None."""
        return self._invoke("date_picker", initial=initial, min=min, max=max)

    def time(self, *, initial: Optional[str] = None,
             use_24h: bool = True) -> Result:
        """Time picker. Resolves with ``HH:MM`` or None."""
        return self._invoke("time_picker", initial=initial, use24h=use_24h)

    def color(self, *, initial: str = "#FF6366F1") -> Result:
        """Colour picker. Resolves with an ARGB string or None."""
        return self._invoke("color_picker", initial=initial)

    def progress(self, message: str = "Please wait…", *,
                 cancellable: bool = False) -> Result:
        """Show a blocking progress dialog; dismiss with :meth:`dismiss`."""
        return self._invoke("progress_dialog", show=True, message=message,
                            cancellable=cancellable)

    def dismiss(self) -> Result:
        """Dismiss the progress dialog."""
        return self._invoke("progress_dialog", show=False)


# ──────────────────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────────────────


class Storage(_Service):
    """Key/value persistence backed by ``SharedPreferences``.

    Values are JSON-encoded on the Python side, so lists and dicts survive a
    round trip::

        page.storage.set("profile", {"name": "Ada", "pro": True})
        page.storage.get("profile", default={}).then(show_profile)
    """

    def get(self, key: str, default: Any = None) -> Result:
        return self._invoke("prefs_get", key=str(key), default=default)

    def set(self, key: str, value: Any) -> Result:
        return self._invoke("prefs_set", key=str(key), value=value)

    def remove(self, key: str) -> Result:
        return self._invoke("prefs_remove", key=str(key))

    def keys(self) -> Result:
        return self._invoke("prefs_keys")

    def clear(self) -> Result:
        return self._invoke("prefs_clear")

    def secure_set(self, key: str, value: str) -> Result:
        """Store a secret in the Android keystore-backed encrypted prefs."""
        return self._invoke("prefs_set", key=str(key), value=value, secure=True)

    def secure_get(self, key: str, default: Any = None) -> Result:
        return self._invoke("prefs_get", key=str(key), default=default,
                            secure=True)


class FilePicker(_Service):
    """The Storage Access Framework: pick, save and read files."""

    def pick(self, *, mime: str = "*/*", multiple: bool = False) -> Result:
        """Pick existing file(s). Resolves with a path (or list of paths)."""
        return self._invoke("pick_file", mime=mime, multiple=bool(multiple))

    def pick_image(self, *, camera: bool = False, multiple: bool = False) -> Result:
        """Pick an image from the gallery, or capture one with the camera."""
        return self._invoke("pick_image", camera=bool(camera),
                            multiple=bool(multiple))

    def save(self, filename: str, content: str, *,
             mime: str = "text/plain") -> Result:
        """Prompt for a location and write *content* there."""
        return self._invoke("save_file", filename=filename, content=content,
                            mime=mime)

    def read(self, path: str) -> Result:
        """Read a previously picked file as text."""
        return self._invoke("read_file", path=str(path))

    def documents_dir(self) -> Result:
        """The app's private documents directory (usable from Python ``open``)."""
        return self._invoke("app_dir", kind="documents")

    def cache_dir(self) -> Result:
        return self._invoke("app_dir", kind="cache")


# ──────────────────────────────────────────────────────────────────────────
# System integration
# ──────────────────────────────────────────────────────────────────────────


class Clipboard(_Service):
    """The system clipboard."""

    def copy(self, text: str, *, label: str = "pydrud") -> Result:
        return self._invoke("clipboard_set", text=str(text), label=label)

    def paste(self) -> Result:
        return self._invoke("clipboard_get")


class Share(_Service):
    """The Android share sheet and outbound intents."""

    def text(self, text: str, *, subject: str = "", title: str = "Share") -> Result:
        return self._invoke("share", kind="text", text=str(text),
                            subject=subject, title=title)

    def file(self, path: str, *, mime: str = "*/*", title: str = "Share") -> Result:
        return self._invoke("share", kind="file", path=str(path), mime=mime,
                            title=title)

    def open_url(self, url: str) -> Result:
        """Open a URL in the browser (or the app that claims it)."""
        return self._invoke("open_url", url=str(url))

    def email(self, to: str, *, subject: str = "", body: str = "") -> Result:
        return self._invoke("open_url",
                            url=f"mailto:{to}?subject={subject}&body={body}")

    def dial(self, number: str) -> Result:
        return self._invoke("open_url", url=f"tel:{number}")

    def sms(self, number: str, *, body: str = "") -> Result:
        return self._invoke("open_url", url=f"smsto:{number}?body={body}")

    def maps(self, query: str) -> Result:
        return self._invoke("open_url", url=f"geo:0,0?q={query}")


class Permissions(_Service):
    """Runtime permissions (Android 6+)."""

    #: Short names mapped to the full Android permission strings.
    ALIASES = {
        "camera": "android.permission.CAMERA",
        "microphone": "android.permission.RECORD_AUDIO",
        "location": "android.permission.ACCESS_FINE_LOCATION",
        "coarse_location": "android.permission.ACCESS_COARSE_LOCATION",
        "contacts": "android.permission.READ_CONTACTS",
        "storage": "android.permission.READ_EXTERNAL_STORAGE",
        "photos": "android.permission.READ_MEDIA_IMAGES",
        "notifications": "android.permission.POST_NOTIFICATIONS",
        "calendar": "android.permission.READ_CALENDAR",
        "bluetooth": "android.permission.BLUETOOTH_CONNECT",
        "phone": "android.permission.CALL_PHONE",
        "sms": "android.permission.SEND_SMS",
    }

    def resolve(self, name: str) -> str:
        """Map a short name to the full permission string."""
        key = str(name).lower()
        if key in self.ALIASES:
            return self.ALIASES[key]
        if "." in name:
            return name
        raise ValueError(
            f"Unknown permission {name!r}; use one of "
            f"{sorted(self.ALIASES)} or a full android.permission.* string")

    def check(self, name: str) -> Result:
        """Resolves with True when already granted."""
        return self._invoke("permission_check", permission=self.resolve(name))

    def request(self, *names: str) -> Result:
        """Ask the user. Resolves with ``{permission: granted}``."""
        if not names:
            raise ValueError("request() needs at least one permission")
        return self._invoke("permission_request",
                            permissions=[self.resolve(n) for n in names])

    def open_settings(self) -> Result:
        """Open this app's settings page (after a permanent denial)."""
        return self._invoke("open_app_settings")


class Notifications(_Service):
    """System notifications."""

    def show(self, title: str, body: str = "", *, id: int = 1,
             channel: str = "default", icon: Optional[str] = None,
             ongoing: bool = False, route: Optional[str] = None) -> Result:
        """Post a notification; tapping it can deep-link to *route*."""
        return self._invoke("notify", id=int(id), title=str(title),
                            body=str(body), channel=channel, icon=icon,
                            ongoing=bool(ongoing), route=route)

    def cancel(self, id: int = 1) -> Result:
        return self._invoke("notify_cancel", id=int(id))

    def cancel_all(self) -> Result:
        return self._invoke("notify_cancel", all=True)

    def create_channel(self, id: str, name: str, *,
                       importance: str = "default") -> Result:
        if importance not in ("min", "low", "default", "high"):
            raise ValueError("importance must be min/low/default/high")
        return self._invoke("notify_channel", id=id, name=name,
                            importance=importance)


class Location(_Service):
    """GPS / fused location."""

    def current(self, *, high_accuracy: bool = True,
                timeout: int = 10) -> Result:
        """Resolves with ``{"lat", "lon", "accuracy", "time"}``."""
        return self._invoke("location_get", highAccuracy=high_accuracy,
                            timeout=int(timeout))

    def watch(self, *, interval: int = 5000, min_distance: float = 10) -> Result:
        """Start location updates delivered as ``location`` events."""
        return self._invoke("location_watch", start=True,
                            interval=int(interval),
                            minDistance=float(min_distance))

    def stop(self) -> Result:
        return self._invoke("location_watch", start=False)


class DeviceInfo(_Service):
    """Static facts about the device and the app."""

    def info(self) -> Result:
        """Model, manufacturer, SDK level, app version, locale, dark mode…"""
        return self._invoke("device_info")

    def battery(self) -> Result:
        return self._invoke("battery_info")

    def network(self) -> Result:
        """Resolves with ``{"online", "type": "wifi|cellular|none"}``."""
        return self._invoke("network_info")


class Haptics(_Service):
    """Vibration and haptic feedback patterns."""

    PATTERNS = {"light": 10, "medium": 25, "heavy": 50,
                "success": 30, "warning": 60, "error": 90}

    def impact(self, style: str = "light") -> Result:
        if style not in self.PATTERNS:
            raise ValueError(f"style must be one of {sorted(self.PATTERNS)}")
        return self._invoke("vibrate", duration=self.PATTERNS[style],
                            style=style)

    def vibrate(self, duration_ms: int = 40) -> Result:
        return self._invoke("vibrate", duration=int(duration_ms))

    def pattern(self, timings: Sequence[int], *, repeat: int = -1) -> Result:
        return self._invoke("vibrate", pattern=[int(t) for t in timings],
                            repeat=int(repeat))


# ──────────────────────────────────────────────────────────────────────────
# Aggregate
# ──────────────────────────────────────────────────────────────────────────


class Services:
    """All native services, lazily constructed and cached."""

    def __init__(self, invoke: Invoke):
        self._invoke = invoke
        self.dialog = Dialogs(invoke)
        self.storage = Storage(invoke)
        self.clipboard = Clipboard(invoke)
        self.share = Share(invoke)
        self.permissions = Permissions(invoke)
        self.notifications = Notifications(invoke)
        self.location = Location(invoke)
        self.device = DeviceInfo(invoke)
        self.files = FilePicker(invoke)
        self.haptics = Haptics(invoke)

    def __repr__(self) -> str:
        return "<Services dialog storage clipboard share permissions " \
               "notifications location device files haptics>"
