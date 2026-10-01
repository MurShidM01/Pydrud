"""
Bridge protocol — defines how the Python ↔ Android communication works.

The protocol uses JSON messages over a lightweight socket or stdin/stdout
channels.  Messages are newline-delimited JSON (NDJSON).

Message types:

  *Android -> Python (events)*
    {"type": "click",     "key": "...", "data": {}}
    {"type": "long_press","key": "...", "data": {}}
    {"type": "change",    "key": "...", "data": {"value": "..."}}
    {"type": "submit",    "key": "...", "data": {"value": "..."}}
    {"type": "focus",     "key": "...", "data": {"focused": true}}
    {"type": "scroll",    "key": "...", "data": {"offset": 120}}
    {"type": "gesture",   "key": "...", "data": {"gesture": "swipe_left"}}
    {"type": "dismiss",   "key": "...", "data": {"direction": "end"}}
    {"type": "refresh",   "key": "...", "data": {}}
    {"type": "ready",     "key": "",    "data": {"width": 411, "height": 866}}
    {"type": "back",      "key": "",    "data": {}}
    {"type": "lifecycle", "key": "",    "data": {"state": "pause|resume|stop|destroy"}}
    {"type": "result",    "key": "",    "data": {"id": 7, "ok": true, "value": ...}}

  The ``result`` event is the reply to any command that carries a request
  ``id`` (every :class:`~pydrud.core.results.Result`-returning service call).
  ``ok: false`` carries ``"error"`` instead of ``"value"`` and rejects the
  pending Result.  Unknown ids are ignored.

  *Python -> Android (rendering)*
    {"cmd": "render",      "patches": [...]}
    {"cmd": "full_render", "tree": {...}}

  *Python -> Android (page / chrome; fire-and-forget)*
    {"cmd": "toast",         "message": "...", "duration": "short|long"}
    {"cmd": "snackbar",      "message": "...", "action": "UNDO"}
    {"cmd": "set_title",     "title": "My App"}
    {"cmd": "set_system_ui", "status_bar_color": "#FF...", "icon_brightness": "light"}
    {"cmd": "theme_mode",    "mode": "light|dark|system"}
    {"cmd": "navigate",      "route": "/page2"}
    {"cmd": "back"}
    {"cmd": "back_result",   "handled": true}
    {"cmd": "finish_activity"}
    {"cmd": "drawer",        "open": true, "side": "start|end"}
    {"cmd": "scroll_to",     "key": "row_42", "animate": true}
    {"cmd": "focus",         "key": "email"}
    {"cmd": "keyboard",      "show": false}
    {"cmd": "keep_awake",    "enabled": true}
    {"cmd": "orientation",   "mode": "portrait|landscape|auto"}
    {"cmd": "fullscreen",    "enabled": true}
    {"cmd": "end_refresh",   "key": "refresh"}
    {"cmd": "vibrate",       "duration": 30}

  *Python -> Android (native services; each replies with a ``result`` event)*
    dialogs      dialog, bottom_sheet, date_picker, time_picker,
                 color_picker, progress_dialog
    storage      prefs_set, prefs_get, prefs_remove, prefs_clear, prefs_keys
    clipboard    clipboard_set, clipboard_get
    sharing      share, open_url, open_app_settings
    permissions  permission_check, permission_request
    notifying    notify, notify_cancel, notify_channel
    location     location_get, location_watch
    device       device_info, battery_info, network_info
    files        pick_file, pick_image, save_file, read_file, app_dir
    haptics      vibrate

Commands without an ``id`` are fire-and-forget; commands with one must be
answered exactly once so the Python side can settle its Result.

This module is kept abstract so the transport layer (socket vs stdio vs JNI)
can be swapped without changing the app code.
"""

from __future__ import annotations
import json
from typing import Any, Callable, Optional

MessageHandler = Callable[[dict], Any]


class BridgeProtocol:
    """Encodes/decodes messages for the Python ↔ Android bridge."""

    @staticmethod
    def encode_command(cmd: str, **data) -> str:
        """Encode a command from Python to Android as JSON."""
        payload: dict = {"cmd": cmd}
        payload.update(data)
        return json.dumps(payload, default=str) + "\n"

    @staticmethod
    def decode_message(line: str) -> Optional[dict]:
        """Decode a JSON message from Android."""
        line = line.strip()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def encode_render(patches: list[dict]) -> str:
        """Encode a render-command with patches."""
        return BridgeProtocol.encode_command("render", patches=patches)

    @staticmethod
    def encode_full_render(tree: dict) -> str:
        """Encode a full (initial) render command."""
        return BridgeProtocol.encode_command("full_render", tree=tree)
