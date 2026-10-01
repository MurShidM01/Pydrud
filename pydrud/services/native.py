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


# ──────────────────────────────────────────────────────────────────────────
# Secure storage (Keystore-backed)
# ──────────────────────────────────────────────────────────────────────────


class Secure(_Service):
    """Encrypted key/value storage backed by the Android Keystore.

    Values are written through ``EncryptedSharedPreferences`` (AES-256-GCM
    with a hardware-backed master key when the device has a TEE), so tokens
    and credentials never sit in plaintext on disk::

        page.secure.set("token", jwt)
        page.secure.get("token").then(use_token)
        page.secure.delete("token")
    """

    def set(self, key: str, value: str) -> Result:
        return self._invoke("secure_set", key=str(key), value=str(value))

    def get(self, key: str, default: Any = None) -> Result:
        return self._invoke("secure_get", key=str(key), default=default)

    def delete(self, key: str) -> Result:
        return self._invoke("secure_remove", key=str(key))

    def keys(self) -> Result:
        return self._invoke("secure_keys")

    def clear(self) -> Result:
        return self._invoke("secure_clear")

    def available(self) -> Result:
        """Whether hardware-backed encryption is available on this device."""
        return self._invoke("secure_available")


# ──────────────────────────────────────────────────────────────────────────
# Background execution
# ──────────────────────────────────────────────────────────────────────────


class Background(_Service):
    """WorkManager jobs and foreground services.

    A *job* is a Python callable that WorkManager re-invokes later — even
    after the app is killed or the device reboots::

        page.background.schedule("sync", every=900, network=True)

        @page.background.job("sync")
        def sync_now(inputs):
            Note.where(dirty=True).update(dirty=False)

    A *foreground service* keeps Python alive with a sticky notification
    (music playback, long downloads, location tracking).
    """

    NETWORKS = ("any", "connected", "unmetered", "not_roaming")

    def __init__(self, invoke: Invoke):
        super().__init__(invoke)
        self._jobs: dict[str, Callable] = {}

    # ── jobs ─────────────────────────────────────────────────────────────

    def job(self, name: str) -> Callable:
        """Decorator registering the Python callable WorkManager will run."""
        def decorator(fn: Callable) -> Callable:
            if not callable(fn):
                raise TypeError("background job must be callable")
            self._jobs[str(name)] = fn
            return fn
        return decorator

    def register(self, name: str, fn: Callable) -> "Background":
        self.job(name)(fn)
        return self

    def run_job(self, name: str, inputs: Optional[dict] = None) -> Any:
        """Invoke a registered job locally (used by the worker and in tests)."""
        fn = self._jobs.get(str(name))
        if fn is None:
            raise KeyError(f"No background job named {name!r}")
        try:
            return fn(dict(inputs or {}))
        except TypeError:
            return fn()

    @property
    def jobs(self) -> list[str]:
        return sorted(self._jobs)

    # ── scheduling ───────────────────────────────────────────────────────

    def schedule(self, name: str, *, every: Optional[float] = None,
                 delay: float = 0, network: Any = False,
                 charging: bool = False, idle: bool = False,
                 battery_not_low: bool = False, replace: bool = True,
                 inputs: Optional[dict] = None) -> Result:
        """Queue a job. With *every* it repeats (minimum 15 minutes)."""
        if every is not None and float(every) < 900:
            raise ValueError(
                "WorkManager's minimum periodic interval is 900 seconds")
        if isinstance(network, bool):
            network = "connected" if network else "any"
        if network not in self.NETWORKS:
            raise ValueError(f"network must be one of {self.NETWORKS}")
        return self._invoke("work_schedule", name=str(name),
                            every=None if every is None else float(every),
                            delay=float(delay), network=network,
                            charging=bool(charging), idle=bool(idle),
                            battery_not_low=bool(battery_not_low),
                            replace=bool(replace), inputs=dict(inputs or {}))

    def cancel(self, name: str) -> Result:
        return self._invoke("work_cancel", name=str(name))

    def cancel_all(self) -> Result:
        return self._invoke("work_cancel", name=None, all=True)

    def status(self, name: str) -> Result:
        """Resolves with ``enqueued`` / ``running`` / ``succeeded`` / …"""
        return self._invoke("work_status", name=str(name))

    # ── foreground service ───────────────────────────────────────────────

    def start_service(self, *, title: str = "Running",
                      message: str = "", icon: str = "",
                      ongoing: bool = True,
                      actions: Optional[Sequence[str]] = None) -> Result:
        """Promote the app to a foreground service with a sticky notification."""
        return self._invoke("service_start", title=title, message=message,
                            icon=icon, ongoing=bool(ongoing),
                            actions=[str(a) for a in (actions or [])])

    def update_service(self, *, title: str = "", message: str = "",
                       progress: Optional[int] = None) -> Result:
        return self._invoke("service_update", title=title, message=message,
                            progress=progress)

    def stop_service(self) -> Result:
        return self._invoke("service_stop")

    def request_battery_exemption(self) -> Result:
        """Ask the user to exempt the app from Doze (use sparingly)."""
        return self._invoke("battery_exemption")


class Push(_Service):
    """Firebase Cloud Messaging.

    ``pydrud build`` wires FCM in automatically when a
    ``google-services.json`` is present in the project root.
    """

    def token(self) -> Result:
        """The device's current registration token."""
        return self._invoke("push_token")

    def subscribe(self, topic: str) -> Result:
        return self._invoke("push_subscribe", topic=str(topic))

    def unsubscribe(self, topic: str) -> Result:
        return self._invoke("push_unsubscribe", topic=str(topic))

    def delete_token(self) -> Result:
        return self._invoke("push_delete_token")

    def permission(self) -> Result:
        """Request the Android 13+ POST_NOTIFICATIONS permission."""
        return self._invoke("permission_request", names=["notifications"])


class Shortcuts(_Service):
    """Launcher shortcuts and home-screen app widgets."""

    def set(self, shortcuts: Sequence[dict]) -> Result:
        """Replace the dynamic shortcuts.

        Each item is ``{"id", "label", "icon", "route"}`` — tapping one
        launches the app and fires a ``deep_link`` event for *route*.
        """
        items = []
        for item in shortcuts:
            if "id" not in item or "label" not in item:
                raise ValueError("each shortcut needs an 'id' and a 'label'")
            items.append({"id": str(item["id"]), "label": str(item["label"]),
                          "icon": str(item.get("icon", "")),
                          "route": str(item.get("route", "/"))})
        if len(items) > 4:
            raise ValueError("Android allows at most 4 dynamic shortcuts")
        return self._invoke("shortcuts_set", shortcuts=items)

    def clear(self) -> Result:
        return self._invoke("shortcuts_set", shortcuts=[])

    def pin(self, id: str, label: str, *, icon: str = "",
            route: str = "/") -> Result:
        """Ask the launcher to pin a shortcut to the home screen."""
        return self._invoke("shortcut_pin", id=str(id), label=str(label),
                            icon=icon, route=route)

    def update_widget(self, values: dict, *, widget: str = "default") -> Result:
        """Push new text/values into the app's home-screen widget."""
        return self._invoke("appwidget_update", widget=str(widget),
                            values=dict(values))


# ──────────────────────────────────────────────────────────────────────────
# Hardware
# ──────────────────────────────────────────────────────────────────────────


class Camera(_Service):
    """Controls the :class:`~pydrud.widgets.advanced.CameraPreview` widget."""

    def start(self, *, key: str = "", facing: str = "back") -> Result:
        if facing not in ("back", "front"):
            raise ValueError("facing must be 'back' or 'front'")
        return self._invoke("camera_start", key=key, facing=facing)

    def stop(self, *, key: str = "") -> Result:
        return self._invoke("camera_stop", key=key)

    def capture(self, *, key: str = "", path: str = "",
                quality: int = 90) -> Result:
        """Take a still photo. Resolves with the saved file path."""
        if not 1 <= int(quality) <= 100:
            raise ValueError("quality must be between 1 and 100")
        return self._invoke("camera_capture", key=key, path=path,
                            quality=int(quality))

    def switch(self, *, key: str = "") -> Result:
        return self._invoke("camera_switch", key=key)

    def flash(self, mode: str = "auto", *, key: str = "") -> Result:
        if mode not in ("on", "off", "auto", "torch"):
            raise ValueError("mode must be on/off/auto/torch")
        return self._invoke("camera_flash", key=key, mode=mode)

    def zoom(self, ratio: float, *, key: str = "") -> Result:
        return self._invoke("camera_zoom", key=key, ratio=float(ratio))

    def record(self, *, key: str = "", path: str = "",
               max_seconds: int = 0) -> Result:
        return self._invoke("camera_record", key=key, path=path,
                            max_seconds=int(max_seconds))

    def stop_recording(self, *, key: str = "") -> Result:
        return self._invoke("camera_record_stop", key=key)

    def scan_codes(self, *, key: str = "", enabled: bool = True) -> Result:
        """Turn on barcode/QR scanning — matches arrive as ``scan`` events."""
        return self._invoke("camera_scan", key=key, enabled=bool(enabled))


class Sensors(_Service):
    """Motion and environment sensors.

    ``page.sensors.listen("accelerometer", cb)`` streams readings as
    ``sensor`` events; the callback receives ``{"sensor", "x", "y", "z"}``.
    """

    KINDS = ("accelerometer", "gyroscope", "magnetometer", "gravity",
             "linear_acceleration", "rotation", "step_counter", "light",
             "proximity", "pressure", "humidity", "temperature")
    RATES = ("fastest", "game", "ui", "normal")

    def __init__(self, invoke: Invoke):
        super().__init__(invoke)
        self._listeners: dict[str, list[Callable]] = {}

    def available(self) -> Result:
        """Resolves with the list of sensors this device actually has."""
        return self._invoke("sensors_available")

    def listen(self, kind: str, callback: Callable, *,
               rate: str = "ui") -> Result:
        self._check(kind)
        if rate not in self.RATES:
            raise ValueError(f"rate must be one of {self.RATES}")
        if not callable(callback):
            raise TypeError("sensor callback must be callable")
        self._listeners.setdefault(kind, []).append(callback)
        return self._invoke("sensor_start", sensor=kind, rate=rate)

    def stop(self, kind: str) -> Result:
        self._check(kind)
        self._listeners.pop(kind, None)
        return self._invoke("sensor_stop", sensor=kind)

    def read(self, kind: str) -> Result:
        """One-shot reading."""
        self._check(kind)
        return self._invoke("sensor_read", sensor=kind)

    def shake(self, callback: Callable, *, threshold: float = 12.0) -> Result:
        """Convenience detector built on the accelerometer."""
        self._listeners.setdefault("shake", []).append(callback)
        return self._invoke("sensor_start", sensor="shake",
                            threshold=float(threshold))

    def dispatch(self, data: dict) -> None:
        """Called by the app when a ``sensor`` event arrives."""
        for callback in list(self._listeners.get(data.get("sensor", ""), [])):
            callback(data)

    def _check(self, kind: str) -> None:
        if kind not in self.KINDS and kind != "shake":
            raise ValueError(f"Unknown sensor {kind!r}. "
                             f"Available: {', '.join(self.KINDS)}")


class Bluetooth(_Service):
    """Bluetooth Low Energy: scan, connect, read/write/notify."""

    def enabled(self) -> Result:
        return self._invoke("bt_enabled")

    def enable(self) -> Result:
        """Ask the user to turn Bluetooth on."""
        return self._invoke("bt_enable")

    def scan(self, *, seconds: float = 8.0,
             services: Optional[Sequence[str]] = None) -> Result:
        """Scan for peripherals. Resolves with a list of devices."""
        return self._invoke("bt_scan", seconds=float(seconds),
                            services=[str(s) for s in (services or [])])

    def stop_scan(self) -> Result:
        return self._invoke("bt_scan_stop")

    def connect(self, address: str) -> Result:
        return self._invoke("bt_connect", address=str(address))

    def disconnect(self, address: str) -> Result:
        return self._invoke("bt_disconnect", address=str(address))

    def services(self, address: str) -> Result:
        return self._invoke("bt_services", address=str(address))

    def read(self, address: str, service: str, characteristic: str) -> Result:
        return self._invoke("bt_read", address=str(address),
                            service=str(service),
                            characteristic=str(characteristic))

    def write(self, address: str, service: str, characteristic: str,
              value: Any, *, response: bool = True) -> Result:
        if isinstance(value, (bytes, bytearray)):
            value = list(value)
        return self._invoke("bt_write", address=str(address),
                            service=str(service),
                            characteristic=str(characteristic),
                            value=value, response=bool(response))

    def notify(self, address: str, service: str, characteristic: str, *,
               enabled: bool = True) -> Result:
        """Subscribe to notifications — they arrive as ``bluetooth`` events."""
        return self._invoke("bt_notify", address=str(address),
                            service=str(service),
                            characteristic=str(characteristic),
                            enabled=bool(enabled))

    def bonded(self) -> Result:
        """Already-paired devices."""
        return self._invoke("bt_bonded")


class Nfc(_Service):
    """NFC tag reading and NDEF writing."""

    def available(self) -> Result:
        return self._invoke("nfc_available")

    def read(self, *, timeout: float = 30.0) -> Result:
        """Wait for a tag. Resolves with ``{"id", "techs", "records"}``."""
        return self._invoke("nfc_read", timeout=float(timeout))

    def write(self, records: Sequence[dict], *,
              timeout: float = 30.0) -> Result:
        """Write NDEF records, e.g. ``[{"type": "text", "value": "hi"}]``."""
        items = []
        for record in records:
            kind = str(record.get("type", "text"))
            if kind not in ("text", "uri", "mime"):
                raise ValueError("record type must be text, uri or mime")
            items.append({"type": kind, "value": str(record.get("value", "")),
                          "mime": str(record.get("mime", ""))})
        if not items:
            raise ValueError("write() needs at least one record")
        return self._invoke("nfc_write", records=items, timeout=float(timeout))

    def cancel(self) -> Result:
        return self._invoke("nfc_cancel")


class Biometrics(_Service):
    """Fingerprint / face unlock via ``BiometricPrompt``."""

    def available(self) -> Result:
        """Resolves with ``{"available", "kind", "enrolled"}``."""
        return self._invoke("biometric_available")

    def authenticate(self, *, title: str = "Verify it's you",
                     subtitle: str = "", description: str = "",
                     cancel: str = "Cancel",
                     allow_device_credential: bool = True) -> Result:
        """Prompt the user. Resolves ``True`` on success, ``False`` if denied."""
        return self._invoke("biometric_auth", title=title, subtitle=subtitle,
                            description=description, cancel=cancel,
                            allow_credential=bool(allow_device_credential))

    def enroll(self) -> Result:
        """Open the system screen for enrolling a fingerprint/face."""
        return self._invoke("biometric_enroll")


class Audio(_Service):
    """Recording and playback."""

    FORMATS = ("m4a", "aac", "wav", "3gp")

    def record(self, *, path: str = "", format: str = "m4a",
               max_seconds: int = 0, sample_rate: int = 44100) -> Result:
        if format not in self.FORMATS:
            raise ValueError(f"format must be one of {self.FORMATS}")
        return self._invoke("audio_record", path=path, format=format,
                            max_seconds=int(max_seconds),
                            sample_rate=int(sample_rate))

    def stop_recording(self) -> Result:
        """Resolves with ``{"path", "seconds", "size"}``."""
        return self._invoke("audio_record_stop")

    def play(self, source: str, *, loop: bool = False,
             volume: float = 1.0) -> Result:
        if not 0.0 <= float(volume) <= 1.0:
            raise ValueError("volume must be between 0 and 1")
        return self._invoke("audio_play", source=str(source),
                            loop=bool(loop), volume=float(volume))

    def pause(self) -> Result:
        return self._invoke("audio_pause")

    def resume(self) -> Result:
        return self._invoke("audio_resume")

    def stop(self) -> Result:
        return self._invoke("audio_stop")

    def seek(self, seconds: float) -> Result:
        return self._invoke("audio_seek", seconds=float(seconds))

    def volume(self, level: float) -> Result:
        return self._invoke("audio_volume", level=float(level))

    def speak(self, text: str, *, locale: str = "", rate: float = 1.0,
              pitch: float = 1.0) -> Result:
        """Text-to-speech."""
        return self._invoke("tts_speak", text=str(text), locale=locale,
                            rate=float(rate), pitch=float(pitch))

    def listen(self, *, locale: str = "", prompt: str = "") -> Result:
        """Speech-to-text. Resolves with the recognised string."""
        return self._invoke("speech_listen", locale=locale, prompt=prompt)


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
        self.secure = Secure(invoke)
        self.background = Background(invoke)
        self.push = Push(invoke)
        self.shortcuts = Shortcuts(invoke)
        self.camera = Camera(invoke)
        self.sensors = Sensors(invoke)
        self.bluetooth = Bluetooth(invoke)
        self.nfc = Nfc(invoke)
        self.biometrics = Biometrics(invoke)
        self.audio = Audio(invoke)

    def __repr__(self) -> str:
        return "<Services dialog storage clipboard share permissions " \
               "notifications location device files haptics secure " \
               "background push shortcuts camera sensors bluetooth nfc " \
               "biometrics audio>"
