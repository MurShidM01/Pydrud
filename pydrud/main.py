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
from pydrud.core.results import Result
from pydrud.core.tasks import TaskRunner
from pydrud.core.diff import TreeDiff
from pydrud.core.events import EventDispatcher
from pydrud.core.bridge import BridgeProtocol
from pydrud.core.protocol import RenderTransaction, PROTOCOL_VERSION
from pydrud.core.elements import ElementTree
from pydrud.widgets import Widget, assign_stable_keys, validate_tree_keys

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
        #: Desired Python tree. Native confirmation advances _snapshot.
        self._desired_tree: Optional[Widget] = None
        #: Clone of the tree the native runtime has explicitly acknowledged.
        self._snapshot: Optional[Widget] = None
        self._elements = ElementTree()
        self._desired_revision = 0
        self._confirmed_revision = 0
        self._inflight: dict[str, RenderTransaction] = {}
        self._native_capabilities: dict = {}
        self._ui_thread_id: Optional[int] = None
        self._bridge = BridgeProtocol()
        self._connected = False
        self._transport: Optional[socket.socket] = None
        # ── Thread-safe event queue ─────────────────────────────────
        self._event_queue: queue.Queue = queue.Queue(maxsize=1024)
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
        """Rebuild and transact the desired tree.

        Python keeps desired, confirmed and in-flight UI state separate.  A
        native ACK is the only operation which advances the confirmed snapshot.
        """
        new = self._build_tree()
        self._desired_tree = new
        if not (self._connected and self._transport):
            return

        base_revision = self._confirmed_revision
        self._desired_revision = max(self._desired_revision, base_revision) + 1

        old = self._snapshot
        if old is None:
            tx = RenderTransaction.create(
                revision=self._desired_revision,
                base_revision=base_revision,
                kind="snapshot",
                payload={"tree": new.to_dict()},
            )
        else:
            try:
                patches = TreeDiff.diff(old, new)
            except Exception as exc:
                self._report_error(exc)
                tx = RenderTransaction.create(
                    revision=self._desired_revision,
                    base_revision=base_revision,
                    kind="snapshot",
                    payload={"tree": new.to_dict()},
                )
            else:
                if not patches:
                    return
                kind = "patch" if len(patches) <= MAX_PATCHES else "snapshot"
                payload = (
                    {"patches": [p.to_dict() for p in patches]}
                    if kind == "patch"
                    else {"tree": new.to_dict()}
                )
                tx = RenderTransaction.create(
                    revision=self._desired_revision,
                    base_revision=base_revision,
                    kind=kind,
                    payload=payload,
                )

        self._inflight[tx.tx_id] = tx
        self._send(self._bridge.encode_transaction(tx))

    def update_widget(self, *widgets: Widget) -> None:
        """Compatibility API: merge explicit widget mutations into the desired tree."""
        if not widgets:
            return self.update()
        if self._current_tree is None:
            return self.update()
        for widget in widgets:
            if not self._replace_widget_reference(self._current_tree, widget.key, widget):
                return self.update()
        self._desired_tree = self._current_tree
        self._render_pending = True if self._inflight else False
        if self._connected and self._transport and not self._inflight:
            self._send_desired_tree()
        return None

    def _replace_widget_reference(self, root: Widget, key: str, replacement: Widget) -> bool:
        for index, child in enumerate(root.children):
            if child.key == key:
                root.children[index] = replacement
                return True
            if self._replace_widget_reference(child, key, replacement):
                return True
        return False

    def render(self):
        """Force a full desired-state snapshot reconciliation."""
        tree = self._build_tree()
        self._desired_tree = tree
        if self._connected and self._transport:
            self._desired_revision = max(self._desired_revision, self._confirmed_revision) + 1
            tx = RenderTransaction.create(
                revision=self._desired_revision,
                base_revision=self._confirmed_revision,
                kind="snapshot",
                payload={"tree": tree.to_dict()},
            )
            self._inflight[tx.tx_id] = tx
            self._send(self._bridge.encode_transaction(tx))

    def update_state(self, state: State):
        """Rebuild after a State change."""
        self.update()

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
        self._connected = False

    # ── lifecycle & errors ────────────────────────────────────────────────

    def on_lifecycle(self, event: str, callback: Callable) -> "App":
        """Register a lifecycle callback (``resume``/``pause``/``stop``/``destroy``)."""
        self._lifecycle_handlers.setdefault(event, []).append(callback)
        return self

    def on_deep_link(self, callback: Callable[[str], None]) -> "App":
        """Handle ``myapp://`` / https links and launcher shortcuts.

        The callback receives the raw URL.  When a router is attached, the
        link is *also* resolved against its route table automatically.
        """
        self._deep_link_handlers.append(callback)
        if self._pending_deep_link is not None:
            link, self._pending_deep_link = self._pending_deep_link, None
            self._handle_deep_link({"url": link})
        return self

    def on_push(self, callback: Callable[[dict], None]) -> "App":
        """Handle an incoming FCM message (foreground or notification tap)."""
        self._push_handlers.append(callback)
        return self

    def _handle_deep_link(self, data: dict) -> None:
        url = data.get("url") or data.get("route") or ""
        if not url:
            return
        if not self._deep_link_handlers and self._router is None:
            self._pending_deep_link = url
            return
        for cb in list(self._deep_link_handlers):
            try:
                cb(url)
            except Exception as exc:
                self._report_error(exc)
        if self._router is not None and hasattr(self._router, "handle_link"):
            try:
                self._router.handle_link(url)
            except Exception as exc:
                self._report_error(exc)

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
        validate_tree_keys(tree)
        self._materialize_elements(tree)
        self._current_tree = tree
        self._desired_tree = tree
        self._event_dispatcher.unregister_all()
        self._event_dispatcher.register_tree(tree)
        return tree

    def _materialize_elements(self, tree: Widget) -> None:
        """Refresh persistent logical element metadata without touching Views."""
        def walk(widget: Widget, parent_key: Optional[str] = None, index: int = 0):
            props = widget._serialise_props()
            element, _ = self._elements.upsert(
                widget.key,
                widget._widget_type,
                parent_key=parent_key,
                index=index,
                desired_props=props,
            )
            element.listeners = set(widget.event_handlers)
            element.children = [child.key for child in widget.children]
            for i, child in enumerate(widget.children):
                walk(child, widget.key, i)
        walk(tree)

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

    # ── stateful hot reload ──────────────────────────────────────────────

    def capture_state(self) -> dict:
        """Snapshot every bound State/Store value before a reload."""
        snapshot: dict = {"states": [], "stores": [], "route": None,
                          "params": {}}
        for state in self._bound_states:
            try:
                snapshot["states"].append(
                    (getattr(state, "name", "") or "", state.value))
            except Exception:
                snapshot["states"].append(("", None))
        for store in self._bound_stores:
            try:
                snapshot["stores"].append(
                    dict(store.state) if hasattr(store, "state") else None)
            except Exception:
                snapshot["stores"].append(None)
        if self._router is not None:
            # Store the *pattern* (e.g. "/items/:id"), which is what the
            # rebuilt router will know about, plus the resolved params.
            snapshot["route"] = self._router.current_route
            snapshot["params"] = dict(self._router.current_params)
            snapshot["path"] = self._router.path()
        return snapshot

    def restore_state(self, snapshot: dict) -> None:
        """Push a snapshot back into the reloaded module's objects.

        Hot reload rebuilds module-level ``State`` objects, so values are
        matched positionally (and by name when one was given) — the same
        trade-off Flutter makes, and it keeps a counter or a half-typed form
        intact while you edit the screen around it.
        """
        states = snapshot.get("states") or []
        for index, state in enumerate(self._bound_states):
            if index >= len(states):
                break
            name, value = states[index]
            if name and getattr(state, "name", "") and name != state.name:
                continue
            try:
                state.value = value
            except Exception:
                pass
        stores = snapshot.get("stores") or []
        for index, store in enumerate(self._bound_stores):
            if index >= len(stores) or stores[index] is None:
                continue
            try:
                store.replace(stores[index])
            except AttributeError:
                try:
                    store.state.update(stores[index])
                except Exception:
                    pass
        route = snapshot.get("route")
        if not route or self._router is None:
            return
        try:
            if self._router.has_route(route):
                self._router.replace(route, **(snapshot.get("params") or {}))
            elif snapshot.get("path"):
                # The route pattern was renamed or removed; fall back to
                # resolving the concrete URL path again.
                self._router.go(snapshot["path"])
        except Exception:
            pass

    def preserve_state(self, enabled: bool = True) -> "App":
        """Keep State/Store values across hot reloads (default: on)."""
        self._preserve_state = bool(enabled)
        return self

    def _on_hot_reload(self, filepath: str) -> None:
        """Called by the file watcher when a source file changes."""
        snapshot = self.capture_state() if self._preserve_state else None
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
            if snapshot is not None:
                self.restore_state(snapshot)
            kept = len(snapshot["states"]) + len(snapshot["stores"]) \
                if snapshot else 0
            print(f"[Pydrud] Hot Reload: {os.path.basename(filepath)}"
                  + (f" (kept {kept} state object(s))" if kept else ""))
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

    # ── native service calls ──────────────────────────────────────────────

    def invoke(self, cmd: str, **data) -> Result:
        """Send a command that expects an answer and return a :class:`Result`.

        A ``request_id`` is attached so the Android side can correlate its
        reply.  When the bridge is not connected (tests, ``pydrud analyze``)
        the result fails immediately instead of hanging forever.
        """
        with self._lock:
            self._request_seq += 1
            request_id = f"r{self._request_seq}"
        result = Result(request_id, cmd)
        self._pending[request_id] = result
        if not self._connected:
            self._pending.pop(request_id, None)
            result.fail("bridge not connected")
            return result
        payload = {k: v for k, v in data.items() if v is not None}
        self._send(self._bridge.encode_command(cmd, request_id=request_id,
                                               **payload))
        return result

    def _resolve_result(self, data: dict) -> None:
        request_id = str(data.get("request_id", ""))
        result = self._pending.pop(request_id, None)
        if result is None:
            return
        if data.get("ok", True):
            result.complete(data.get("value"))
        else:
            result.fail(str(data.get("error", "native call failed")))

    def _cancel_pending(self, reason: str = "bridge closed") -> None:
        pending, self._pending = self._pending, {}
        for result in pending.values():
            result.fail(reason)

    # ── background work ───────────────────────────────────────────────────

    @property
    def tasks(self) -> TaskRunner:
        return self._tasks

    def run_task(self, fn: Callable, *args, **kwargs):
        """Run *fn* on a worker thread (also accepts ``async def``)."""
        return self._tasks.run(fn, *args, **kwargs)

    def run_on_ui(self, fn: Callable, *args, **kwargs) -> None:
        """Queue *fn* to run on the event-loop thread.

        Widget mutations from a worker thread must go through this, exactly
        like ``runOnUiThread`` on Android.
        """
        if self._ui_thread_id == threading.get_ident():
            try:
                fn(*args, **kwargs)
            except Exception as exc:
                self._report_error(exc)
            return
        if not self._running:
            fn(*args, **kwargs)
            return
        try:
            self._ui_queue.put_nowait((fn, args, kwargs))
            self._event_queue.put_nowait("__ui__")
        except queue.Full as exc:
            raise RuntimeError("Pydrud UI queue is full") from exc

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                fn, args, kwargs = self._ui_queue.get_nowait()
            except queue.Empty:
                return
            try:
                fn(*args, **kwargs)
            except Exception as exc:
                self._report_error(exc)

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

                # Push the palette first so the very first frame is drawn
                # with the app's colours (no white flash, no stock blue).
                self._send_theme()

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

    def _send_theme(self) -> None:
        """Hand the current palette to the native renderer.

        Native widgets (ripples, switches, inputs, the status bar) read
        their colours from ``PydrudTheme`` on the Java side; this keeps
        that in step with :class:`pydrud.widgets.theme.Theme`.
        """
        try:
            from pydrud.widgets.theme import Theme as _Theme

            payload = _Theme.payload()
        except Exception:  # pragma: no cover - defensive
            return
        self._send(json.dumps({"cmd": "theme", **payload}) + "\n")

    def apply_theme(self) -> None:
        """Re-send the palette and repaint after changing :class:`Theme`.

        ::

            Theme.dark()
            app.apply_theme()
        """
        self._send_theme()
        self.render()

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
        """Process incoming events on the single Python UI actor."""
        self._ui_thread_id = threading.get_ident()
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
            self._ui_thread_id = None
            self._connected = False
            self._cancel_pending()
            self._inflight.clear()
            if self._transport:
                try:
                    self._transport.close()
                except Exception:
                    pass

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
            for cb in list(self._push_handlers):
                try:
                    cb(dict(data))
                except Exception as exc:
                    self._report_error(exc)
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

    def _handle_render_confirmation(self, event_type: str, data: dict) -> None:
        tx_id = str(data.get("transaction_id", ""))
        tx = self._inflight.pop(tx_id, None)
        if tx is None:
            return
        revision = int(data.get("revision", 0) or 0)
        if revision != tx.revision:
            self._report_error(RuntimeError(
                f"Render confirmation mismatch for {tx_id}: "
                f"expected {tx.revision}, got {revision}"
            ))
            return
        if event_type == "render_ack":
            self._confirmed_revision = revision
            if self._desired_tree is not None:
                self._snapshot = self._desired_tree.clone()
            return

        self._confirmed_revision = int(data.get("native_revision", 0) or 0)
        if self._desired_tree is None or not (self._connected and self._transport):
            return
        self._desired_revision = max(self._desired_revision, self._confirmed_revision) + 1
        recovery = RenderTransaction.create(
            revision=self._desired_revision,
            base_revision=self._confirmed_revision,
            kind="snapshot",
            payload={"tree": self._desired_tree.to_dict()},
        )
        self._inflight[recovery.tx_id] = recovery
        self._send(self._bridge.encode_transaction(recovery))

    def _handle_ready(self, d: dict) -> None:
        """First contact: negotiate native capabilities, then render."""
        self._native_capabilities = dict(d.get("capabilities") or {})
        self._apply_metrics(d)
        # Device metrics may change the layout — re-render with real sizes.
        self.render()

    def _handle_metrics(self, d: dict) -> None:
        """The window changed (rotation, resize, insets, font scale).

        Only re-render when something actually moved, so a stream of
        identical inset callbacks does not thrash the view tree.
        """
        if not self._apply_metrics(d):
            return
        for cb in list(self._metrics_handlers):
            try:
                cb(_MQ_INFO())
            except Exception as exc:
                self._report_error(exc)
        self.render()

    def _apply_metrics(self, d: dict) -> bool:
        """Feed a ``ready``/``metrics`` payload into MediaQuery + Responsive."""
        from pydrud.core.responsive import MediaQuery as _MQ

        payload = {k: v for k, v in dict(d or {}).items() if v is not None}
        payload.setdefault("width", 360)
        payload.setdefault("height", 640)
        payload.setdefault("density", 2.0)
        try:
            return _MQ.update(**payload)
        except Exception as exc:
            self._report_error(exc)
            return False

    def on_metrics_change(self, callback):
        """Run *callback(ScreenInfo)* whenever the window size changes.

        ::

            @app.on_metrics_change
            def _(info):
                print(info.width, info.orientation, info.breakpoint)
        """
        if not callable(callback):
            raise TypeError("on_metrics_change() expects a callable")
        self._metrics_handlers.append(callback)
        return callback


def _MQ_INFO():
    from pydrud.core.responsive import MediaQuery as _MQ

    return _MQ.info()


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
        from pydrud.navigation import TRANSITIONS

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
        if mode in ("dark", "light"):
            # Repaint natively-styled widgets with the new palette.
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
