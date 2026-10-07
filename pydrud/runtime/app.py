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
from pydrud.core.styles import (
    RendererProfile,
    StyleSheet,
    StyleSheetManager,
)
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
from pydrud.runtime.page import _Page
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
        stylesheet: str | os.PathLike[str] | StyleSheet | None = None,
        stylesheets=None,
        renderer_profile: Optional[RendererProfile] = None,
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
        # ``None`` means no renderer has negotiated capabilities yet. An
        # empty mapping after handshake means optional services are absent.
        self._native_capabilities: Optional[dict] = None
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
        self._stylesheet_manager = StyleSheetManager(
            self._project_root, stylesheets=stylesheets)
        if stylesheet is not None:
            self._stylesheet_manager.add(stylesheet)
        #: Optional renderer facts are injected as data; the neutral core
        #: never selects or imports an Android renderer implicitly.
        self._renderer_profile = renderer_profile
        self._stylesheet_diagnostics: list = []
        self._stylesheet_warnings: list[str] = []
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

    @property
    def stylesheet(self) -> StyleSheet:
        """The current combined, last-known-good PSS stylesheet."""
        return self._stylesheet_manager.stylesheet

    @property
    def stylesheet_diagnostics(self) -> tuple:
        """Diagnostics from the most recent stylesheet load or reload."""
        return tuple(self._stylesheet_diagnostics)

    @property
    def stylesheet_warnings(self) -> tuple[str, ...]:
        """Renderer/profile warnings from the latest style resolution."""
        return tuple(self._stylesheet_warnings)

    def add_stylesheet(self, stylesheet) -> "App":
        """Register a PSS file path or parsed ``StyleSheet`` (chainable).

        Files under ``src/`` are discovered automatically; this method is
        useful for styles kept elsewhere or supplied programmatically.
        """
        self._stylesheet_manager.add(stylesheet)
        return self

    def add_stylesheet_source(
        self, source: str, *, filename: str = "<memory>"
    ) -> "App":
        """Parse and register in-memory PSS source, replacing the same name."""
        self._stylesheet_manager.add_source(source, filename=filename)
        return self

    def run(self, *, retry: bool = True, retry_delay: float = 0.5,
            max_retries: int = 30, use_platform_logging: bool = True):
        """Start the app on its configured local runtime bridge.

        Args:
            retry: Retry the TCP connection while the local renderer starts.
            retry_delay: Seconds between connection retries.
            max_retries: Maximum connection attempts before giving up.
            use_platform_logging: Install the Android log adapter for the
                direct Chaquopy bridge (disable for neutral test renderers).
        """
        # The direct local bridge is the Chaquopy target. Host preview uses
        # serve_transport and never installs a platform logging adapter.
        if use_platform_logging:
            from pydrud.platforms.android.logging import (
                install as install_android_logging,
            )
            install_android_logging()
        self._build_tree()

        if self._hot_reload_requested:
            self.enable_hot_reload()

        if self._dev_server_enabled and self._dev_server is None:
            self._start_dev_server()

        self._start_bridge(retry=retry, retry_delay=retry_delay, max_retries=max_retries)

    def _start_dev_server(self) -> None:
        """Start on-device DevServer for hot reload."""
        try:
            from pydrud.platforms.android.devserver import DevServer
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
        negotiated = dict(capabilities) if capabilities is not None else None
        if negotiated != self._native_capabilities:
            # A capability-driven placeholder can change a widget's wire type.
            # This transport sends a fresh authoritative snapshot, so reset the
            # per-renderer element type registry before rebuilding that tree.
            self._elements.clear()
        self._native_capabilities = negotiated
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


# ── Entry point for Chaquopy (called from Java) ──────────────────────────────


def start_app():
    """Entry point called by MainActivity after the bridge server is ready.

    Invoked from Java via::

        Python.getInstance().getModule("app.main").callAttr("start_app")
    """
    from app.main import main

    App(target=main).run()
