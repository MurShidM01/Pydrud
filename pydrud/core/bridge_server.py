"""A device-facing bridge for the ``host`` runtime backend.

When a project is built with the host backend the APK embeds no interpreter:
Python runs on the developer's machine and the app dials *out* to it. This
module is that listener. It speaks the plain bridge protocol (the same NDJSON
envelope :class:`~pydrud.runtime.app.App` already understands) with no preview
handshake, so a device can attach with nothing more than an ``adb reverse``
forward — no QR code, no session token, no connect screen.

It is a local-development transport, exactly like the on-device bridge the
Chaquopy backend uses: loopback-only by default, one renderer at a time, and
intended for a trusted machine or a USB-attached device.
"""

from __future__ import annotations

import socket
import threading
from typing import Any, Callable, Optional

StatusCallback = Callable[[str, dict[str, Any]], None]


class BridgeServer:
    """Accept one device renderer at a time and attach it to an ``App``.

    Only networking lives here. Widget construction, event dispatch, revision
    state, patching, ACK/NACK and resynchronization stay in
    :class:`~pydrud.runtime.app.App`.
    """

    def __init__(
        self,
        app,
        *,
        host: str = "127.0.0.1",
        port: int = 8597,
        on_status: Optional[StatusCallback] = None,
    ):
        self.app = app
        self.host = str(host)
        self.port = int(port)
        self.on_status = on_status
        self._listener: Optional[socket.socket] = None
        self._active: Optional[socket.socket] = None
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
        """Bind the listener without entering the accept loop."""
        if self._listener is not None:
            return self.address
        family = socket.AF_INET6 if ":" in self.host else socket.AF_INET
        listener = socket.socket(family, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((self.host, self.port))
            listener.listen(1)
            listener.settimeout(0.5)
        except Exception:
            listener.close()
            raise
        self._listener = listener
        self.port = self.address[1]
        self._stop.clear()
        return self.address

    def serve_forever(self) -> None:
        """Accept renderers until :meth:`stop` is called."""
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
                busy = self._active is not None
                if not busy:
                    self._active = client
            if busy:
                # One renderer at a time, matching the on-device bridge.
                try:
                    client.close()
                except OSError:
                    pass
                continue
            worker = threading.Thread(
                target=self._serve_client,
                args=(client, peer),
                daemon=True,
                name="pydrud-bridge-client",
            )
            with self._lock:
                self._workers.add(worker)
            worker.start()

    def stop(self) -> None:
        """Close the listener and the active renderer."""
        self._stop.set()
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        with self._lock:
            active = self._active
        if active is not None:
            try:
                active.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                active.close()
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
        try:
            client.settimeout(None)
            self._notify("connected", peer=peer_text)
            # The device sends its ``ready`` frame itself; the app's reader
            # loop negotiates capabilities and metrics from it, so no
            # handshake is read here.
            self.app.serve_transport(client)
        except (ConnectionError, OSError) as exc:
            self._notify("connection_error", peer=peer_text, error=str(exc))
        except Exception as exc:  # pragma: no cover - defensive boundary
            self._notify("server_error", peer=peer_text, error=str(exc))
        finally:
            with self._lock:
                if self._active is client:
                    self._active = None
                self._workers.discard(threading.current_thread())
            try:
                client.close()
            except OSError:
                pass
            if not self._stop.is_set():
                self._notify("disconnected", peer=peer_text)

    def _notify(self, event: str, **data: Any) -> None:
        if self.on_status is None:
            return
        try:
            self.on_status(event, data)
        except Exception:
            pass


def _peer_text(peer: object) -> str:
    if isinstance(peer, tuple) and len(peer) >= 2:
        return f"{peer[0]}:{peer[1]}"
    return str(peer)


__all__ = ["BridgeServer"]
