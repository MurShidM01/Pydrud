"""
The mutable page object passed to the user's builder function.

A :class:`_Page` is the small imperative surface a screen uses — ``add``,
``update``, ``toast``, the native-service accessors — while all the state
and transport live on :class:`~pydrud.runtime.app.App`. Split out of
``app.py`` so the page API reads on its own.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Callable, Optional

from pydrud.widgets import Widget

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pydrud.runtime.app import App


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
