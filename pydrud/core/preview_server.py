"""Authenticated desktop server for independent live-preview renderers."""

from __future__ import annotations

import socket
import threading
import time
from typing import Any, Callable, Optional

from pydrud.core.preview import (
    PreviewProtocolError,
    PreviewSession,
    rejection_message,
    validate_client_hello,
    welcome_message,
)
from pydrud.core.protocol import (
    MAX_FRAME_BYTES,
    ProtocolError,
    decode_envelope,
    encode_envelope,
)

StatusCallback = Callable[[str, dict[str, Any]], None]


class PreviewServer:
    """Accept authenticated preview clients and attach them to an ``App``.

    The server owns only network/session concerns. Widget construction, event
    dispatch, revision state, patching, ACK/NACK and resynchronization remain
    in :class:`pydrud.runtime.app.App`.
    """

    def __init__(
        self,
        app,
        session: PreviewSession,
        *,
        host: str = "0.0.0.0",
        port: int = 8597,
        handshake_timeout: float = 10.0,
        on_status: Optional[StatusCallback] = None,
    ):
        self.app = app
        self.session = session
        self.host = str(host)
        self.port = int(port)
        self.handshake_timeout = max(1.0, float(handshake_timeout))
        self.on_status = on_status
        self._listener: Optional[socket.socket] = None
        self._active: Optional[socket.socket] = None
        self._clients: set[socket.socket] = set()
        self._workers: set[threading.Thread] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()

    @property
    def address(self) -> tuple[str, int]:
        if self._listener is None:
            return self.host, self.port
        address = self._listener.getsockname()
        return str(address[0]), int(address[1])

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active is not None

    def start(self) -> tuple[str, int]:
        """Bind the listener without blocking in the accept loop."""
        if self._listener is not None:
            return self.address
        family = socket.AF_INET6 if ":" in self.host else socket.AF_INET
        listener = socket.socket(family, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if family == socket.AF_INET6:
            try:
                listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except OSError:
                pass
        try:
            listener.bind((self.host, self.port))
            listener.listen(8)
            listener.settimeout(0.5)
        except Exception:
            listener.close()
            raise
        self._listener = listener
        self.port = self.address[1]
        self._stop.clear()
        return self.address

    def serve_forever(self) -> None:
        """Accept clients until :meth:`stop` is called."""
        if self._listener is None:
            self.start()
        assert self._listener is not None
        listener = self._listener
        self._notify("listening", host=self.address[0], port=self.address[1])
        while not self._stop.is_set():
            try:
                client, peer = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._stop.is_set():
                    break
                raise
            with self._lock:
                overloaded = len(self._clients) >= 8
                if not overloaded:
                    self._clients.add(client)
            if overloaded:
                try:
                    _send_message(client, rejection_message(PreviewProtocolError(
                        "client_busy", "too many pending preview connections")))
                except (OSError, ProtocolError):
                    pass
                client.close()
                continue
            worker = threading.Thread(
                target=self._serve_client,
                args=(client, peer),
                daemon=True,
                name="pydrud-preview-client",
            )
            with self._lock:
                self._workers.add(worker)
            worker.start()

    def stop(self) -> None:
        """Close the listener and all handshaking/active clients."""
        self._stop.set()
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        with self._lock:
            clients = list(self._clients)
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                client.close()
            except OSError:
                pass
        with self._lock:
            workers = list(self._workers)
        current = threading.current_thread()
        for worker in workers:
            if worker is not current:
                worker.join(timeout=1.0)

    def _serve_client(self, client: socket.socket, peer) -> None:
        peer_text = _peer_text(peer)
        claimed = False
        try:
            client.settimeout(self.handshake_timeout)
            raw = _read_frame(client, timeout=self.handshake_timeout)
            try:
                hello = decode_envelope(raw)
            except ProtocolError as exc:
                raise PreviewProtocolError("invalid_hello", str(exc)) from exc
            normalized = validate_client_hello(hello, self.session)

            with self._lock:
                if self._active is not None:
                    raise PreviewProtocolError(
                        "client_busy", "another preview client is already connected")
                self._active = client
                claimed = True

            client.settimeout(None)
            _send_message(client, welcome_message(self.session, self.port))
            self._notify(
                "connected",
                peer=peer_text,
                client=normalized["client"],
                revision=normalized["last_revision"],
            )
            self.app.serve_transport(
                client,
                capabilities=normalized["capabilities"],
                metrics=normalized["metrics"],
                native_revision=normalized["last_revision"],
            )
        except PreviewProtocolError as exc:
            try:
                _send_message(client, rejection_message(exc))
            except (OSError, ProtocolError):
                pass
            self._notify("rejected", peer=peer_text, code=exc.code)
        except (ConnectionError, OSError, socket.timeout) as exc:
            self._notify("connection_error", peer=peer_text, error=str(exc))
        except Exception as exc:  # pragma: no cover - defensive server boundary
            self._notify("server_error", peer=peer_text, error=str(exc))
        finally:
            with self._lock:
                if claimed and self._active is client:
                    self._active = None
                self._clients.discard(client)
                self._workers.discard(threading.current_thread())
            try:
                client.close()
            except OSError:
                pass
            if claimed and not self._stop.is_set():
                self._notify("disconnected", peer=peer_text)

    def _notify(self, event: str, **data: Any) -> None:
        if self.on_status is None:
            return
        try:
            self.on_status(event, data)
        except Exception:
            pass


def _read_frame(sock: socket.socket, *, timeout: float) -> str:
    """Read one frame without buffering bytes belonging to the next phase."""
    frame = bytearray()
    deadline = time.monotonic() + timeout
    while len(frame) <= MAX_FRAME_BYTES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise socket.timeout("preview hello timed out")
        sock.settimeout(remaining)
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("connection closed before preview hello")
        frame.extend(chunk)
        if chunk == b"\n":
            try:
                return frame.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise PreviewProtocolError(
                    "invalid_hello", "preview hello must be UTF-8") from exc
    raise PreviewProtocolError(
        "frame_too_large",
        f"preview hello exceeds {MAX_FRAME_BYTES} bytes",
    )


def _send_message(sock: socket.socket, message: dict[str, Any]) -> None:
    sock.sendall(encode_envelope(message).encode("utf-8"))


def _peer_text(peer: object) -> str:
    if isinstance(peer, tuple) and len(peer) >= 2:
        return f"{peer[0]}:{peer[1]}"
    return str(peer)


__all__ = ["PreviewServer"]
