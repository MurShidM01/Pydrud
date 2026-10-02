"""Versioned transactional rendering protocol primitives.

The wire format remains NDJSON for backwards compatibility, while render
transactions gain revisions, acknowledgements, bounded sizes and explicit
recovery semantics.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional


PROTOCOL_VERSION = 2
MAX_FRAME_BYTES = 2 * 1024 * 1024
DEFAULT_RENDER_TIMEOUT = 5.0


class ProtocolError(ValueError):
    """A structured protocol violation.

    Subclasses ``ValueError`` for compatibility with the pre-v2 decoder,
    which exposed JSON parsing failures as value errors.
    """


@dataclass(frozen=True, slots=True)
class RenderTransaction:
    tx_id: str
    revision: int
    base_revision: int
    kind: str  # patch | snapshot
    payload: dict[str, Any]
    created_at: float

    @classmethod
    def create(
        cls,
        *,
        revision: int,
        base_revision: int,
        kind: str,
        payload: dict[str, Any],
    ) -> "RenderTransaction":
        return cls(
            tx_id="tx_" + secrets.token_hex(10),
            revision=int(revision),
            base_revision=int(base_revision),
            kind=kind,
            payload=dict(payload),
            created_at=time.monotonic(),
        )

    def envelope(self) -> dict[str, Any]:
        result = {
            "cmd": "render_transaction",
            "protocol_version": PROTOCOL_VERSION,
            "transaction_id": self.tx_id,
            "revision": self.revision,
            "base_revision": self.base_revision,
            "kind": self.kind,
        }
        result.update(self.payload)
        return result


def encode_envelope(message: dict[str, Any]) -> str:
    """Encode and enforce a hard frame limit."""
    if not isinstance(message, dict):
        raise ProtocolError("protocol message must be an object")
    raw = json.dumps(message, separators=(",", ":"), ensure_ascii=False, default=str)
    encoded = (raw + "\n").encode("utf-8")
    if len(encoded) > MAX_FRAME_BYTES:
        raise ProtocolError(
            f"protocol frame is {len(encoded)} bytes; maximum is {MAX_FRAME_BYTES}"
        )
    return encoded.decode("utf-8")


def decode_envelope(line: str) -> Optional[dict[str, Any]]:
    if not isinstance(line, str):
        raise ProtocolError("protocol frame must be text")
    raw = line.strip()
    if not raw:
        return None
    encoded_size = len(raw.encode("utf-8")) + 1
    if encoded_size > MAX_FRAME_BYTES:
        raise ProtocolError(
            f"protocol frame is {encoded_size} bytes; maximum is {MAX_FRAME_BYTES}"
        )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ProtocolError("protocol frame must decode to an object")
    return value
