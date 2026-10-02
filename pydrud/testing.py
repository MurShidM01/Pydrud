"""
A fake Android device for end-to-end testing of the Pydrud bridge.

``FakeDevice`` speaks exactly the protocol the Java ``BridgeService`` /
``ViewFactory`` implement:

* it listens on 127.0.0.1 and accepts the Python app's connection;
* it sends a ``ready`` event with screen metrics, and ``rotate()`` /
  ``resize()`` / ``show_keyboard()`` replay the ``metrics`` events a real
  device sends when the window changes;
* it applies ``full_render`` and ``render`` (patch) commands to an in-memory
  mirror of the native view tree, using the same semantics as
  ``ViewFactory.applyPatch``;
* it can push ``click`` / ``change`` / ``back`` / ``lifecycle`` events back
  into the app and records every command it received.

That makes it possible to run a complete Pydrud app in CI and assert on what
the device would actually display.

It is part of the public API — test your own app with::

    from pydrud.testing import AppTester

    def test_counter():
        with AppTester(main) as app:
            app.tap("increment")
            assert app.shows("Count: 1")
"""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any, Optional


class RenderedNode:
    """A mirror of a native View created from a widget JSON node."""

    def __init__(self, data: dict):
        self.key: str = data.get("key", "")
        self.type: str = data.get("type", "")
        self.style: dict = dict(data.get("style") or {})
        self.props: dict = dict(data.get("props") or {})
        self.events: list[str] = list(data.get("events") or [])
        self.visible: bool = data.get("visible", True)
        self.children: list["RenderedNode"] = [
            RenderedNode(c) for c in (data.get("children") or [])
        ]
        self.parent: Optional["RenderedNode"] = None
        for child in self.children:
            child.parent = self

    # ── queries ───────────────────────────────────────────────────────────

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def find(self, key: str) -> Optional["RenderedNode"]:
        for node in self.walk():
            if node.key == key:
                return node
        return None

    def find_by_type(self, type_name: str) -> list["RenderedNode"]:
        return [n for n in self.walk() if n.type == type_name]

    def texts(self) -> list[str]:
        """Every string shown on screen, in render order."""
        out = []
        for node in self.walk():
            for field in ("value", "text", "label", "hint"):
                v = node.props.get(field)
                if isinstance(v, str) and v:
                    out.append(v)
        return out

    def __repr__(self) -> str:
        return f"<{self.type} {self.key!r} children={len(self.children)}>"


class FakeDevice:
    """A test double for the Android side of the bridge."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0,
                 width: int = 400, height: int = 800, density: float = 2.0):
        self.host = host
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((host, port))
        self._server.listen(1)
        self.port = self._server.getsockname()[1]

        self.width = width
        self.height = height
        self.density = density

        self.root: Optional[RenderedNode] = None
        self.commands: list[dict] = []
        self.patch_batches: list[list[dict]] = []
        self.full_renders = 0

        self._conn: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._connected = threading.Event()
        self._activity_finished = False
        #: Canned answers for native service calls: {cmd: value|callable}.
        self.responders: dict[str, Any] = {}
        self.requests: list[dict] = []

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> "FakeDevice":
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True,
                                        name="fake-device")
        self._thread.start()
        return self

    def stop(self) -> None:
        self._running = False
        for sock in (self._conn, self._server):
            try:
                if sock:
                    sock.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)

    def __enter__(self) -> "FakeDevice":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # ── server loop ───────────────────────────────────────────────────────

    def _serve(self) -> None:
        try:
            conn, _addr = self._server.accept()
        except OSError:
            return
        self._conn = conn
        self._connected.set()
        self.send_ready()

        buffer = b""
        try:
            while self._running:
                data = conn.recv(65536)
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    text = line.decode("utf-8").strip()
                    if text:
                        self._handle(text)
        except OSError:
            pass

    def _handle(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        with self._lock:
            self.commands.append(msg)
            cmd = msg.get("cmd", "")
            if cmd == "full_render":
                self.root = RenderedNode(msg["tree"])
                self.full_renders += 1
            elif cmd == "render":
                patches = msg.get("patches", [])
                self.patch_batches.append(patches)
                for patch in patches:
                    self._apply_patch(patch)
            elif cmd == "finish_activity":
                self._activity_finished = True
            request_id = msg.get("request_id")
        if request_id:
            self.requests.append(msg)
            self._auto_respond(msg, request_id)

    # ── native service emulation ─────────────────────────────────────────

    def on_command(self, cmd: str, value: Any) -> "FakeDevice":
        """Answer ``cmd`` with *value* (or ``value(msg)`` when callable)."""
        self.responders[cmd] = value
        return self

    def _auto_respond(self, msg: dict, request_id: str) -> None:
        cmd = msg.get("cmd", "")
        if cmd not in self.responders:
            return
        answer = self.responders[cmd]
        try:
            value = answer(msg) if callable(answer) else answer
        except Exception as exc:  # pragma: no cover - responder bug
            self.respond_error(request_id, str(exc))
            return
        self.respond(request_id, value)

    def respond(self, request_id: str, value: Any = None) -> None:
        """Deliver a successful answer for a pending native call."""
        self.send_event("result", "", {"request_id": request_id, "ok": True,
                                       "value": value})

    def respond_error(self, request_id: str, error: str) -> None:
        self.send_event("result", "", {"request_id": request_id, "ok": False,
                                       "error": error})

    def last_request(self, cmd: str) -> Optional[dict]:
        for msg in reversed(self.requests):
            if msg.get("cmd") == cmd:
                return msg
        return None

    # ── patch application (mirrors ViewFactory.applyPatch) ────────────────

    def _apply_patch(self, patch: dict) -> None:
        if self.root is None:
            return
        op = patch.get("op")
        key = patch.get("key", "")
        parent_key = patch.get("parent_key", "")
        index = patch.get("index", -1)

        if op == "create":
            parent = self.root.find(parent_key)
            if parent is None:
                return
            node = RenderedNode(patch["tree"])
            node.parent = parent
            at = len(parent.children) if index is None or index < 0 else min(index, len(parent.children))
            parent.children.insert(at, node)

        elif op == "update":
            node = self.root.find(key)
            if node is None:
                return
            for name, value in (patch.get("props") or {}).items():
                if name == "_visible":
                    node.visible = bool(value)
                elif name == "_events":
                    node.events = list(value or [])
                elif not name.startswith("_"):
                    node.props[name] = value
            for name, value in (patch.get("style") or {}).items():
                if value is None:
                    node.style.pop(name, None)
                else:
                    node.style[name] = value

        elif op == "delete":
            node = self.root.find(key)
            if node is not None and node.parent is not None:
                node.parent.children.remove(node)

        elif op == "move":
            node = self.root.find(key)
            if node is None or node.parent is None or index is None or index < 0:
                return
            parent = node.parent
            parent.children.remove(node)
            parent.children.insert(min(index, len(parent.children)), node)

        elif op == "replace":
            node = self.root.find(key)
            parent = node.parent if node is not None else self.root.find(parent_key)
            new_node = RenderedNode(patch["tree"])
            if node is not None and parent is not None:
                at = parent.children.index(node)
                parent.children[at] = new_node
                new_node.parent = parent
            elif parent is not None:
                parent.children.append(new_node)
                new_node.parent = parent

    # ── outgoing events ───────────────────────────────────────────────────

    def _send(self, payload: dict) -> None:
        if self._conn is None:
            raise RuntimeError("FakeDevice: no app connected")
        self._conn.sendall((json.dumps(payload) + "\n").encode("utf-8"))

    def send_ready(self) -> None:
        self._send({
            "type": "ready",
            "key": "",
            "data": {
                "width": self.width,
                "height": self.height,
                "density": self.density,
                "status_bar_height": 24,
                "navigation_bar_height": 16,
                "text_scale": 1.0,
            },
        })

    def send_metrics(self, **overrides) -> None:
        """Tell the app the window changed (what Android does on rotation)."""
        data = {
            "width": self.width,
            "height": self.height,
            "density": self.density,
            "width_px": int(self.width * self.density),
            "height_px": int(self.height * self.density),
            "status_bar_height": 24,
            "navigation_bar_height": 16,
            "padding_top": 24,
            "padding_bottom": 16,
            "text_scale": 1.0,
            "reason": "configuration",
        }
        data.update(overrides)
        self._send({"type": "metrics", "key": "", "data": data})

    def resize(self, width: int, height: int, **overrides) -> None:
        """Simulate a window resize (split screen, foldable, desktop)."""
        self.width, self.height = int(width), int(height)
        self.send_metrics(**overrides)

    def rotate(self, **overrides) -> None:
        """Simulate a rotation by swapping the window dimensions."""
        self.resize(self.height, self.width, **overrides)

    def set_text_scale(self, scale: float) -> None:
        """Simulate the user changing their system font size."""
        self.send_metrics(text_scale=scale)

    def show_keyboard(self, height: int = 300) -> None:
        self.send_metrics(keyboard_height=height, reason="insets")

    def hide_keyboard(self) -> None:
        self.send_metrics(keyboard_height=0, reason="insets")

    def send_event(self, type_: str, key: str, data: dict | None = None) -> None:
        self._send({"type": type_, "key": key, "data": data or {}})

    def click(self, key: str) -> None:
        self.send_event("click", key)

    def change(self, key: str, value: Any) -> None:
        self.send_event("change", key, {"value": value})

    def submit(self, key: str, value: Any) -> None:
        self.send_event("submit", key, {"value": value})

    def back(self) -> None:
        self.send_event("back", "")

    def long_press(self, key: str) -> None:
        self.send_event("long_press", key)

    def gesture(self, key: str, gesture: str, **data) -> None:
        """Fire a gesture (``swipe_left``, ``double_tap``, ``scale``, …)."""
        self.send_event(gesture, key, data)

    def swipe(self, key: str, direction: str = "left", distance: float = 120) -> None:
        if direction not in ("left", "right", "up", "down"):
            raise ValueError("direction must be left/right/up/down")
        dx = {"left": -distance, "right": distance}.get(direction, 0)
        dy = {"up": -distance, "down": distance}.get(direction, 0)
        self.send_event(f"swipe_{direction}", key,
                        {"dx": dx, "dy": dy, "velocity": 1.0})

    def refresh(self, key: str) -> None:
        self.send_event("refresh", key)

    def dismiss(self, key: str, direction: str = "end") -> None:
        self.send_event("dismiss", key, {"direction": direction})

    def lifecycle(self, state: str) -> None:
        self.send_event("lifecycle", "", {"state": state})

    def tap_snackbar_action(self) -> bool:
        """Tap the action button of the most recent snackbar.

        Returns False when no snackbar is showing or it carried no
        ``on_action`` callback.
        """
        return self._snackbar_event(True)

    def dismiss_snackbar(self) -> bool:
        """Let the most recent snackbar time out without being tapped."""
        return self._snackbar_event(False)

    def _snackbar_event(self, actioned: bool) -> bool:
        bars = self.commands_named("snackbar")
        if not bars:
            return False
        callback_id = bars[-1].get("callback_id", "")
        if not callback_id:
            return False
        self.send_event("snackbar", "",
                        {"callback_id": callback_id, "action": actioned})
        return True

    # ── helpers for tests ─────────────────────────────────────────────────

    def wait_connected(self, timeout: float = 5.0) -> bool:
        return self._connected.wait(timeout)

    def wait_for(self, predicate, timeout: float = 3.0, interval: float = 0.01) -> bool:
        """Poll *predicate* until it is true or *timeout* elapses."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                try:
                    if predicate(self):
                        return True
                except Exception:
                    pass
            time.sleep(interval)
        return False

    def wait_for_text(self, text: str, timeout: float = 3.0) -> bool:
        return self.wait_for(lambda d: d.root is not None and text in d.root.texts(), timeout)

    def wait_for_command(self, cmd: str, timeout: float = 3.0) -> bool:
        return self.wait_for(
            lambda d: any(c.get("cmd") == cmd for c in d.commands), timeout
        )

    def wait_for_request(self, cmd: str, timeout: float = 3.0) -> dict:
        """Wait for a native service call and return the request message."""
        if not self.wait_for(
                lambda d: any(m.get("cmd") == cmd for m in d.requests), timeout):
            raise AssertionError(
                f"no {cmd!r} request; saw "
                f"{[m.get('cmd') for m in self.requests]}")
        return self.last_request(cmd)  # type: ignore[return-value]

    def commands_named(self, cmd: str) -> list[dict]:
        return [c for c in self.commands if c.get("cmd") == cmd]

    def key_of(self, type_name: str, text: str) -> str:
        """Find the key of the first widget of *type_name* showing *text*."""
        if self.root is None:
            raise AssertionError("nothing rendered yet")
        for node in self.root.walk():
            if node.type != type_name:
                continue
            for field in ("value", "text", "label"):
                if node.props.get(field) == text:
                    return node.key
        raise AssertionError(f"No {type_name} with text {text!r}. "
                             f"Rendered: {self.root.texts()}")

    @property
    def texts(self) -> list[str]:
        return self.root.texts() if self.root else []

    @property
    def activity_finished(self) -> bool:
        return self._activity_finished


def run_app(app, device: FakeDevice) -> threading.Thread:
    """Run ``app.run()`` on a background thread connected to *device*."""
    app.host = device.host
    app.port = device.port
    thread = threading.Thread(target=app.run, kwargs={"max_retries": 50},
                              daemon=True, name="pydrud-app")
    thread.start()
    if not device.wait_connected(timeout=5):
        raise AssertionError("app never connected to the fake device")
    return thread


class AppTester:
    """A one-liner harness for testing a whole app.

    ``AppTester`` boots a :class:`FakeDevice`, runs the app against it on a
    background thread, and gives you intention-revealing helpers (``tap``,
    ``type_in``, ``shows``) instead of raw keys and sockets::

        with AppTester(main) as app:
            app.type_in("email", "ada@example.com")
            app.tap("login")
            app.answer("dialog", True)         # canned native answer
            assert app.shows("Welcome back")

    Every helper settles the UI first (waits for the app to finish
    processing queued events), so tests do not need manual sleeps.
    """

    def __init__(self, target=None, *, app=None, width: int = 400,
                 height: int = 800, density: float = 2.0, title: str = "Test"):
        if target is None and app is None:
            raise ValueError("AppTester needs target= or app=")
        self.device = FakeDevice(width=width, height=height, density=density)
        if app is None:
            from pydrud.main import App

            app = App(target=target, title=title)
        self.app = app
        self._thread: Optional[threading.Thread] = None

    # ── lifecycle ────────────────────────────────────────────────────────

    def start(self) -> "AppTester":
        self.device.start()
        self._thread = run_app(self.app, self.device)
        self.device.wait_for(lambda d: d.root is not None, timeout=5)
        return self

    def stop(self) -> None:
        try:
            self.app.stop()
        finally:
            self.device.stop()

    def __enter__(self) -> "AppTester":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # ── interactions ─────────────────────────────────────────────────────

    def tap(self, key_or_text: str) -> "AppTester":
        """Tap a widget by key, or by the text it displays."""
        self.device.click(self._resolve(key_or_text))
        return self.settle()

    def long_press(self, key_or_text: str) -> "AppTester":
        self.device.long_press(self._resolve(key_or_text))
        return self.settle()

    def type_in(self, key: str, text: str) -> "AppTester":
        self.device.change(self._resolve(key), text)
        return self.settle()

    def toggle(self, key: str, value: bool = True) -> "AppTester":
        self.device.change(self._resolve(key), value)
        return self.settle()

    def swipe(self, key: str, direction: str = "left") -> "AppTester":
        self.device.swipe(self._resolve(key), direction)
        return self.settle()

    def press_back(self) -> bool:
        """Press the hardware back button; True when the app handled it."""
        before = len(self.device.commands_named("back_result"))
        self.device.back()
        self.device.wait_for(
            lambda d: len(d.commands_named("back_result")) > before, timeout=2)
        results = self.device.commands_named("back_result")
        return bool(results and results[-1].get("handled"))

    def lifecycle(self, state: str) -> "AppTester":
        self.device.lifecycle(state)
        return self.settle()

    def tap_snackbar_action(self) -> "AppTester":
        """Tap the Undo-style action on the snackbar currently showing."""
        self.device.tap_snackbar_action()
        return self.settle()

    def answer(self, cmd: str, value) -> "AppTester":
        """Pre-programme the answer to a native service call."""
        self.device.on_command(cmd, value)
        return self

    def settle(self, timeout: float = 1.0) -> "AppTester":
        """Wait until the app has drained its event queue."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.app._event_queue.empty():
                time.sleep(0.01)
                if self.app._event_queue.empty():
                    return self
            time.sleep(0.005)
        return self

    # ── assertions / queries ─────────────────────────────────────────────

    def shows(self, text: str, timeout: float = 1.0) -> bool:
        return self.device.wait_for_text(text, timeout)

    @property
    def texts(self) -> list:
        return self.device.texts

    @property
    def root(self):
        return self.device.root

    def node(self, key: str):
        return self.device.root.find(key) if self.device.root else None

    def prop(self, key: str, name: str, default=None):
        node = self.node(key)
        return default if node is None else node.props.get(name, default)

    def count(self, widget_type: str) -> int:
        return len(self.device.root.find_by_type(widget_type)) \
            if self.device.root else 0

    def requested(self, cmd: str, timeout: float = 1.0) -> dict:
        return self.device.wait_for_request(cmd, timeout)

    def _resolve(self, key_or_text: str) -> str:
        root = self.device.root
        if root is None:
            raise AssertionError("nothing rendered yet")
        if root.find(key_or_text) is not None:
            return key_or_text
        for node in root.walk():
            for field in ("value", "text", "label", "title"):
                if node.props.get(field) == key_or_text:
                    return node.key
        raise AssertionError(
            f"No widget with key or text {key_or_text!r}. "
            f"Visible text: {root.texts()}")
