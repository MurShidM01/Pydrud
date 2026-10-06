"""
Camera, sensors, Bluetooth, NFC, biometrics and audio I/O.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Sequence

from pydrud.core.results import Result
from pydrud.services.native._base import Invoke, _Service



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
        """Set the camera flash mode (``auto``/``on``/``off``/``torch``).
        """
        if mode not in ("on", "off", "auto", "torch"):
            raise ValueError("mode must be on/off/auto/torch")
        return self._invoke("camera_flash", key=key, mode=mode)

    def zoom(self, ratio: float, *, key: str = "") -> Result:
        """Set the camera zoom ratio (``1.0`` is wide).
        """
        return self._invoke("camera_zoom", key=key, ratio=float(ratio))

    def record(self, *, key: str = "", path: str = "",
               max_seconds: int = 0) -> Result:
        """Start recording video from the preview at ``key``.
        """
        return self._invoke("camera_record", key=key, path=path,
                            max_seconds=int(max_seconds))

    def stop_recording(self, *, key: str = "") -> Result:
        """Stop video recording; resolves with the file path.
        """
        return self._invoke("camera_record_stop", key=key)

    def scan_codes(self, *, key: str = "", enabled: bool = True) -> Result:
        """Turn on barcode/QR scanning — matches arrive as ``scan`` events.
        """
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
        """Whether the Bluetooth adapter is currently on.
        """
        return self._invoke("bt_enabled")

    def enable(self) -> Result:
        """Ask the user to turn Bluetooth on.
        """
        return self._invoke("bt_enable")

    def scan(self, *, seconds: float = 8.0,
             services: Optional[Sequence[str]] = None) -> Result:
        """Scan for peripherals. Resolves with a list of devices.
        """
        return self._invoke("bt_scan", seconds=float(seconds),
                            services=[str(s) for s in (services or [])])

    def stop_scan(self) -> Result:
        """Stop a scan started by :meth:`scan`.
        """
        return self._invoke("bt_scan_stop")

    def connect(self, address: str) -> Result:
        """Connect to a peripheral by MAC address.
        """
        return self._invoke("bt_connect", address=str(address))

    def disconnect(self, address: str) -> Result:
        """Drop the connection to a peripheral.
        """
        return self._invoke("bt_disconnect", address=str(address))

    def services(self, address: str) -> Result:
        """List the GATT services a connected peripheral exposes.
        """
        return self._invoke("bt_services", address=str(address))

    def read(self, address: str, service: str, characteristic: str) -> Result:
        """Read a GATT characteristic.
        """
        return self._invoke("bt_read", address=str(address),
                            service=str(service),
                            characteristic=str(characteristic))

    def write(self, address: str, service: str, characteristic: str,
              value: Any, *, response: bool = True) -> Result:
        """Write bytes to a GATT characteristic.
        """
        if isinstance(value, (bytes, bytearray)):
            value = list(value)
        return self._invoke("bt_write", address=str(address),
                            service=str(service),
                            characteristic=str(characteristic),
                            value=value, response=bool(response))

    def notify(self, address: str, service: str, characteristic: str, *,
               enabled: bool = True) -> Result:
        """Subscribe to notifications — they arrive as ``bluetooth`` events.
        """
        return self._invoke("bt_notify", address=str(address),
                            service=str(service),
                            characteristic=str(characteristic),
                            enabled=bool(enabled))

    def bonded(self) -> Result:
        """Already-paired devices.
        """
        return self._invoke("bt_bonded")


class Nfc(_Service):
    """NFC tag reading and NDEF writing."""

    def available(self) -> Result:
        """Whether this device has NFC hardware, enabled.
        """
        return self._invoke("nfc_available")

    def read(self, *, timeout: float = 30.0) -> Result:
        """Wait for a tag. Resolves with ``{"id", "techs", "records"}``.
        """
        return self._invoke("nfc_read", timeout=float(timeout))

    def write(self, records: Sequence[dict], *,
              timeout: float = 30.0) -> Result:
        """Write NDEF records, e.g. ``[{"type": "text", "value": "hi"}]``.
        """
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
        """Cancel a pending NFC read/write.
        """
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
        """Speech-to-text. Resolves with the recognised string.
        """
        return self._invoke("speech_listen", locale=locale, prompt=prompt)
