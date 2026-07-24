"""
Bridge protocol — defines how the Python ↔ Android communication works.

The protocol uses JSON messages over a lightweight socket or stdin/stdout
channels.  Messages are newline-delimited JSON (NDJSON).

Message types:

  *Android → Python (events)*
    {"type": "click",     "key": "...", "data": {}}
    {"type": "change",    "key": "...", "data": {"value": "..."}}
    {"type": "submit",    "key": "...", "data": {"value": "..."}}
    {"type": "focus",     "key": "...", "data": {"focused": true}}
    {"type": "ready",     "key": "",    "data": {}}
    {"type": "lifecycle", "key": "",    "data": {"state": "pause|resume|stop|destroy"}}

  *Python → Android (render commands)*
    {"cmd": "render",      "patches": [...]}
    {"cmd": "full_render", "tree": {...}}
    {"cmd": "toast",       "message": "..."}
    {"cmd": "navigate",    "route": "/page2"}
    {"cmd": "set_title",   "title": "My App"}
    {"cmd": "back"}
    {"cmd": "eval_js",     "code": "..."}   (future)

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
