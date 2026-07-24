"""
Pydrud App — the top-level entry point.

An ``App`` owns the widget-tree, state, event dispatcher, and bridge.
It provides the familiar ``ft.app(target=...)`` developer experience.
"""

from __future__ import annotations
import json
import os
import socket
import sys
import time
from typing import Any, Callable, Optional

from pydrud.core.state import State
from pydrud.core.diff import TreeDiff
from pydrud.core.events import EventDispatcher
from pydrud.core.bridge import BridgeProtocol
from pydrud.widgets import Widget


class App:
    """A Pydrud application.

    Typical usage::

        def main(page: Page):
            page.add(Text("Hello, World!"))

        app = App(target=main)
        app.run()
    """

    def __init__(
        self,
        *,
        target: Optional[Callable] = None,
        title: str = "Pydrud App",
        host: str = "127.0.0.1",
        port: int = 8595,
        assets_dir: str = "assets",
        **kwargs,
    ):
        self.target = target
        self.title = title
        self.host = host
        self.port = port
        self.assets_dir = assets_dir

        self._page = _Page(self)
        self._event_dispatcher = EventDispatcher()
        self._prev_tree: Optional[Widget] = None
        self._current_tree: Optional[Widget] = None
        self._bridge = BridgeProtocol()
        self._connected = False
        self._transport: Optional[socket.socket] = None

    # ── public API ────────────────────────────────────────────────────────

    @property
    def page(self):
        return self._page

    def run(self, *, retry: bool = True, retry_delay: float = 0.5, max_retries: int = 30):
        """Start the app: build the tree, connect to Android bridge, enter event loop.

        Args:
            retry: If True, retry the TCP connection (for Chaquopy where the
                   Android bridge server may not be ready yet).
            retry_delay: Seconds between connection retries.
            max_retries: Maximum connection attempts before giving up.
        """
        if self.target:
            self.target(self._page)

        self._current_tree = self._page.build()
        self._event_dispatcher.register_tree(self._current_tree)

        self._start_bridge(retry=retry, retry_delay=retry_delay, max_retries=max_retries)

    def build(self) -> Widget:
        """Convenience: run the target and return the widget tree without
        connecting the bridge.  Useful for testing."""
        if self.target:
            self.target(self._page)
        self._current_tree = self._page.build()
        self._event_dispatcher.register_tree(self._current_tree)
        return self._current_tree

    def update(self):
        """Rebuild the widget tree and send a full re-render.

        For V1 we send the full tree on every state change rather than
        incremental patches, because the ``create`` / ``delete`` patch
        operations don't carry enough parent-attachment info for the
        Android renderer to apply them reliably.
        """
        if self.target:
            self._page.clear()
            self.target(self._page)
        new = self._page.build()

        self._current_tree = new
        self._event_dispatcher.unregister_all()
        self._event_dispatcher.register_tree(new)

        if self._connected and self._transport:
            msg = self._bridge.encode_full_render(new.to_dict())
            self._send(msg)

        self._prev_tree = None

    def render(self):
        """Force a full re-render (send the entire tree)."""
        if self.target:
            self._page.clear()
            self.target(self._page)
        tree = self._page.build()
        self._current_tree = tree
        self._event_dispatcher.unregister_all()
        self._event_dispatcher.register_tree(tree)

        if self._connected and self._transport:
            msg = self._bridge.encode_full_render(tree.to_dict())
            self._send(msg)

        self._prev_tree = None

    def update_state(self, state: State):
        """Rebuild after a State change."""
        self.update()

    # ── bridge internals ──────────────────────────────────────────────────

    def _start_bridge(self, *, retry=True, retry_delay=0.5, max_retries=30):
        """Connect to the Android side via TCP socket.

        In Chaquopy the Android BridgeService starts first and listens.
        We retry until the server is accepting connections.
        """
        attempts = 0
        last_error = None

        while attempts < max_retries:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10.0)
                sock.connect((self.host, self.port))
                sock.settimeout(None)
                self._transport = sock
                self._connected = True
                self._buffer = b""

                # Send the full initial tree.
                msg = self._bridge.encode_full_render(self._current_tree.to_dict())
                self._send(msg)

                # Enter listen loop (blocks).
                self._listen_loop(sock)
                return
            except ConnectionRefusedError as e:
                last_error = e
                if not retry:
                    break
                attempts += 1
                time.sleep(retry_delay)
            except Exception as exc:
                print(f"[Pydrud] Bridge error: {exc}")
                if not retry:
                    break
                attempts += 1
                time.sleep(retry_delay)

        print(f"[Pydrud] Bridge connection failed after {attempts} attempts: {last_error}")
        print("[Pydrud] Running in headless/test mode (no Android bridge).")
        self._connected = False

    def _send(self, msg: str):
        if self._transport and self._connected:
            try:
                self._transport.sendall(msg.encode("utf-8"))
            except Exception:
                self._connected = False

    def _listen_loop(self, sock):
        """Read newline-delimited JSON events from the socket."""
        self._buffer = b""
        try:
            while True:
                try:
                    data = sock.recv(4096)
                    if not data:
                        break
                except socket.timeout:
                    continue
                self._buffer += data
                while b"\n" in self._buffer:
                    line, self._buffer = self._buffer.split(b"\n", 1)
                    decoded = line.decode("utf-8").strip()
                    if decoded:
                        event = json.loads(decoded)
                        if event.get("type") == "ready":
                            # Capture screen dimensions for responsive scaling.
                            d = event.get("data", {})
                            from pydrud.core.responsive import Responsive as _R
                            _R.init(
                                width_dp=d.get("width", 360),
                                height_dp=d.get("height", 640),
                                density=d.get("density", 2.0),
                            )
                            continue
                        self._event_dispatcher.dispatch(decoded)
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            self._connected = False
            try:
                sock.close()
            except Exception:
                pass


class _Page:
    """The mutable page object passed to the user's builder function."""

    def __init__(self, app: App):
        self._app = app
        self.controls: list[Widget] = []
        self.title: str = app.title
        self.bgcolor: Optional[str] = None
        self.scroll: Optional[str] = None
        self.padding: Optional[Any] = None
        self._built = False  # track if first build happened

    def add(self, *controls: Widget):
        self.controls.extend(controls)

    def clear(self):
        self.controls.clear()

    def remove(self, key: str):
        self.controls = [c for c in self.controls if c.key != key]

    def update(self):
        self._app.update()

    def build(self) -> Widget:
        from pydrud.widgets.layout import Container, Column

        style = {}
        if self.bgcolor:
            style["bg"] = self.bgcolor
        if self.scroll:
            style["scroll"] = True
        if self.padding is not None:
            from pydrud.widgets.styling import EdgeInsets
            if isinstance(self.padding, (int, float)):
                padding = EdgeInsets.all(self.padding)
            else:
                padding = self.padding
            style["padding"] = padding.to_dict()

        self._built = True
        return Container(
            key="_page",
            style={**style, "width": "match", "height": "match"},
            expand=1,
            child=Column(
                expand=1,
                children=list(self.controls),
            ),
        )


# ── Entry point for Chaquopy (called from Java) ──────────────────────────────


def start_app():
    """Entry point called by MainActivity after the bridge server is ready.

    This function is loaded by Chaquopy's Python runtime and invoked from
    Java via::

        Python.getInstance().getModule("app.main").callAttr("start_app")
    """
    from app.main import main
    app = App(target=main)
    app.run()
