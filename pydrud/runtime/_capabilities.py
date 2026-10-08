"""Graceful degradation for optional renderer capabilities.

Capabilities arrive in the existing ``ready`` event or preview handshake.
This module interprets the optional data without assuming a particular
transport or platform.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from pydrud.widgets import Widget
from pydrud.widgets.basic import Text

logger = logging.getLogger("pydrud.capabilities")

_SERVICE_COMMANDS: dict[str, str] = {
    "dialog": "dialog",
    "bottom_sheet": "dialog",
    "date_picker": "dialog",
    "time_picker": "dialog",
    "color_picker": "dialog",
    "progress_dialog": "dialog",
    "app_dir": "storage",
    "prefs_clear": "storage",
    "prefs_get": "storage",
    "prefs_keys": "storage",
    "prefs_remove": "storage",
    "prefs_set": "storage",
    "read_file": "files",
    "save_file": "files",
    "pick_file": "files",
    "pick_image": "files",
    "clipboard_get": "clipboard",
    "clipboard_set": "clipboard",
    "share": "share",
    "open_url": "share",
    "open_app_settings": "permissions",
    "permission_check": "permissions",
    "permission_request": "permissions",
    "permission_status": "permissions",
    "notify": "notifications",
    "notify_cancel": "notifications",
    "notify_channel": "notifications",
    "location_get": "location",
    "location_watch": "location",
    "device_info": "device",
    "battery_info": "device",
    "network_info": "device",
    "vibrate": "haptics",
    "secure_available": "secure",
    "secure_clear": "secure",
    "secure_get": "secure",
    "secure_keys": "secure",
    "secure_remove": "secure",
    "secure_set": "secure",
    "battery_exemption": "background",
    "service_start": "background",
    "service_stop": "background",
    "service_update": "background",
    "work_cancel": "background",
    "work_schedule": "background",
    "work_status": "background",
    "push_delete_token": "push",
    "push_subscribe": "push",
    "push_token": "push",
    "push_unsubscribe": "push",
    "appwidget_update": "shortcuts",
    "shortcut_pin": "shortcuts",
    "shortcuts_set": "shortcuts",
    "camera_capture": "camera",
    "camera_flash": "camera",
    "camera_record": "camera",
    "camera_record_stop": "camera",
    "camera_scan": "camera",
    "camera_start": "camera",
    "camera_stop": "camera",
    "camera_switch": "camera",
    "camera_zoom": "camera",
    "sensor_read": "sensors",
    "sensor_start": "sensors",
    "sensor_stop": "sensors",
    "sensors_available": "sensors",
    "bt_bonded": "bluetooth",
    "bt_connect": "bluetooth",
    "bt_disconnect": "bluetooth",
    "bt_enable": "bluetooth",
    "bt_enabled": "bluetooth",
    "bt_notify": "bluetooth",
    "bt_read": "bluetooth",
    "bt_scan": "bluetooth",
    "bt_scan_stop": "bluetooth",
    "bt_services": "bluetooth",
    "bt_write": "bluetooth",
    "nfc_available": "nfc",
    "nfc_cancel": "nfc",
    "nfc_read": "nfc",
    "nfc_write": "nfc",
    "biometric_auth": "biometrics",
    "biometric_available": "biometrics",
    "biometric_enroll": "biometrics",
    "audio_pause": "audio",
    "audio_play": "audio",
    "audio_record": "audio",
    "audio_record_stop": "audio",
    "audio_resume": "audio",
    "audio_seek": "audio",
    "audio_stop": "audio",
    "audio_volume": "audio",
    "speech_listen": "audio",
    "tts_speak": "audio",
    "system_colors": "system_theme",
}

_WARNED_WIDGET_TYPES: set[str] = set()
_WARN_LOCK = threading.Lock()


def service_for_command(command: str) -> str | None:
    """Return the optional service required by a request/response command."""
    return _SERVICE_COMMANDS.get(str(command))


def _listed(values: Any, name: str) -> bool:
    """Check an advertised optional capability represented as a list/map."""
    if isinstance(values, dict):
        return values.get(name) is True
    if isinstance(values, (list, tuple, set, frozenset)):
        return name in values
    return False


def capability_available(
    capabilities: dict[str, Any] | None,
    feature: str,
    *,
    command: str | None = None,
) -> bool:
    """Whether the connected client explicitly advertises *feature*.

    A direct command declaration is also accepted for clients which expose
    only their concrete command set. Missing optional fields mean unavailable.
    """
    if capabilities is None:
        return False
    if command and _listed(capabilities.get("commands"), command):
        return True
    # An explicit Boolean (including false) is authoritative, and NativeView
    # is deliberately never inferred from a widget catalogue alone.
    if isinstance(capabilities.get(feature), bool):
        return capabilities[feature]
    if _listed(capabilities.get("services"), feature):
        return True
    return False


def capability_failure(
    capabilities: dict[str, Any] | None,
    command: str,
) -> str | None:
    """Return an actionable failure reason for an unavailable command."""
    service = service_for_command(command)
    if service is not None:
        if capability_available(capabilities, service, command=command):
            return None
        return (
            f"capability '{service}' is unavailable on this client; "
            f"'{command}' was not sent. Connect a client that advertises "
            f"the '{service}' service, or provide a non-native fallback."
        )

    if capabilities is None:
        return None
    if _listed(capabilities.get("commands"), command):
        return None
    return (
        f"capability for command '{command}' is not advertised by this client; "
        "the request was not sent. Add it to the client's optional "
        "'commands' capability or use a supported API."
    )


def _advertised_widget_types(capabilities: dict[str, Any] | None) -> Any:
    if capabilities is None:
        return None
    return capabilities.get("widget_types")


def widget_supported(
    capabilities: dict[str, Any] | None,
    widget_type: str,
) -> bool:
    """Whether a renderer can accept a widget type.

    ``Text`` is the protocol's visible fallback primitive. If a client does
    not send a widget catalogue, preserve legacy behavior; an explicit list
    is the opt-in signal for validation of the rest of the vocabulary.
    """
    if widget_type == "Text" or capabilities is None:
        return True
    if widget_type == "NativeView" and not capability_available(
            capabilities, "native_view"):
        return False
    declared = _advertised_widget_types(capabilities)
    if declared is None:
        return True
    return _listed(declared, widget_type)


def replace_unsupported_widgets(
    root: Widget,
    capabilities: dict[str, Any] | None,
) -> Widget:
    """Replace unsupported nodes with visible, non-interactive ``Text`` nodes.

    The tree is a fresh build, so replacing its children is safe. Stable keys
    are retained, keeping render reconciliation deterministic. A warning is
    emitted once per unsupported widget type for the host process.

    The comparison uses :meth:`Widget.render_type` — the type each node
    actually serialises to — not the Python ``_widget_type``. Composite
    widgets (``Scaffold``, ``AppBar``, ``Flex`` …) render as an internal
    layout node, and ``FloatingActionButton`` renders as a ``Container``;
    testing ``_widget_type`` would wrongly replace a supported composite with
    a placeholder.
    """
    if widget_supported(capabilities, root.render_type()):
        stack = [root]
        while stack:
            parent = stack.pop()
            children: list[Widget] = []
            for child in parent.children:
                rendered = child.render_type()
                if not widget_supported(capabilities, rendered):
                    children.append(_placeholder(child))
                    _warn_unsupported(rendered)
                else:
                    children.append(child)
                    stack.append(child)
            parent.children = children
        return root

    placeholder = _placeholder(root)
    _warn_unsupported(root.render_type())
    return placeholder


def _placeholder(widget: Widget) -> Text:
    fallback = Text(
        f"Unsupported widget: {widget._widget_type}",
        key=widget.key,
        expand=widget.expand,
        class_=list(getattr(widget, "class_", ()) or ()),
    )
    fallback._auto_key = getattr(widget, "_auto_key", True)
    return fallback


def _warn_unsupported(widget_type: str) -> None:
    with _WARN_LOCK:
        if widget_type in _WARNED_WIDGET_TYPES:
            return
        _WARNED_WIDGET_TYPES.add(widget_type)
    logger.warning(
        "Connected renderer does not advertise widget type %s; rendering a "
        "visible Text placeholder. Add the type to the client's "
        "'widget_types' capability or use a supported widget.",
        widget_type,
    )


__all__ = [
    "capability_available", "capability_failure", "replace_unsupported_widgets",
    "service_for_command", "widget_supported",
]
