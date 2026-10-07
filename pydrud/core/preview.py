"""Stable wire contract for host-driven Pydrud UI preview clients.

The preview handshake is intentionally separate from the renderer protocol:
preview protocol v1 establishes and authenticates a development session, then
both peers exchange the existing Pydrud bridge envelopes (theme commands,
revisioned render transactions, ACK/NACK messages and UI events).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import math
import secrets
import urllib.parse
import uuid
from dataclasses import dataclass
from typing import Any

from pydrud.core.protocol import MAX_FRAME_BYTES, PROTOCOL_VERSION

PREVIEW_PROTOCOL = "pydrud.preview"
PREVIEW_PROTOCOL_VERSION = 1
DEFAULT_PREVIEW_PORT = 8597
DEFAULT_PREVIEW_HOST = "0.0.0.0"
PREVIEW_SCHEME = "pydrud"
PREVIEW_AUTHORITY = "preview"
PREVIEW_PATH = "/connect"

REQUIRED_RENDERER_CAPABILITIES = frozenset({
    "transactional_render",
    "revisioned_render",
    "ack_nack",
    "resync",
})

SERVER_CAPABILITIES = {
    "host_python": True,
    "file_watching": True,
    "stateful_hot_reload": True,
    "initial_snapshot": True,
    "incremental_patches": True,
    "reconnect_resync": True,
}


class PreviewProtocolError(ValueError):
    """A rejected or malformed preview handshake."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)


@dataclass(frozen=True, slots=True)
class PreviewSession:
    """Identity and short-lived bearer credential for one ``pydrud dev`` run."""

    project_id: str
    project_name: str
    session_id: str
    token: str

    @classmethod
    def create(cls, project_id: str, project_name: str) -> "PreviewSession":
        project_id = str(project_id).strip()
        project_name = str(project_name).strip()
        if not project_id:
            raise ValueError("project_id must not be empty")
        if not project_name:
            raise ValueError("project_name must not be empty")
        return cls(
            project_id=project_id[:200],
            project_name=project_name[:200],
            session_id=str(uuid.uuid4()),
            token=secrets.token_urlsafe(32),
        )

    @property
    def short_id(self) -> str:
        return self.session_id.split("-", 1)[0]

    def matches_token(self, candidate: object) -> bool:
        return hmac.compare_digest(self.token, str(candidate or ""))


def fallback_project_id(project_root: str) -> str:
    """Stable non-secret identity when a project has no configured package."""
    digest = hashlib.sha256(str(project_root).encode("utf-8")).hexdigest()[:16]
    return f"local.{digest}"


def build_preview_uri(session: PreviewSession, host: str, port: int) -> str:
    """Create the exact URI encoded in the terminal QR code."""
    host = _connectable_host(host)
    port = _port(port)
    query = urllib.parse.urlencode({
        "host": host,
        "port": str(port),
        "session": session.session_id,
        "token": session.token,
        "protocol": str(PREVIEW_PROTOCOL_VERSION),
        "renderer": str(PROTOCOL_VERSION),
        "project": session.project_id,
        "name": session.project_name,
    })
    return urllib.parse.urlunparse((
        PREVIEW_SCHEME, PREVIEW_AUTHORITY, PREVIEW_PATH, "", query, "",
    ))


def parse_preview_uri(uri: str) -> dict[str, Any]:
    """Parse and validate a Pydrud preview QR payload.

    This helper is public protocol tooling for the future independent client;
    it does not connect to the server.
    """
    parsed = urllib.parse.urlparse(str(uri))
    if (parsed.scheme != PREVIEW_SCHEME or parsed.netloc != PREVIEW_AUTHORITY
            or parsed.path != PREVIEW_PATH):
        raise PreviewProtocolError("invalid_uri", "not a Pydrud preview URI")
    try:
        values = urllib.parse.parse_qs(parsed.query, strict_parsing=True)
    except ValueError as exc:
        raise PreviewProtocolError(
            "invalid_uri", "malformed preview URI query") from exc

    def one(name: str) -> str:
        found = values.get(name, [])
        if len(found) != 1 or not found[0]:
            raise PreviewProtocolError(
                "invalid_uri", f"preview URI requires one {name!r} value")
        return found[0]

    protocol = _integer(one("protocol"), "protocol")
    renderer = _integer(one("renderer"), "renderer")
    if protocol != PREVIEW_PROTOCOL_VERSION:
        raise PreviewProtocolError(
            "unsupported_version",
            f"preview protocol {protocol} is not supported",
        )
    if renderer != PROTOCOL_VERSION:
        raise PreviewProtocolError(
            "unsupported_renderer",
            f"renderer protocol {renderer} is not supported",
        )
    try:
        host = _connectable_host(one("host"))
        port = _port(_integer(one("port"), "port"))
    except ValueError as exc:
        raise PreviewProtocolError("invalid_uri", str(exc)) from exc
    return {
        "host": host,
        "port": port,
        "session_id": one("session"),
        "token": one("token"),
        "protocol_version": protocol,
        "renderer_protocol_version": renderer,
        "project_id": one("project"),
        "project_name": one("name"),
    }


def validate_client_hello(message: object, session: PreviewSession) -> dict[str, Any]:
    """Validate the first client frame and return normalized connection data."""
    if not isinstance(message, dict):
        raise PreviewProtocolError("invalid_hello", "hello must be a JSON object")
    if message.get("type") != "preview_hello":
        raise PreviewProtocolError("invalid_hello", "first frame must be preview_hello")
    if message.get("protocol") != PREVIEW_PROTOCOL:
        raise PreviewProtocolError("invalid_hello", "unknown preview protocol")
    version = _integer(message.get("protocol_version"), "protocol_version")
    if version != PREVIEW_PROTOCOL_VERSION:
        raise PreviewProtocolError(
            "unsupported_version",
            f"expected preview protocol {PREVIEW_PROTOCOL_VERSION}, got {version}",
        )
    renderer = _integer(
        message.get("renderer_protocol_version"),
        "renderer_protocol_version",
    )
    if renderer != PROTOCOL_VERSION:
        raise PreviewProtocolError(
            "unsupported_renderer",
            f"expected renderer protocol {PROTOCOL_VERSION}, got {renderer}",
        )
    if not hmac.compare_digest(
            str(message.get("session_id") or ""), session.session_id):
        raise PreviewProtocolError("authentication_failed", "invalid session or token")
    if not session.matches_token(message.get("token")):
        raise PreviewProtocolError("authentication_failed", "invalid session or token")

    capabilities = message.get("capabilities")
    if not isinstance(capabilities, dict):
        raise PreviewProtocolError(
            "missing_capabilities", "client capabilities must be an object")
    missing = sorted(name for name in REQUIRED_RENDERER_CAPABILITIES
                     if capabilities.get(name) is not True)
    if missing:
        raise PreviewProtocolError(
            "missing_capabilities",
            "client is missing required renderer capabilities: "
            + ", ".join(missing),
        )

    metrics = message.get("metrics") or {}
    if not isinstance(metrics, dict):
        raise PreviewProtocolError("invalid_metrics", "metrics must be an object")
    normalized_metrics = _normalize_metrics(metrics)

    revision = _integer(message.get("last_revision", 0), "last_revision")
    if revision < 0 or revision > 9_000_000_000_000_000:
        raise PreviewProtocolError("invalid_revision", "last_revision is out of range")

    client = message.get("client") or {}
    if not isinstance(client, dict):
        raise PreviewProtocolError("invalid_client", "client metadata must be an object")
    return {
        "capabilities": dict(capabilities),
        "metrics": normalized_metrics,
        "last_revision": revision,
        "client": {
            "name": str(client.get("name") or "preview client")[:100],
            "version": str(client.get("version") or "")[:100],
            "platform": str(client.get("platform") or "")[:100],
        },
    }


def welcome_message(session: PreviewSession, port: int) -> dict[str, Any]:
    """Server handshake response sent before any renderer commands."""
    return {
        "type": "preview_welcome",
        "protocol": PREVIEW_PROTOCOL,
        "protocol_version": PREVIEW_PROTOCOL_VERSION,
        "renderer_protocol_version": PROTOCOL_VERSION,
        "session_id": session.session_id,
        "project": {
            "id": session.project_id,
            "name": session.project_name,
        },
        "port": _port(port),
        "capabilities": dict(SERVER_CAPABILITIES),
        "limits": {"max_frame_bytes": MAX_FRAME_BYTES},
    }


def rejection_message(error: PreviewProtocolError) -> dict[str, Any]:
    return {
        "type": "preview_reject",
        "protocol": PREVIEW_PROTOCOL,
        "protocol_version": PREVIEW_PROTOCOL_VERSION,
        "code": error.code,
        "message": error.message,
    }


def _normalize_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Bound client-controlled dimensions before they reach layout code."""
    values = dict(metrics)
    if "platform_version" not in values and "sdk" in values:
        # Compatibility for preview clients using the pre-neutral metric name.
        values["platform_version"] = values["sdk"]
    if "width" not in values and "width_dp" in values:
        values["width"] = values["width_dp"]
    if "height" not in values and "height_dp" in values:
        values["height"] = values["height_dp"]
    if "text_scale" not in values and "fontScale" in values:
        values["text_scale"] = values["fontScale"]
    insets = values.get("insets")
    if insets is not None:
        if not isinstance(insets, dict):
            raise PreviewProtocolError(
                "invalid_metrics", "metrics.insets must be an object")
        for side in ("top", "right", "bottom", "left"):
            if side in insets:
                values.setdefault(f"padding_{side}", insets[side])

    specs = {
        "width": (1.0, 100_000.0, 360.0),
        "height": (1.0, 100_000.0, 640.0),
        "width_px": (1.0, 1_000_000.0, None),
        "height_px": (1.0, 1_000_000.0, None),
        "density": (0.1, 20.0, 2.0),
        "dpi": (1.0, 10_000.0, None),
        "xdpi": (1.0, 10_000.0, None),
        "ydpi": (1.0, 10_000.0, None),
        "text_scale": (0.1, 10.0, None),
        "status_bar_height": (0.0, 100_000.0, None),
        "navigation_bar_height": (0.0, 100_000.0, None),
        "padding_top": (0.0, 100_000.0, None),
        "padding_right": (0.0, 100_000.0, None),
        "padding_bottom": (0.0, 100_000.0, None),
        "padding_left": (0.0, 100_000.0, None),
        "keyboard_height": (0.0, 100_000.0, None),
        "refresh_rate": (1.0, 1_000.0, None),
        "smallest_width": (0.0, 100_000.0, None),
    }
    normalized: dict[str, Any] = {}
    for name, (minimum, maximum, default) in specs.items():
        value = values.get(name, default)
        if value is None:
            continue
        if isinstance(value, bool):
            raise PreviewProtocolError(
                "invalid_metrics", f"metrics.{name} must be numeric")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise PreviewProtocolError(
                "invalid_metrics", f"metrics.{name} must be numeric") from exc
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise PreviewProtocolError(
                "invalid_metrics",
                f"metrics.{name} must be between {minimum:g} and {maximum:g}",
            )
        normalized[name] = number

    normalized["dark"] = bool(values.get("dark", False))
    for name in ("orientation", "ui_mode", "model", "platform_version"):
        if name in values:
            normalized[name] = str(values[name])[:100]
    return normalized


def _connectable_host(value: object) -> str:
    host = str(value or "").strip().strip("[]")
    if not host or host in {"0.0.0.0", "::"}:
        raise ValueError("QR host must be a connectable IP address or hostname")
    if any(ch.isspace() for ch in host) or "/" in host:
        raise ValueError("invalid preview host")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if len(host) > 253 or any(not label for label in host.split(".")):
            raise ValueError("invalid preview hostname")
    return host


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise PreviewProtocolError("invalid_hello", f"{name} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise PreviewProtocolError(
            "invalid_hello", f"{name} must be an integer") from exc


def _port(value: object) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("preview port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("preview port must be between 1 and 65535")
    return port


__all__ = [
    "DEFAULT_PREVIEW_HOST", "DEFAULT_PREVIEW_PORT", "PREVIEW_PROTOCOL",
    "PREVIEW_PROTOCOL_VERSION", "PreviewProtocolError", "PreviewSession",
    "REQUIRED_RENDERER_CAPABILITIES", "SERVER_CAPABILITIES",
    "build_preview_uri", "fallback_project_id", "parse_preview_uri",
    "rejection_message", "validate_client_hello", "welcome_message",
]
