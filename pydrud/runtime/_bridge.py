"""
The TCP bridge: connecting, reading, and the single UI event loop.

Also owns native request/response calls and the UI-thread queue. Split out of
``app.py``; the methods run on ``App`` through :class:`BridgeMixin`.
"""

from __future__ import annotations

import queue
import socket
import threading
import time
from typing import Callable, Optional

from pydrud.core.protocol import MAX_FRAME_BYTES
from pydrud.core.results import Result
from pydrud.core.tasks import TaskRunner
from pydrud.runtime._capabilities import capability_failure


class BridgeMixin:
    """Bridge connection, event loop, native calls and UI-thread marshalling."""


    # ── native service calls ──────────────────────────────────────────────

    def invoke(self, cmd: str, **data) -> Result:
        """Send a command that expects an answer and return a :class:`Result`.

        A ``request_id`` is attached so the connected client can correlate its
        reply. When the bridge is disconnected, or the client does not
        advertise a required optional service, the result fails immediately
        instead of hanging forever.
        """
        with self._lock:
            self._request_seq += 1
            request_id = f"r{self._request_seq}"
        result = Result(request_id, cmd)
        if not self._connected:
            result.fail("bridge not connected")
            return result
        unavailable = capability_failure(self._native_capabilities, cmd)
        if unavailable is not None:
            result.fail(unavailable)
            return result
        self._pending[request_id] = result
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
        # Cancel (not fail): a shutdown is expected, so coroutines awaiting
        # these results see `ResultCancelled` instead of an app-level error.
        pending, self._pending = self._pending, {}
        for result in pending.values():
            result.cancel(reason)

    # ── background work ───────────────────────────────────────────────────

    @property
    def tasks(self) -> TaskRunner:
        return self._tasks

    def run_task(self, fn: Callable, *args, **kwargs):
        """Run *fn* on a worker thread (also accepts ``async def``)."""
        return self._tasks.run(fn, *args, **kwargs)

    def run_on_ui(self, fn: Callable, *args, **kwargs) -> None:
        """Queue *fn* to run on the event-loop thread.

        Widget mutations from a worker thread must go through this, using the
        connected runtime's single UI actor.
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
        reader = self._reader_thread
        loop_alive = reader is not None and reader.is_alive()
        if self._ui_thread_id is None and not loop_alive:
            # Headless or fully disconnected: no event loop will ever drain
            # the queue, so run inline exactly as before.
            fn(*args, **kwargs)
            return
        # Queue callbacks while the app is starting too. ``_running`` becomes
        # true before the bridge event loop publishes ``_ui_thread_id``; doing
        # the callback inline in that window races the initial render and can
        # lose a state update on slower hosts (notably Windows).
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


    # ── bridge internals ──────────────────────────────────────────────────

    def _start_bridge(self, *, retry=True, retry_delay=0.5, max_retries=30):
        """Connect to the configured local renderer and run the event loop."""
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

                # Wait for ``ready`` before the first tree: the renderer's
                # optional capabilities decide whether widgets/services are
                # available. ``_handle_ready`` builds and sends the snapshot.
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
        print("[Pydrud] Running in headless/test mode (no renderer bridge).")
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
        #: Apply the same hard limit as every other protocol decoder so an
        #: unauthenticated or buggy peer cannot grow this buffer indefinitely.
        max_line = MAX_FRAME_BYTES
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
                if len(buffer) > max_line and b"\n" not in buffer:
                    self._report_error(RuntimeError(
                        "bridge frame exceeds the maximum size of "
                        f"{max_line} bytes"))
                    break
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if len(line) + 1 > max_line:
                        self._report_error(RuntimeError(
                            "bridge frame exceeds the maximum size of "
                            f"{max_line} bytes"))
                        return
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
                try:
                    self._handle_raw_event(raw)
                finally:
                    self._events_handled += 1
        finally:
            self._ui_thread_id = None
            self._connected = False
            self._cancel_pending()
            self._inflight.clear()
            self._inflight_trees.clear()
            self._outbox.clear()
            self._outbox_final_tree = None
            self._render_pending = False
            if self._transport:
                try:
                    self._transport.close()
                except Exception:
                    pass
            self._transport = None