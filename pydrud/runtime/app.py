"""
Pydrud App — the top-level entry point.

An ``App`` owns the widget-tree, state, event dispatcher, and bridge.
It provides the familiar ``App(target=main).run()`` developer experience.
"""

from __future__ import annotations
import json
import os
import queue
import socket
import threading
from typing import Any, Callable, Optional

from pydrud.core.state import State
from pydrud.core.results import Result
from pydrud.core.tasks import TaskRunner
from pydrud.core.events import EventDispatcher
from pydrud.core.bridge import BridgeProtocol
from pydrud.core.protocol import MAX_FRAME_BYTES, RenderTransaction
from pydrud.core.elements import ElementTree
from pydrud.core.logcat import install as install_logcat
from pydrud.widgets import Widget

# ``App`` is composed from cohesive mixins so no single module owns the whole
# application. ``MAX_PATCHES``/``_MQ_INFO`` are re-exported here because
# ``pydrud.main`` and tests import them from this module.
from pydrud.runtime._render import (  # noqa: F401
    MAX_PATCHES,
    RenderMixin,
    _MQ_INFO,
)
from pydrud.runtime._bridge import BridgeMixin
from pydrud.runtime._hotreload import HotReloadMixin
from pydrud.runtime._lifecycle import LifecycleMixin

# Module-name helpers live in their own module so hot reload can use them
# without importing this one. Re-exported here for backwards compatibility
# (``pydrud.main`` does ``from pydrud.runtime.app import _module_name_for``).
from pydrud.runtime._modules import (  # noqa: F401
    _find_user_modules,
    _module_name_for,
    _module_name_from_path,
)


class App(RenderMixin, BridgeMixin, LifecycleMixin, HotReloadMixin):
    """A Pydrud application.

    Typical usage::

        def main(page):
            page.add(Text("Hello, World!"))

        App(target=main).run()
    """

    #: The most recently created :class:`App`. Screen code can reach the
    #: running app through :meth:`current` without threading it through
    #: every function. ``None`` before the first app is constructed.
    _active: "Optional[App]" = None

    @classmethod
    def current(cls) -> "Optional[App]":
        """The most recently created app, or ``None``."""
        return cls._active

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
        App._active = self
        self.target = target
        self.title = title
        self.host = host
        self.port = port
        self.assets_dir = assets_dir

        self._page = _Page(self)
        self._event_dispatcher = EventDispatcher(self._schedule_awaitable)
        self._current_tree: Optional[Widget] = None
        #: Desired Python tree. Native confirmation advances _snapshot.
        self._desired_tree: Optional[Widget] = None
        #: Clone of the tree the native runtime has explicitly acknowledged.
        self._snapshot: Optional[Widget] = None
        self._elements = ElementTree()
        self._desired_revision = 0
        self._confirmed_revision = 0
        self._inflight: dict[str, RenderTransaction] = {}
        self._inflight_trees: dict[str, Widget] = {}
        #: Remaining frames of a chunked snapshot, sent one ACK at a time.
        self._outbox: list[tuple[dict, str]] = []
        #: The full tree a chunked snapshot is rebuilding, applied on the
        #: final chunk's ACK.
        self._outbox_final_tree: Optional[Widget] = None
        self._render_pending = False
        self._render_pending_force_snapshot = False
        self._native_capabilities: dict = {}
        self._ui_thread_id: Optional[int] = None
        self._bridge = BridgeProtocol()
        self._connected = False
        self._transport: Optional[socket.socket] = None
        # ── Thread-safe event queue ─────────────────────────────────
        self._event_queue: queue.Queue = queue.Queue(maxsize=1024)
        #: Number of event lines fully handled by the event loop. Test
        #: harnesses use it to tell "nothing queued yet" from "all done".
        self._events_handled = 0
        self._shutdown_event = threading.Event()
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        # ── Router support ─────────────────────────────────────────
        self._router: Optional[Any] = None
        self._metrics_handlers: list = []
        # ── Hot Reload ─────────────────────────────────────────────
        self._watcher: Optional[Any] = None
        self._watch_dirs: list[str] = ["src"]
        self._project_root: str = self._find_root()
        self._hot_reload_requested = hot_reload
        # ── Lifecycle hooks ────────────────────────────────────────
        self._lifecycle_handlers: dict[str, list[Callable]] = {}
        #: Deep links / shortcuts / push messages / sensor streams.
        self._deep_link_handlers: list[Callable] = []
        self._push_handlers: list[Callable] = []
        #: FCM registration-token refreshes and audio playback completions.
        self._push_token_handlers: list[Callable] = []
        self._audio_complete_handlers: list[Callable] = []
        #: Streaming native events: GPS fixes, BLE notifications, recordings.
        self._location_handlers: list[Callable] = []
        self._bluetooth_handlers: list[Callable] = []
        self._recording_handlers: list[Callable] = []
        self._pending_deep_link: Optional[str] = None
        #: Bound reactive objects — also used to carry values across reloads.
        self._bound_states: list = []
        self._bound_stores: list = []
        self._subscriptions: list = []
        self._preserve_state: bool = True
        self._error_handler: Optional[Callable[[BaseException], None]] = None
        # ── Native service calls (request/response) ────────────────
        self._pending: dict[str, Result] = {}
        self._request_seq = 0
        self._tasks = TaskRunner(on_error=self._report_error)
        # ── UI-thread marshalling ──────────────────────────────────
        self._ui_queue: queue.Queue = queue.Queue(maxsize=1024)
        # ── DevServer (Hot reload & diagnostics) ───────────────────
        self._dev_port = kwargs.get("dev_port", 8596)
        self._dev_server_enabled = kwargs.get("dev_server", True)
        self._dev_server: Optional[Any] = None

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
        # Route Python output to logcat under the stable `Pydrud` tag before
        # anything else can fail (DX-004). No-op on the host.
        install_logcat()
        self._build_tree()

        if self._hot_reload_requested:
            self.enable_hot_reload()

        if self._dev_server_enabled and self._dev_server is None:
            self._start_dev_server()

        self._start_bridge(retry=retry, retry_delay=retry_delay, max_retries=max_retries)

    def _start_dev_server(self) -> None:
        """Start on-device DevServer for hot reload."""
        try:
            from pydrud.core.devserver import DevServer
            self._dev_server = DevServer(self, host=self.host, port=self._dev_port)
            self._dev_server.start()
        except Exception:
            pass

    def build(self) -> Widget:
        """Run the target and return the widget tree without connecting.

        Useful for tests and for ``pydrud analyze``.
        """
        return self._build_tree()

    def serve_transport(
        self,
        transport: socket.socket,
        *,
        capabilities: Optional[dict] = None,
        metrics: Optional[dict] = None,
        native_revision: int = 0,
    ) -> None:
        """Serve one authenticated, connected renderer until it disconnects."""
        if self._connected:
            raise RuntimeError("a renderer transport is already connected")
        # Finish any callback queued just behind the previous disconnect, then
        # discard that reader's consumed-loop sentinel before reconnect.
        self._drain_ui_queue()
        while True:
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                break

        self._running = self._connected = True
        self._shutdown_event.clear()
        self._transport = transport
        self._native_capabilities = dict(capabilities or {})
        self._confirmed_revision = max(0, int(native_revision))
        self._desired_revision = max(self._desired_revision,
                                     self._confirmed_revision)
        self._snapshot = None
        self._inflight.clear()
        self._inflight_trees.clear()
        self._outbox.clear()
        self._outbox_final_tree = None
        self._render_pending = self._render_pending_force_snapshot = False

        try:
            if metrics:
                self._apply_metrics(dict(metrics))
            self._desired_tree = self._build_tree()
            self._send_theme()
            self._request_system_theme()
            self._send_desired_tree(force_snapshot=True)
            self._reader_thread = threading.Thread(
                target=self._reader_loop, args=(transport,), daemon=True,
                name="pydrud-preview-reader")
            self._reader_thread.start()
            self._event_loop()
        finally:
            # Between clients there is no UI actor; watcher callbacks rebuild
            # directly and the next connection receives that desired tree.
            self._running = self._connected = False
            if self._transport is transport:
                try:
                    transport.close()
                except OSError:
                    pass
                self._transport = None


    @staticmethod
    def _plan_snapshot_frames(tree: dict) -> list[tuple[dict, str]]:
        """Split a serialised tree into frames that each fit the limit.

        Returns ``[(payload, kind), ...]`` where the first entry is a shallow
        ``snapshot`` and the rest are ``patch`` frames of ``create`` ops.
        Children are included breadth-first while they fit; anything left out
        is materialised later, parents before children, so the native node
        map stays consistent. A tree that already fits yields a single
        snapshot frame, so the common case is unchanged.
        """
        limit = MAX_FRAME_BYTES
        # Leave headroom for the transaction envelope and JSON punctuation.
        budget = max(4096, int(limit * 0.75))

        def shallow(node: dict) -> dict:
            out = {k: v for k, v in node.items() if k != "children"}
            out["children"] = []
            return out

        def size(value) -> int:
            try:
                return len(json.dumps(value, separators=(",", ":"), default=str))
            except Exception:
                return limit  # treat unserialisable as "too big" — defer it

        root_shallow = shallow(tree)
        frame_size = size(root_shallow)
        deferred: list[tuple[str, int, dict]] = []
        queue = [(tree, root_shallow)]
        while queue:
            src, dst = queue.pop(0)
            for index, child in enumerate(src.get("children") or []):
                child_size = size(child)
                if frame_size + child_size <= budget:
                    child_shallow = shallow(child)
                    dst["children"].append(child_shallow)
                    frame_size += child_size
                    queue.append((child, child_shallow))
                else:
                    deferred.append((src.get("key", ""), index, child))

        frames: list[tuple[dict, str]] = [({"tree": root_shallow}, "snapshot")]

        # Stream the omitted subtrees as create patches, parents first.
        patch: list[dict] = []
        patch_size = 0
        work = list(deferred)
        while work:
            parent_key, index, child = work.pop(0)
            child_shallow = shallow(child)
            entry = {"op": "create", "key": child.get("key", ""),
                     "parent_key": parent_key, "index": index,
                     "tree": child_shallow}
            entry_size = size(entry)
            if patch and patch_size + entry_size > budget:
                frames.append(({"patches": patch}, "patch"))
                patch, patch_size = [], 0
            patch.append(entry)
            patch_size += entry_size
            for grand_index, grand in enumerate(child.get("children") or []):
                work.append((child.get("key", ""), grand_index, grand))
        if patch:
            frames.append(({"patches": patch}, "patch"))
        return frames


    def bind(self, *states) -> "App":
        """Auto-update the UI whenever any bound object changes.

        Accepts :class:`~pydrud.core.state.State` values as well as anything
        observable (``Store``, ``ReactiveList``, ``Computed``) — i.e. objects
        exposing ``watch()`` or ``subscribe()``.
        """
        for state in states:
            if isinstance(state, State):
                self._bound_states.append(state)
                self._subscriptions.append(state.watch(lambda _old, _new: self.update(), scheduler=self.run_on_ui))
            elif hasattr(state, "subscribe"):
                self._bound_stores.append(state)
                self._subscriptions.append(state.subscribe(lambda *_args, **_kw: self.update()))
            else:
                raise TypeError(
                    f"App.bind() expects State or an observable store, "
                    f"got {type(state).__name__}")
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
        self._cancel_pending("app stopped")
        for subscription in list(self._subscriptions):
            try:
                subscription.cancel()
            except Exception:
                pass
        self._subscriptions.clear()
        try:
            self._tasks.shutdown()
        except Exception:
            pass
        if self._transport is not None:
            try:
                self._transport.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self._transport.close()
            except Exception:
                pass
        if self._dev_server is not None:
            try:
                self._dev_server.stop()
            except Exception:
                pass
            self._dev_server = None
        self._connected = False


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

    @property
    def router(self):
        """The navigation Router attached to this App, or None."""
        return getattr(self, "_router", None)

    @router.setter
    def router(self, router) -> None:
        self.attach_router(router)

    def attach_router(self, router) -> None:
        """Attach a Router so the hardware back button pops screens."""
        self._router = router
        router.attach(self)


    def _handle_raw_event(self, raw: str) -> None:
        """Decode and route a single NDJSON event line."""
        if raw == "__ui__":
            self._drain_ui_queue()
            return
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict):
            return

        etype = event.get("type", "")
        data = event.get("data") or {}

        if etype == "result":
            self._resolve_result(data)
            return

        if etype in ("render_ack", "render_nack"):
            self._handle_render_confirmation(etype, data)
            return

        if etype == "ready":
            self._handle_ready(data)
            return

        if etype == "metrics":
            # The window changed: rotation, split screen, foldable unfold,
            # font-scale change, keyboard, new insets.
            self._handle_metrics(data)
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

        if etype == "deep_link":
            self._handle_deep_link(data)
            return

        if etype == "push":
            self._dispatch(self._push_handlers, dict(data))
            return

        if etype == "push_token":
            self._dispatch(self._push_token_handlers,
                           str(data.get("token", "")))
            return

        if etype == "audio_complete":
            self._dispatch(self._audio_complete_handlers, dict(data))
            return

        if etype == "location":
            self._dispatch(self._location_handlers, dict(data))
            return

        if etype == "bluetooth":
            self._dispatch(self._bluetooth_handlers, dict(data))
            return

        if etype == "recording":
            self._dispatch(self._recording_handlers, dict(data))
            return

        if etype == "protocol_error":
            # The native renderer rejected a message: a malformed patch, an
            # unknown op, a version mismatch.  Silence here meant the UI
            # quietly stopped updating, so surface it like any other error.
            message = str(data.get("message", "")) or "native protocol error"
            code = data.get("code")
            self._report_error(RuntimeError(
                f"native protocol error [{code}]: {message}"
                if code is not None else f"native protocol error: {message}"))
            return

        if etype == "sensor":
            try:
                self._page.sensors.dispatch(dict(data))
            except Exception as exc:
                self._report_error(exc)
            return

        if etype == "job":
            # WorkManager asking Python to run a registered background job.
            name = data.get("name", "")
            try:
                value = self._page.background.run_job(name, data.get("inputs"))
                ok, payload = True, value
            except Exception as exc:
                self._report_error(exc)
                ok, payload = False, str(exc)
            self._send(self._bridge.encode_command(
                "job_result", name=name, ok=ok,
                value=payload if ok else None,
                error=None if ok else payload))
            return

        if etype == "snackbar":
            try:
                self._page._dispatch_snackbar(dict(data))
            except Exception as exc:
                self._report_error(exc)
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
        self.theme_mode: str = "light"
        self._services: Optional[Any] = None
        self._http: Optional[Any] = None
        self._cache: Optional[Any] = None
        self._databases: dict = {}
        self._app_dir: Optional[str] = None
        self._overlays: dict[str, Widget] = {}
        self._snack_callbacks: dict[str, tuple] = {}
        self._snack_seq: int = 0

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

    # ── native services ───────────────────────────────────────────────────

    @property
    def services(self):
        """All native services (dialogs, storage, permissions, …)."""
        if self._services is None:
            from pydrud.services.native import Services

            self._services = Services(self._app.invoke)
        return self._services

    @property
    def dialog(self):
        """Alerts, confirms, prompts, sheets and pickers."""
        return self.services.dialog

    @property
    def storage(self):
        """Persistent key/value storage (SharedPreferences)."""
        return self.services.storage

    @property
    def clipboard(self):
        return self.services.clipboard

    @property
    def share(self):
        return self.services.share

    @property
    def permissions(self):
        return self.services.permissions

    @property
    def notifications(self):
        return self.services.notifications

    @property
    def location(self):
        return self.services.location

    @property
    def device(self):
        return self.services.device

    @property
    def files(self):
        return self.services.files

    @property
    def haptics(self):
        return self.services.haptics

    @property
    def secure(self):
        """Keystore-backed encrypted key/value storage."""
        return self.services.secure

    @property
    def background(self):
        """WorkManager jobs and foreground services."""
        return self.services.background

    @property
    def push(self):
        """Firebase Cloud Messaging tokens and topics."""
        return self.services.push

    @property
    def shortcuts(self):
        """Launcher shortcuts and home-screen widgets."""
        return self.services.shortcuts

    @property
    def camera(self):
        """Live camera control (pairs with the CameraPreview widget)."""
        return self.services.camera

    @property
    def sensors(self):
        """Accelerometer, gyroscope, light, proximity, step counter, …"""
        return self.services.sensors

    @property
    def bluetooth(self):
        """Bluetooth Low Energy scanning and GATT access."""
        return self.services.bluetooth

    @property
    def nfc(self):
        """NFC tag reading and NDEF writing."""
        return self.services.nfc

    @property
    def biometrics(self):
        """Fingerprint / face authentication."""
        return self.services.biometrics

    @property
    def audio(self):
        """Recording, playback, text-to-speech and speech-to-text."""
        return self.services.audio

    def database(self, name: str = "app.db", **kwargs):
        """Open (once) a SQLite database inside the app's private storage.

        ``page.database()`` works on the device *and* on a laptop: when there
        is no bridge, the file lands in ``.pydrud/`` next to the project.
        """
        from pydrud.data.database import Database

        if name in self._databases:
            return self._databases[name]
        path = name if os.path.isabs(name) else os.path.join(
            self._storage_dir("databases"), name)
        database = Database(path, **kwargs)
        self._databases[name] = database
        return database

    @property
    def cache(self):
        """A persistent TTL + LRU cache in the app's cache directory."""
        if self._cache is None:
            from pydrud.data.cache import Cache

            self._cache = Cache(self._storage_dir("cache"))
        return self._cache

    def _storage_dir(self, kind: str) -> str:
        """Resolve a writable directory, on-device or on a dev machine."""
        base = self._app_dir
        if base is None:
            base = os.environ.get("PYDRUD_APP_DIR") or os.path.join(
                getattr(self._app, "_project_root", ".") or ".", ".pydrud")
            self._app_dir = base
        path = os.path.join(base, kind)
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def http(self):
        """A non-blocking HTTP client bound to this page's task runner."""
        if self._http is None:
            from pydrud.services.http import Http

            self._http = Http(self._app.run_task)
        return self._http

    @property
    def router(self):
        """The navigation router for this page/app."""
        if getattr(self._app, "_router", None) is not None:
            return self._app._router
        if getattr(self._app, "router", None) is not None:
            return self._app.router
        return None

    def invoke(self, cmd: str, **data):
        """Low-level escape hatch: call any native command and await a Result."""
        return self._app.invoke(cmd, **data)

    # ── concurrency ───────────────────────────────────────────────────────

    def run_task(self, fn: Callable, *args, **kwargs):
        """Run slow work off the UI thread (``async def`` is supported)."""
        return self._app.run_task(fn, *args, **kwargs)

    def run_on_ui(self, fn: Callable, *args, **kwargs) -> None:
        """Hop back onto the UI thread before touching widgets."""
        self._app.run_on_ui(fn, *args, **kwargs)

    def after(self, delay: float, fn: Callable, *args, **kwargs):
        """Run *fn* once after *delay* seconds."""
        return self._app.tasks.after(delay, fn, *args, **kwargs)

    def every(self, interval: float, fn: Callable, *args, **kwargs):
        """Run *fn* every *interval* seconds until the timer is cancelled."""
        return self._app.tasks.every(interval, fn, *args, **kwargs)

    # ── app commands ──────────────────────────────────────────────────────

    def update(self, *controls: Widget) -> None:
        """Refresh the UI.

        ``page.update()`` re-runs your builder and diffs the whole page;
        ``page.update(widget)`` pushes just that widget's subtree, which is
        what you want after mutating a control you kept a reference to.
        """
        if controls:
            self._app.update_widget(*controls)
        else:
            self._app.update()

    def toast(self, message: str, *, long: bool = False) -> None:
        """Show an Android toast."""
        self._send("toast", message=str(message), long=bool(long))

    def snack_bar(
        self,
        message: str,
        *,
        action: str = "",
        on_action: Callable[[], Any] | None = None,
        on_dismiss: Callable[[], Any] | None = None,
        long: bool = True,
    ) -> None:
        """Show a Material snackbar at the bottom of the screen.

        The action button actually calls back into Python::

            page.snack_bar("Counter reset", action="Undo",
                           on_action=lambda: restore())

        Args:
            message: The text to show.
            action: Label of the action button (omit for no button).
            on_action: Called when the action button is tapped.
            on_dismiss: Called when the snackbar goes away untouched.
            long: Longer display duration.
        """
        callback_id = ""
        if on_action is not None or on_dismiss is not None:
            self._snack_seq += 1
            callback_id = f"snack{self._snack_seq}"
            self._snack_callbacks[callback_id] = (on_action, on_dismiss)
        self._send("snackbar", message=str(message), action=action,
                   long=bool(long), callback_id=callback_id)

    def _dispatch_snackbar(self, data: dict) -> None:
        """Route a ``snackbar`` event from Android back to the callback."""
        entry = self._snack_callbacks.pop(data.get("callback_id", ""), None)
        if entry is None:
            return
        on_action, on_dismiss = entry
        callback = on_action if data.get("action") else on_dismiss
        if callback is not None:
            callback()

    def set_title(self, title: str) -> None:
        self.title = title
        self._send("set_title", title=title)

    def vibrate(self, duration_ms: int = 40) -> None:
        """Short haptic feedback (enable the ``haptics`` capability)."""
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

    # ── UI commands ───────────────────────────────────────────────────────

    def open_drawer(self, side: str = "start") -> None:
        """Open the navigation drawer declared on the Scaffold."""
        if side not in ("start", "end"):
            raise ValueError("side must be 'start' or 'end'")
        self._send("drawer", open=True, side=side)

    def close_drawer(self, side: str = "start") -> None:
        self._send("drawer", open=False, side=side)

    def end_refresh(self) -> None:
        """Stop the pull-to-refresh spinner."""
        self._send("end_refresh")

    def scroll_to(self, key: str, *, animate: bool = True) -> None:
        """Scroll the nearest scrollable ancestor to the widget *key*."""
        self._send("scroll_to", key=str(key), animate=bool(animate))

    def focus(self, key: str, *, keyboard: bool = True) -> None:
        """Move focus to an input and optionally raise the soft keyboard."""
        self._send("focus", key=str(key), keyboard=bool(keyboard))

    def hide_keyboard(self) -> None:
        self._send("keyboard", show=False)

    def show_keyboard(self) -> None:
        self._send("keyboard", show=True)

    def keep_awake(self, enabled: bool = True) -> None:
        """Keep the screen on (video players, recipes, navigation)."""
        self._send("keep_awake", enabled=bool(enabled))

    def set_orientation(self, orientation: str) -> None:
        """Lock the orientation: ``portrait``, ``landscape`` or ``auto``."""
        if orientation not in ("portrait", "landscape", "auto"):
            raise ValueError("orientation must be portrait/landscape/auto")
        self._send("orientation", value=orientation)

    def fullscreen(self, enabled: bool = True) -> None:
        """Immersive mode: hide the status and navigation bars."""
        self._send("fullscreen", enabled=bool(enabled))

    def route_transition(self, transition: str = "fade",
                         *, duration: int = 220) -> None:
        """Animate the *next* screen swap (used by Router transitions)."""
        from pydrud.runtime.navigation import TRANSITIONS

        if transition not in TRANSITIONS:
            raise ValueError(f"transition must be one of {TRANSITIONS}")
        self._send("route_transition", transition=transition,
                   duration=int(duration))

    def animation(self, duration: float = 0.3, *, curve: str = "ease_in_out",
                  fps: int = 60):
        """Create an :class:`AnimationController` driven by this page.

        Ticks run on the task runner and listeners are marshalled back onto
        the UI thread, so a listener may safely mutate widgets.
        """
        from pydrud.core.controllers import AnimationController

        return AnimationController(duration, curve=curve, fps=fps,
                                   runner=self._app.tasks,
                                   on_ui=self._app.run_on_ui)

    def set_theme_mode(self, mode: str) -> None:
        """Switch between ``"light"``, ``"dark"`` and ``"system"``."""
        if mode not in ("light", "dark", "system"):
            raise ValueError("theme mode must be light/dark/system")
        from pydrud.widgets.theme import Theme

        self.theme_mode = mode
        if mode == "dark":
            Theme.dark()
        elif mode == "light":
            Theme.light()
        self._send("theme_mode", mode=mode)
        # Repaint natively-styled widgets *and* rebuild the tree, so colours
        # resolved in Python (Colors.TEXT, Theme.surface, …) change with the
        # same call instead of waiting for the next unrelated refresh.
        self._app.apply_theme()

    def set_theme(self, seed: str, *, dark: Optional[bool] = None) -> None:
        """Rebuild the palette from a brand colour and repaint.

        ::

            page.set_theme(Colors.TEAL)
            page.set_theme("#FFEF4444", dark=True)
        """
        from pydrud.widgets.theme import Theme

        if dark is not None:
            self.theme_mode = "dark" if dark else "light"
            Theme.dark_mode = bool(dark)
        Theme.seed(seed)
        self._app.apply_theme()

    def configure(self, **values) -> None:
        """Restyle the running app from Python — colours *and* metrics.

        Accepts any colour role or design token and repaints immediately::

            page.configure(primary="#FF0EA5E9")        # brand colour
            page.configure(radius_card=24, font_scale=1.1)
            page.configure(app_bar_height=64, nav_height=72)

        See :class:`pydrud.Tokens` for the full list.
        """
        from pydrud.widgets.theme import Theme

        Theme.configure(**values)
        self._app.apply_theme()

    def _send(self, cmd: str, **data) -> None:
        self._app._send(self._app._bridge.encode_command(cmd, **data))

    # ── build ─────────────────────────────────────────────────────────────

    def build(self) -> Widget:
        from pydrud.widgets.layout import Column, Stack
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


# ── Entry point for Chaquopy (called from Java) ──────────────────────────────


def start_app():
    """Entry point called by MainActivity after the bridge server is ready.

    Invoked from Java via::

        Python.getInstance().getModule("app.main").callAttr("start_app")
    """
    from app.main import main

    App(target=main).run()
