"""
Sharing, permissions, notifications, location, device info and haptics.
"""

from __future__ import annotations

from typing import Optional, Sequence

from pydrud.core.results import Result
from pydrud.services.native._base import _Service



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
        "mic": "android.permission.RECORD_AUDIO",
        "record_audio": "android.permission.RECORD_AUDIO",
        "audio": "android.permission.RECORD_AUDIO",
        "location": "android.permission.ACCESS_FINE_LOCATION",
        "fine_location": "android.permission.ACCESS_FINE_LOCATION",
        "coarse_location": "android.permission.ACCESS_COARSE_LOCATION",
        "background_location": "android.permission.ACCESS_BACKGROUND_LOCATION",
        "contacts": "android.permission.READ_CONTACTS",
        "contacts_write": "android.permission.WRITE_CONTACTS",
        "write_contacts": "android.permission.WRITE_CONTACTS",
        "storage": "android.permission.READ_EXTERNAL_STORAGE",
        "photos": "android.permission.READ_MEDIA_IMAGES",
        "images": "android.permission.READ_MEDIA_IMAGES",
        "media_images": "android.permission.READ_MEDIA_IMAGES",
        "videos": "android.permission.READ_MEDIA_VIDEO",
        "video": "android.permission.READ_MEDIA_VIDEO",
        "media_video": "android.permission.READ_MEDIA_VIDEO",
        "music": "android.permission.READ_MEDIA_AUDIO",
        "audio_files": "android.permission.READ_MEDIA_AUDIO",
        "media_audio": "android.permission.READ_MEDIA_AUDIO",
        "read_storage": "android.permission.READ_EXTERNAL_STORAGE",
        "write_storage": "android.permission.WRITE_EXTERNAL_STORAGE",
        "notifications": "android.permission.POST_NOTIFICATIONS",
        "notification": "android.permission.POST_NOTIFICATIONS",
        "post_notifications": "android.permission.POST_NOTIFICATIONS",
        "internet": "android.permission.INTERNET",
        "network": "android.permission.ACCESS_NETWORK_STATE",
        "calendar": "android.permission.READ_CALENDAR",
        "calendar_write": "android.permission.WRITE_CALENDAR",
        "write_calendar": "android.permission.WRITE_CALENDAR",
        "bluetooth": "android.permission.BLUETOOTH_CONNECT",
        "nearby_devices": "android.permission.BLUETOOTH_CONNECT",
        "bluetooth_connect": "android.permission.BLUETOOTH_CONNECT",
        "bluetooth_scan": "android.permission.BLUETOOTH_SCAN",
        "bluetooth_advertise": "android.permission.BLUETOOTH_ADVERTISE",
        "nfc": "android.permission.NFC",
        "biometric": "android.permission.USE_BIOMETRIC",
        "fingerprint": "android.permission.USE_BIOMETRIC",
        "vibrate": "android.permission.VIBRATE",
        "haptics": "android.permission.VIBRATE",
        "activity": "android.permission.ACTIVITY_RECOGNITION",
        "activity_recognition": "android.permission.ACTIVITY_RECOGNITION",
        "phone": "android.permission.CALL_PHONE",
        "phone_state": "android.permission.READ_PHONE_STATE",
        "read_phone_state": "android.permission.READ_PHONE_STATE",
        "sms": "android.permission.SEND_SMS",
        "send_sms": "android.permission.SEND_SMS",
        "receive_sms": "android.permission.RECEIVE_SMS",
        "wake_lock": "android.permission.WAKE_LOCK",
        "boot": "android.permission.RECEIVE_BOOT_COMPLETED",
        "boot_completed": "android.permission.RECEIVE_BOOT_COMPLETED",
        "foreground_service": "android.permission.FOREGROUND_SERVICE",
        "foreground_data_sync": "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
        "alarms": "android.permission.SCHEDULE_EXACT_ALARM",
        "exact_alarm": "android.permission.SCHEDULE_EXACT_ALARM",
    }

    def resolve(self, name: str) -> str:
        """Map a short name to the full permission string."""
        key = str(name).strip().lower().replace("-", "_")
        if key in self.ALIASES:
            return self.ALIASES[key]
        if "." in name:
            return name
        raise ValueError(
            f"Unknown permission {name!r}; use one of "
            f"{sorted(self.ALIASES)} or a full android.permission.* string")

    def check(self, name: str) -> Result:
        """Resolves with ``True`` when *name* is already granted.

        Prefer :meth:`status` when the distinction between an ordinary denial
        and a permanent denial matters.
        """
        return self._invoke("permission_check", permission=self.resolve(name))

    def is_granted(self, name: str, *, timeout: float = 2.0) -> bool:
        """Synchronous ``True``/``False`` — never opens a system prompt.

        The bridge answers permission checks from native side immediately,
        so blocking the calling thread here is safe (and this is what makes
        guards like ``if page.permissions.is_granted("camera"):`` feel
        natural). Inside async code prefer ``await page.permissions.check(name)``.
        """
        return bool(self.check(name).wait(timeout=timeout, default=False))

    def status(self, name: str) -> Result:
        """Query permission state without opening a system prompt.

        Resolves with one of ``"granted"``, ``"denied"`` or
        ``"permanently_denied"``. Android only exposes permanent denial after
        an earlier request, which Pydrud records for the app automatically.
        """
        return self._invoke("permission_status", permission=self.resolve(name))

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
        """Create a notification channel (Android 8+ grouping).
        """
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
        """Start location updates delivered as ``location`` events.
        """
        return self._invoke("location_watch", start=True,
                            interval=int(interval),
                            minDistance=float(min_distance))

    def stop(self) -> Result:
        """Stop location updates started by :meth:`watch`.
        """
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

    def selection(self) -> Result:
        """A crisp tick for selection changes (tabs, pickers, counters)."""
        return self._invoke("vibrate", duration=8, style="selection")

    def pattern(self, timings: Sequence[int], *, repeat: int = -1) -> Result:
        return self._invoke("vibrate", pattern=[int(t) for t in timings],
                            repeat=int(repeat))


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
        return self._invoke(
            "permission_request",
            permissions=[Permissions.ALIASES["notifications"]],
        )


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
