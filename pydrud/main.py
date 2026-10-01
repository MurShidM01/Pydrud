"""
Pydrud App — the top-level entry point.

An ``App`` owns the widget-tree, state, event dispatcher, and bridge.
It provides the familiar ``ft.app(target=...)`` developer experience.
"""

from __future__ import annotations
import importlib
import json
import os
import queue
import socket
import sys
import threading
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
        self._current_tree: Optional[Widget] = None
        self._bridge = BridgeProtocol()
        self._connected = False
        self._transport: Optional[socket.socket] = None
        # ── Thread-safe event queue ─────────────────────────────────
        self._event_queue: queue.Queue = queue.Queue()
        self._shutdown_event = threading.Event()
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        # ── Router support ─────────────────────────────────────────
        self._router: Optional[Any] = None
        # ── Hot Reload ─────────────────────────────────────────────
        self._watcher: Optional[Any] = None
        self._watch_dirs: list[str] = ["src"]
        self._project_root: str = self._find_root()

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
        """Rebuild the widget tree and send incremental patches via TreeDiff.

        Compares the old tree against the newly built tree, computes
        incremental patches (create/update/delete/replace) with proper
        parent_key info, and sends only the patches over the bridge.
        Falls back to full_render when the patch list is too large (>50).
        """
        # Clone the current tree for diff comparison before rebuilding.
        old_clone = self._current_tree.clone() if self._current_tree else None

        if self.target:
            self._page.clear()
            self.target(self._page)
        new = self._page.build()

        self._current_tree = new
        self._event_dispatcher.unregister_all()
        self._event_dispatcher.register_tree(new)

        if self._connected and self._transport:
            if old_clone is not None:
                from pydrud.core.diff import TreeDiff as _TreeDiff
                patches = _TreeDiff.diff(old_clone, new)
                if patches and len(patches) <= 50:
                    msg = self._bridge.encode_render([p.to_dict() for p in patches])
                    self._send(msg)
                else:
                    msg = self._bridge.encode_full_render(new.to_dict())
                    self._send(msg)
            else:
                # First call to update() — full render.
                msg = self._bridge.encode_full_render(new.to_dict())
                self._send(msg)

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

    def update_state(self, state: State):
        """Rebuild after a State change."""
        self.update()

    # ── Hot Reload ─────────────────────────────────────────────────────────

    def enable_hot_reload(self, watch_dirs: list[str] | None = None) -> None:
        """Start watching source files for changes and auto-rebuild the UI.

        When a ``.py`` file changes, the affected module is reloaded,
        the widget tree is rebuilt, and incremental patches are sent
        to the device — no APK recompilation needed.

        Args:
            watch_dirs: Directories to watch (relative to project root).
                        Defaults to ``["src"]``.
        """
        from pydrud.core.watcher import FileWatcher
        dirs = [os.path.join(self._project_root, d) for d in (watch_dirs or self._watch_dirs)]
        self._watcher = FileWatcher(dirs, self._on_hot_reload)
        self._watcher.start()

    def _on_hot_reload(self, filepath: str) -> None:
        """Called by the file watcher when a source file changes."""
        try:
            rel = os.path.relpath(filepath, self._project_root)
            mod_parts = rel.replace(os.sep, "/").replace(".py", "").split("/")
            mod_name = ".".join(mod_parts)

            # Reload the changed module.
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])

            # Rebuild the widget tree.
            if self.target:
                self._page.clear()
                # Re-import the target if it was reloaded.
                self.target(self._page)
                self.render()
        except Exception as exc:
            print(f"[Pydrud] Hot Reload error for {filepath}: {exc}")

    def hot_restart(self) -> None:
        """Fully reset the app state and re-render from scratch.

        Clears the navigation stack, resets the page, re-imports all
        user modules, calls ``target(page)`` again, and sends a full
        tree render. This is the Python equivalent of "restart app".
        """
        # Reset navigation.
        if self._router is not None:
            self._router.reset()
            self._router.current_route = None

        # Reset event handling.
        self._event_dispatcher.unregister_all()

        # Reload all user modules in src/ to pick up fresh code.
        user_modules = _find_user_modules(self._project_root)
        for mod_name in user_modules:
            if mod_name in sys.modules:
                try:
                    importlib.reload(sys.modules[mod_name])
                except Exception as exc:
                    print(f"[Pydrud] Hot Restart reload error {mod_name}: {exc}")

        # Rebuild from scratch.
        self._page.clear()
        if self.target:
            self.target(self._page)
        self.render()

    @staticmethod
    def _find_root() -> str:
        """Walk up from cwd to find the project root (has pydrud.yaml)."""
        cwd = os.getcwd()
        current = cwd
        while True:
            if os.path.isfile(os.path.join(current, "pydrud.yaml")):
                return current
            parent = os.path.dirname(current)
            if parent == current:
                return cwd
            current = parent

    # ── Router support ────────────────────────────────────────────────────

    def attach_router(self, router) -> None:
        """Attach a Router for screen-based navigation.

        The router receives back-button events from the Android hardware
        back button.
        """
        self._router = router
        router.attach(self)

    # ── bridge internals ──────────────────────────────────────────────────

    def _start_bridge(self, *, retry=True, retry_delay=0.5, max_retries=30):
        """Connect to the Android side via TCP socket.

        In Chaquopy the Android BridgeService starts first and listens.
        We retry until the server is accepting connections.

        Once connected, a background daemon thread reads NDJSON events
        from the socket and pushes them onto an internal queue. The main
        thread processes events from the queue, keeping the event loop
        responsive and allowing ``page.update()`` to be called safely
        from event handlers without blocking the socket reader.
        """
        self._running = True
        self._shutdown_event.clear()
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

                # Start background reader thread.
                self._reader_thread = threading.Thread(
                    target=self._reader_loop,
                    args=(sock,),
                    daemon=True,
                    name="pydrud-reader",
                )
                self._reader_thread.start()

                # Enter event processing loop (main thread).
                self._event_loop()
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
                with self._lock:
                    self._transport.sendall(msg.encode("utf-8"))
            except Exception:
                self._connected = False

    def _reader_loop(self, sock):
        """Background thread: read NDJSON lines from the socket and enqueue them."""
        buffer = b""
        try:
            while self._running and not self._shutdown_event.is_set():
                try:
                    data = sock.recv(4096)
                    if not data:
                        break
                except socket.timeout:
                    continue
                except OSError:
                    break
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    decoded = line.decode("utf-8").strip()
                    if decoded:
                        self._event_queue.put(decoded)
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            self._event_queue.put(None)  # Sentinel: signal the event loop to stop

    def _event_loop(self):
        """Process incoming events from the queue on the main thread.

        This replaces the old blocking ``_listen_loop``. Events are
        dequeued and dispatched to registered callbacks. The loop
        exits when a ``None`` sentinel is received (connection lost)
        or when ``_running`` is set to ``False``.
        """
        try:
            while self._running:
                try:
                    raw = self._event_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if raw is None:
                    # Sentinel — connection lost.
                    break
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # Handle special events inline.
                if event.get("type") == "ready":
                    d = event.get("data", {})
                    from pydrud.core.responsive import Responsive as _R
                    from pydrud.core.responsive import MediaQuery as _MQ
                    _R.init(
                        width_dp=d.get("width", 360),
                        height_dp=d.get("height", 640),
                        density=d.get("density", 2.0),
                    )
                    _MQ.init(
                        width_dp=d.get("width", 360),
                        height_dp=d.get("height", 640),
                        density=d.get("density", 2.0),
                        status_bar_height=d.get("status_bar_height", 24),
                    )
                    continue

                # Handle hardware back button via Router.
                if event.get("type") == "back":
                    if self._router is not None:
                        handled = self._router.handle_back()
                        if not handled:
                            # No more screens to pop — tell Android to finish.
                            self._send(
                                self._bridge.encode_command("finish_activity")
                            )
                    continue

                # Dispatch to registered event handlers.
                self._event_dispatcher.dispatch(raw)
        finally:
            self._connected = False
            if self._transport:
                try:
                    self._transport.close()
                except Exception:
                    pass


class _Page:
    """The mutable page object passed to the user's builder function."""

    def __init__(self, app: App):
        self._app = app
        self.controls: list[Widget] = []
        self.floating: list[Widget] = []  # Widgets rendered as overlay (e.g. FAB)
        self.title: str = app.title
        self.bgcolor: Optional[str] = None
        self.scroll: Optional[str] = None
        self.padding: Optional[Any] = None
        self._built = False  # track if first build happened

    def add(self, *controls: Widget):
        self.controls.extend(controls)

    def add_floating(self, widget: Widget):
        """Add a widget that renders as an overlay (e.g. FAB).

        Floating widgets become direct children of the root FrameLayout,
        enabling absolute positioning via FrameLayout gravity.
        """
        self.floating.append(widget)

    def clear(self):
        self.controls.clear()
        self.floating.clear()

    def remove(self, key: str):
        self.controls = [c for c in self.controls if c.key != key]

    def update(self):
        self._app.update()

    def set_system_ui(
        self,
        *,
        status_bar_color: str | None = None,
        icon_brightness: str | None = None,
    ):
        """Send system UI styling command to Android.

        Args:
            status_bar_color: Hex color string, e.g. ``"#FF1A73E8"``.
            icon_brightness: ``"light"`` (white icons) or ``"dark"``
                             (dark icons, for light status bars).
        """
        cmd = {"cmd": "set_system_ui"}
        if status_bar_color:
            cmd["status_bar_color"] = status_bar_color
        if icon_brightness:
            cmd["icon_brightness"] = icon_brightness
        self._app._send(self._app._bridge.encode_command(**cmd))

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
        # Build the root Container with the main Column as first child.
        # NOTE: Column must have height="match" because parent is a FrameLayout
        # (from Container), which ignores expand/weight. Without explicit
        # height="match", the Column gets WRAP_CONTENT height = 0 for children.
        root = Container(
            key="_page",
            style={**style, "width": "match", "height": "match"},
            expand=1,
            child=Column(
                expand=1,
                style={"height": "match"},
                children=list(self.controls),
            ),
        )
        # Add floating widgets as direct siblings of the Column inside
        # the root FrameLayout (for absolute positioning).
        for f in self.floating:
            root.children.append(f)
        return root


# ── Helper: find user modules for hot restart ─────────────────────────────────


def _find_user_modules(project_root: str) -> list[str]:
    """Find all importable module names under the project's src/ directory."""
    src_dir = os.path.join(project_root, "src")
    modules: list[str] = []
    if not os.path.isdir(src_dir):
        return modules
    for root, _dirs, files in os.walk(src_dir):
        for fname in files:
            if fname.endswith(".py") and fname != "__init__.py":
                rel = os.path.relpath(os.path.join(root, fname), src_dir)
                mod = rel.replace(os.sep, ".").replace(".py", "")
                if mod:
                    modules.append(mod)
    return modules


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
