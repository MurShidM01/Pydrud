"""
Lifecycle hooks, deep links, error reporting and tree building for :class:`App`.

Everything a native event can call back into lives here; split out of
``app.py`` so the event surface is readable on its own.
"""

from __future__ import annotations

import sys
import traceback
from typing import TYPE_CHECKING, Callable, Optional

from pydrud.core.results import ResultCancelled
from pydrud.runtime._capabilities import replace_unsupported_widgets
from pydrud.widgets import Widget, assign_stable_keys, validate_tree_keys

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pydrud.runtime.app import App


class LifecycleMixin:
    """Lifecycle / deep-link / push / sensor handlers and tree building."""


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

    def on_push_token(self, callback: Callable[[str], None]) -> "App":
        """Handle an FCM registration token (issued or refreshed).

        Firebase rotates the token silently; without this hook the native
        ``push_token`` event had nowhere to go and the server kept a stale
        token.  The callback receives the token string.
        """
        self._push_token_handlers.append(callback)
        return self

    def on_audio_complete(self, callback: Callable[[dict], None]) -> "App":
        """Fire when ``page.audio.play()`` reaches the end of a clip.

        The callback receives the event payload (``{"source": ...}``).
        """
        self._audio_complete_handlers.append(callback)
        return self

    def on_location(self, callback: Callable[[dict], None]) -> "App":
        """Receive GPS fixes started with ``page.location.watch()``.

        The callback gets ``{"latitude", "longitude", "accuracy", "altitude",
        "speed", "bearing", "time"}`` for every update until
        ``page.location.stop_watch()``.
        """
        self._location_handlers.append(callback)
        return self

    def on_bluetooth(self, callback: Callable[[dict], None]) -> "App":
        """Receive Bluetooth events: ``found``, ``notify``, ``disconnected``.

        Scanning reports each peripheral as it appears, and a characteristic
        subscribed with ``page.bluetooth.notify()`` delivers its payload here
        as a list of byte values.
        """
        self._bluetooth_handlers.append(callback)
        return self

    def on_recording(self, callback: Callable[[dict], None]) -> "App":
        """Fire when a video started with ``page.camera.record()`` finalises.

        The callback receives ``{"path", "ok"}``.
        """
        self._recording_handlers.append(callback)
        return self

    def _schedule_awaitable(self, awaitable) -> None:
        """Run an async UI callback without blocking the bridge event loop.

        ``TaskRunner`` owns a small coroutine-capable worker pool.  Native
        :class:`~pydrud.core.results.Result` instances are awaitable and
        forward their completion back into this coroutine's event loop, so a
        handler can naturally write ``await page.dialog.confirm(...)``.
        """
        async def run_handler():
            try:
                return await awaitable
            except ResultCancelled:
                # The bridge shut down while the call was pending — a normal
                # shutdown signal, not an app error.  Report nothing.
                return None
            except Exception as exc:
                # Route through the app's error path (on_error / dev server /
                # logcat) instead of TaskRunner's raw worker-thread print,
                # which escapes pytest capture and interleaves with output.
                self._report_error(exc)

        try:
            self._tasks.run(run_handler)
        except Exception as exc:
            self._report_error(exc)

    def _dispatch(self, handlers: list, payload) -> None:
        """Call every handler, isolating failures from the event loop."""
        for cb in list(handlers):
            try:
                result = cb(payload)
                if hasattr(result, "__await__"):
                    self._schedule_awaitable(result)
            except Exception as exc:
                self._report_error(exc)

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
        tb_str = traceback.format_exc()
        if self._dev_server is not None:
            try:
                self._dev_server.broadcast_error(exc, tb=tb_str)
            except Exception:
                pass
        if self._error_handler is not None:
            try:
                self._error_handler(exc)
                return
            except Exception:
                pass
        # App.run installs the Android stdout/stderr adapter on-device. Host
        # preview reports the same traceback through ordinary stderr without
        # importing any platform logging implementation.
        print(f"Error: {exc}", file=sys.stderr)
        if tb_str.strip() and tb_str.strip() != "NoneType: None":
            print(tb_str.rstrip(), file=sys.stderr)

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
        tree = replace_unsupported_widgets(tree, self._native_capabilities)
        validate_tree_keys(tree)
        self._materialize_elements(tree)
        self._current_tree = tree
        self._desired_tree = tree
        self._event_dispatcher.unregister_all()
        self._event_dispatcher.register_tree(tree)
        return tree

    def _materialize_elements(self, tree: Widget) -> None:
        """Refresh persistent logical element metadata without touching Views."""
        stack: list[tuple[Widget, Optional[str], int]] = [(tree, None, 0)]
        while stack:
            widget, parent_key, index = stack.pop()
            # Freeze the build's props now (PB-004) so the diff compares the
            # values that were actually rendered, not a fresh re-serialisation.
            props = widget._freeze_props()
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
                stack.append((child, widget.key, i))