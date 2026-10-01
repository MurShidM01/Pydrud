"""
A fake Android device for end-to-end testing of the Pydrud bridge.

``FakeDevice`` speaks exactly the protocol the Java ``BridgeService`` /
``ViewFactory`` implement:

* it listens on 127.0.0.1 and accepts the Python app's connection;
* it sends a ``ready`` event with screen metrics;
* it applies ``full_render`` and ``render`` (patch) commands to an in-memory
  mirror of the native view tree, using the same semantics as
  ``ViewFactory.applyPatch``;
* it can push ``click`` / ``change`` / ``back`` / ``lifecycle`` events back
  into the app and records every command it received.

That makes it possible to run a complete Pydrud app in CI and assert on what
the device would actually display.
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

    def lifecycle(self, state: str) -> None:
        self.send_event("lifecycle", "", {"state": state})

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
