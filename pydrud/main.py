"""
Pydrud App — the top-level entry point.

An ``App`` owns the widget-tree, state, event dispatcher, and bridge.
It provides the familiar ``App(target=main).run()`` developer experience.
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
import traceback
from typing import Any, Callable, Optional

from pydrud.core.state import State
from pydrud.core.diff import TreeDiff
from pydrud.core.events import EventDispatcher
from pydrud.core.bridge import BridgeProtocol
from pydrud.widgets import Widget, assign_stable_keys

#: Above this many patches a full re-render is cheaper than patching.
MAX_PATCHES = 60


class App:
    """A Pydrud application.

    Typical usage::

        def main(page):
            page.add(Text("Hello, World!"))

        App(target=main).run()
    """

    def __init__(
        self,
        *,
        target: Optional[Callable] = None,
        title: str = "Pydrud App",
        host: str = "127.0.0.1",
        port: int = 8595,
        assets_dir: str = "assets",
        hot_reload: bool = False,
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
        self._hot_reload_requested = hot_reload
        # ── Lifecycle hooks ────────────────────────────────────────
        self._lifecycle_handlers: dict[str, list[Callable]] = {}
        self._error_handler: Optional[Callable[[BaseException], None]] = None

    # ── public API ────────────────────────────────────────────────────────

    @property
    def page(self) -> "_Page":
        return self._page

    @property
    def connected(self) -> bool:
        return self._connected

    def run(self, *, retry: bool = True, retry_delay: float = 0.5, max_retries: int = 30):
        """Start the app: build the tree, connect to Android, enter the event loop.

        Args:
            retry: Retry the TCP connection (the Android bridge server may
                not be listening yet when Chaquopy starts Python).
            retry_delay: Seconds between connection retries.
            max_retries: Maximum connection attempts before giving up.
        """
        self._build_tree()

        if self._hot_reload_requested:
            self.enable_hot_reload()

        self._start_bridge(retry=retry, retry_delay=retry_delay, max_retries=max_retries)

    def build(self) -> Widget:
        """Run the target and return the widget tree without connecting.

        Useful for tests and for ``pydrud analyze``.
        """
        return self._build_tree()

    def update(self):
        """Rebuild the widget tree and send incremental patches via TreeDiff.

        Falls back to a full render when there is no previous tree or when
        the patch list grows beyond :data:`MAX_PATCHES`.
        """
        old_tree = self._current_tree
        old_clone = old_tree.clone() if old_tree is not None else None

        new = self._build_tree()

        if not (self._connected and self._transport):
            return

        if old_clone is None:
            self._send(self._bridge.encode_full_render(new.to_dict()))
            return

        try:
            patches = TreeDiff.diff(old_clone, new)
        except Exception as exc:  # pragma: no cover — defensive
            self._report_error(exc)
            self._send(self._bridge.encode_full_render(new.to_dict()))
            return

        if not patches:
            return
        if len(patches) <= MAX_PATCHES:
            self._send(self._bridge.encode_render([p.to_dict() for p in patches]))
        else:
            self._send(self._bridge.encode_full_render(new.to_dict()))

    def render(self):
        """Force a full re-render (send the entire tree)."""
        tree = self._build_tree()
        if self._connected and self._transport:
            self._send(self._bridge.encode_full_render(tree.to_dict()))

    def update_state(self, state: State):
        """Rebuild after a State change."""
        self.update()

    def bind(self, *states: State) -> "App":
        """Auto-update the UI whenever any of *states* changes."""
        for state in states:
            state.watch(lambda _old, _new: self.update())
        return self

    def stop(self) -> None:
        """Shut the app down: stop the watcher, reader thread, and socket."""
        self._running = False
        self._shutdown_event.set()
        if self._watcher is not None:
            try:
                self._watcher.stop()
            except Exception:
                pass
            self._watcher = None
        self._event_queue.put(None)
        if self._transport is not None:
            try:
                self._transport.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self._transport.close()
            except Exception:
                pass
        self._connected = False

    # ── lifecycle & errors ────────────────────────────────────────────────

    def on_lifecycle(self, event: str, callback: Callable) -> "App":
        """Register a lifecycle callback (``resume``/``pause``/``stop``/``destroy``)."""
        self._lifecycle_handlers.setdefault(event, []).append(callback)
        return self

    def on_error(self, callback: Callable[[BaseException], None]) -> "App":
        """Register a handler called when an event callback raises."""
        self._error_handler = callback
        return self

    def _report_error(self, exc: BaseException) -> None:
        if self._error_handler is not None:
            try:
                self._error_handler(exc)
                return
            except Exception:
                pass
        print(f"[Pydrud] Error: {exc}")
        traceback.print_exc()

    # ── tree building ─────────────────────────────────────────────────────

    def _build_tree(self) -> Widget:
        """Run the target, build the page, stabilise keys, index handlers."""
        if self.target:
            self._page.clear()
            try:
                self.target(self._page)
            except Exception as exc:
                self._report_error(exc)
        tree = self._page.build()
        assign_stable_keys(tree, prefix="_page")
        self._current_tree = tree
        self._event_dispatcher.unregister_all()
        self._event_dispatcher.register_tree(tree)
        return tree

    # ── Hot Reload ─────────────────────────────────────────────────────────

    def enable_hot_reload(self, watch_dirs: list[str] | None = None) -> None:
        """Watch source files and rebuild the UI when they change.

        Args:
            watch_dirs: Directories to watch (relative to the project root).
                Defaults to ``["src"]``.
        """
        from pydrud.core.watcher import FileWatcher

        if self._watcher is not None:
            return
        names = watch_dirs or self._watch_dirs
        dirs = [
            d if os.path.isabs(d) else os.path.join(self._project_root, d)
            for d in names
        ]
        dirs = [d for d in dirs if os.path.isdir(d)]
        if not dirs:
            print(f"[Pydrud] Hot Reload: no directories to watch ({names})")
            return
        self._watcher = FileWatcher(dirs, self._on_hot_reload)
        self._watcher.start()
        print(f"[Pydrud] Hot Reload watching: {', '.join(dirs)}")

    def disable_hot_reload(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None

    def _on_hot_reload(self, filepath: str) -> None:
        """Called by the file watcher when a source file changes."""
        try:
            mod_name = _module_name_for(filepath, self._project_root)
            if mod_name and mod_name in sys.modules:
                module = importlib.reload(sys.modules[mod_name])
                # Re-bind the target if it came from the reloaded module.
                target_name = getattr(self.target, "__name__", None)
                target_mod = getattr(self.target, "__module__", None)
                if target_name and target_mod == mod_name:
                    new_target = getattr(module, target_name, None)
                    if callable(new_target):
                        self.target = new_target
            print(f"[Pydrud] Hot Reload: {os.path.basename(filepath)}")
            self.update()
        except Exception as exc:
            print(f"[Pydrud] Hot Reload error for {filepath}: {exc}")

    def hot_restart(self) -> None:
        """Reset all app state and re-render from scratch."""
        if self._router is not None:
            self._router.reset()

        self._event_dispatcher.unregister_all()
        self._current_tree = None

        for mod_name in _find_user_modules(self._project_root):
            if mod_name in sys.modules:
                try:
                    importlib.reload(sys.modules[mod_name])
                except Exception as exc:
                    print(f"[Pydrud] Hot Restart reload error {mod_name}: {exc}")

        self.render()

    @staticmethod
    def _find_root() -> str:
        """Walk up from cwd to find the project root (containing pydrud.yaml)."""
        current = os.getcwd()
        while True:
            if os.path.isfile(os.path.join(current, "pydrud.yaml")):
                return current
            parent = os.path.dirname(current)
            if parent == current:
                return os.getcwd()
            current = parent

    # ── Router support ────────────────────────────────────────────────────

    def attach_router(self, router) -> None:
        """Attach a Router so the hardware back button pops screens."""
        self._router = router
        router.attach(self)

    # ── bridge internals ──────────────────────────────────────────────────

    def _start_bridge(self, *, retry=True, retry_delay=0.5, max_retries=30):
        """Connect to the Android side via TCP and run the event loop."""
        self._running = True
        self._shutdown_event.clear()
        attempts = 0
        last_error: Optional[BaseException] = None

        while attempts < max_retries and self._running:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10.0)
                sock.connect((self.host, self.port))
                sock.settimeout(None)
                self._transport = sock
                self._connected = True

                # Send the full initial tree.
                if self._current_tree is None:
                    self._build_tree()
                self._send(self._bridge.encode_full_render(self._current_tree.to_dict()))

                self._reader_thread = threading.Thread(
                    target=self._reader_loop,
                    args=(sock,),
                    daemon=True,
                    name="pydrud-reader",
                )
                self._reader_thread.start()

                self._event_loop()
                return
            except (ConnectionRefusedError, socket.timeout, OSError) as exc:
                last_error = exc
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass
                self._transport = None
                self._connected = False
                if not retry:
                    break
                attempts += 1
                time.sleep(retry_delay)
            except Exception as exc:  # pragma: no cover — defensive
                last_error = exc
                self._report_error(exc)
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
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if decoded:
                        self._event_queue.put(decoded)
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            self._event_queue.put(None)  # Sentinel: stop the event loop.

    def _event_loop(self):
        """Process incoming events from the queue on the main thread."""
        try:
            while self._running:
                try:
                    raw = self._event_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if raw is None:
                    break
                self._handle_raw_event(raw)
        finally:
            self._connected = False
            if self._transport:
                try:
                    self._transport.close()
                except Exception:
                    pass

    def _handle_raw_event(self, raw: str) -> None:
        """Decode and route a single NDJSON event line."""
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict):
            return

        etype = event.get("type", "")
        data = event.get("data") or {}

        if etype == "ready":
            self._handle_ready(data)
            return

        if etype == "back":
            handled = False
            if self._router is not None:
                try:
                    handled = self._router.handle_back()
                except Exception as exc:
                    self._report_error(exc)
            self._send(
                self._bridge.encode_command("back_result", handled=bool(handled))
            )
            return

        if etype == "lifecycle":
            state = data.get("state", "")
            for cb in self._lifecycle_handlers.get(state, []):
                try:
                    cb(data)
                except Exception as exc:
                    self._report_error(exc)
            return

        try:
            self._event_dispatcher.dispatch(raw)
        except Exception as exc:
            self._report_error(exc)

    def _handle_ready(self, d: dict) -> None:
        from pydrud.core.responsive import MediaQuery as _MQ
        from pydrud.core.responsive import Responsive as _R

        width = d.get("width", 360)
        height = d.get("height", 640)
        density = d.get("density", 2.0)
        _R.init(width_dp=width, height_dp=height, density=density)
        _MQ.init(
            width_dp=width,
            height_dp=height,
            density=density,
            status_bar_height=d.get("status_bar_height", 24),
            text_scale=d.get("text_scale", 1.0),
            navigation_bar_height=d.get("navigation_bar_height", 0),
        )
        # Device metrics may change the layout — re-render with real sizes.
        self.render()


class _Page:
    """The mutable page object passed to the user's builder function."""

    def __init__(self, app: App):
        self._app = app
        self.controls: list[Widget] = []
        self.floating: list[Widget] = []  # Overlay widgets (e.g. FAB)
        self.title: str = app.title
        self.bgcolor: Optional[str] = None
        self.scroll: Optional[str] = None
        self.padding: Optional[Any] = None
        self._built = False

    # ── content ───────────────────────────────────────────────────────────

    def add(self, *controls: Widget) -> "_Page":
        for control in controls:
            if not isinstance(control, Widget):
                raise TypeError(
                    f"page.add() expects Widget instances, got {type(control).__name__}"
                )
            self.controls.append(control)
        return self

    def add_floating(self, widget: Widget) -> "_Page":
        """Add an overlay widget (rendered above the page content)."""
        if not isinstance(widget, Widget):
            raise TypeError("page.add_floating() expects a Widget")
        self.floating.append(widget)
        return self

    def clear(self) -> None:
        self.controls.clear()
        self.floating.clear()

    def remove(self, key: str) -> None:
        self.controls = [c for c in self.controls if c.key != key]
        self.floating = [c for c in self.floating if c.key != key]

    def find(self, key: str) -> Optional[Widget]:
        """Find a widget anywhere in the current page tree."""
        for control in self.controls + self.floating:
            found = control.find_by_key(key)
            if found is not None:
                return found
        return None

    # ── app commands ──────────────────────────────────────────────────────

    def update(self) -> None:
        self._app.update()

    def toast(self, message: str, *, long: bool = False) -> None:
        """Show an Android toast."""
        self._send("toast", message=str(message), long=bool(long))

    def snack_bar(self, message: str, *, action: str = "", long: bool = True) -> None:
        """Show a Material snackbar at the bottom of the screen."""
        self._send("snackbar", message=str(message), action=action, long=bool(long))

    def set_title(self, title: str) -> None:
        self.title = title
        self._send("set_title", title=title)

    def vibrate(self, duration_ms: int = 40) -> None:
        """Short haptic feedback (requires the VIBRATE permission)."""
        self._send("vibrate", duration=int(duration_ms))

    def close(self) -> None:
        """Finish the Android activity (closes the app)."""
        self._send("finish_activity")

    def set_system_ui(
        self,
        *,
        status_bar_color: str | None = None,
        icon_brightness: str | None = None,
        navigation_bar_color: str | None = None,
    ) -> None:
        """Set status/navigation bar colour and icon brightness.

        Args:
            status_bar_color: Hex colour string, e.g. ``"#FF1A73E8"``.
            icon_brightness: ``"light"`` (white icons) or ``"dark"``.
            navigation_bar_color: Hex colour for the nav bar.
        """
        if icon_brightness not in (None, "light", "dark"):
            raise ValueError("icon_brightness must be 'light' or 'dark'")
        extras: dict = {}
        if status_bar_color:
            extras["status_bar_color"] = status_bar_color
        if icon_brightness:
            extras["icon_brightness"] = icon_brightness
        if navigation_bar_color:
            extras["navigation_bar_color"] = navigation_bar_color
        self._send("set_system_ui", **extras)

    def _send(self, cmd: str, **data) -> None:
        self._app._send(self._app._bridge.encode_command(cmd, **data))

    # ── build ─────────────────────────────────────────────────────────────

    def build(self) -> Widget:
        from pydrud.widgets.layout import Column, Container, Stack
        from pydrud.widgets.styling import EdgeInsets

        style: dict = {"width": "match", "height": "match"}
        if self.bgcolor:
            style["bg"] = self.bgcolor
        if self.padding is not None:
            padding = (
                EdgeInsets.all(self.padding)
                if isinstance(self.padding, (int, float))
                else self.padding
            )
            style["padding"] = padding.to_dict()

        self._built = True

        content = Column(
            key="_page_content",
            expand=1,
            style={"width": "match", "height": "match", "scroll": bool(self.scroll)},
            children=list(self.controls),
        )

        # A Stack keeps floating widgets (FABs, overlays) above the content.
        return Stack(
            key="_page",
            style=style,
            expand=1,
            children=[content, *self.floating],
        )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _module_name_for(filepath: str, project_root: str) -> str:
    """Map ``<root>/src/app/main.py`` to the module name ``app.main``."""
    try:
        rel = os.path.relpath(os.path.abspath(filepath), os.path.abspath(project_root))
    except ValueError:  # pragma: no cover — different drives on Windows
        return ""
    if rel.startswith(".."):
        return ""
    # Sources live under src/, which is the import root on the device.
    rel = rel.replace(os.sep, "/")
    if rel.startswith("src/"):
        rel = rel[len("src/"):]
    rel = rel[:-3] if rel.endswith(".py") else rel
    parts = [p for p in rel.split("/") if p]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _find_user_modules(project_root: str) -> list[str]:
    """Find all importable module names under the project's src/ directory."""
    src_dir = os.path.join(project_root, "src")
    modules: list[str] = []
    if not os.path.isdir(src_dir):
        return modules
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "pydrud")]
        for fname in files:
            if fname.endswith(".py"):
                mod = _module_name_for(os.path.join(root, fname), project_root)
                if mod:
                    modules.append(mod)
    return modules


# ── Entry point for Chaquopy (called from Java) ──────────────────────────────


def start_app():
    """Entry point called by MainActivity after the bridge server is ready.

    Invoked from Java via::

        Python.getInstance().getModule("app.main").callAttr("start_app")
    """
    from app.main import main

    App(target=main).run()
