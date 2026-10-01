"""
Navigation system for Pydrud — Router, NavigationStack, and Route.

Provides a screen-based navigation model where each screen is a builder
function that receives the page object. The Router manages push/pop with
a navigation stack and syncs with the Android hardware back button.

Usage::

    from pydrud import App, Router

    def home_screen(page):
        page.add(Text("Home"))

    def settings_screen(page):
        page.add(Text("Settings"))

    router = Router()
    router.define("home", home_screen)
    router.define("settings", settings_screen)

    app = App(target=router.build_root())
    app.attach_router(router)
    app.run()
"""

from __future__ import annotations
from typing import Any, Callable, Optional

from pydrud.main import _Page


class Route:
    """A named screen route."""

    def __init__(
        self,
        name: str,
        builder: Callable,
        *,
        title: str = "",
    ):
        self.name = name
        self.builder = builder
        self.title = title

    def __repr__(self) -> str:
        return f"Route({self.name!r})"


class NavigationStack:
    """A simple LIFO stack of navigation entries.

    Each entry stores the route name and its parameters, so state
    can be preserved when pushing and restored when popping.
    """

    def __init__(self):
        self._stack: list[dict] = []

    def push(self, route_name: str, params: dict | None = None) -> None:
        """Push a new screen onto the stack."""
        self._stack.append({
            "route": route_name,
            "params": dict(params or {}),
        })

    def pop(self) -> dict | None:
        """Pop the top screen. Returns the entry dict or None if empty."""
        if not self._stack:
            return None
        return self._stack.pop()

    def current(self) -> dict | None:
        """Peek at the top entry without removing it."""
        if not self._stack:
            return None
        return self._stack[-1]

    def clear(self) -> None:
        """Remove all entries."""
        self._stack.clear()

    def can_pop(self) -> bool:
        """True if there is more than one entry (or at least one to pop)."""
        return len(self._stack) > 1

    def size(self) -> int:
        return len(self._stack)

    def reset_to(self, route_name: str) -> None:
        """Clear the stack and set *route_name* as the single root entry."""
        self._stack = [{"route": route_name, "params": {}}]


class Router:
    """Manages route definitions and navigation state.

    The router is deliberately decoupled from the App so it can be
    used independently (e.g. in tests or with multiple page instances).
    """

    def __init__(self):
        self._routes: dict[str, Route] = {}
        self._stack = NavigationStack()
        self._current_route: Optional[str] = None
        self._app: Optional[Any] = None  # Set by App.attach_router()

    # ── Route management ─────────────────────────────────────────────────

    def define(self, name: str, builder: Callable, **kwargs) -> "Router":
        """Register a named route with its screen builder function."""
        self._routes[name] = Route(name, builder, **kwargs)
        return self

    def define_many(self, routes: dict[str, Callable]) -> "Router":
        """Register multiple routes at once: ``{"name": builder, ...}``."""
        for name, builder in routes.items():
            self._routes[name] = Route(name, builder)
        return self

    def has_route(self, name: str) -> bool:
        return name in self._routes

    # ── Navigation ───────────────────────────────────────────────────────

    def push(self, name: str, **params) -> None:
        """Navigate to a route, pushing current screen onto the stack.

        The current screen's builder will be called with the page to
        rebuild the widget tree. If the page has an app reference, it
        triggers ``page.update()`` automatically.
        """
        if name not in self._routes:
            raise ValueError(f"Route {name!r} not defined. Available: {list(self._routes.keys())}")

        route = self._routes[name]

        # Save current screen on stack if we have one.
        if self._current_route is not None:
            self._stack.push(self._current_route, {})

        self._current_route = name

        # Build the screen.
        if self._app is not None:
            page = self._app.page
            page.clear()
            route.builder(page)
            page.update()

    def pop(self) -> None:
        """Go back to the previous screen.

        Pops the top entry from the stack and rebuilds that screen.
        If the stack is empty (only root remains), does nothing.
        """
        if not self._stack.can_pop():
            return

        entry = self._stack.pop()
        if entry is None:
            return

        prev_route = entry["route"]
        self._current_route = prev_route
        route = self._routes.get(prev_route)
        if route is None:
            return

        if self._app is not None:
            page = self._app.page
            page.clear()
            route.builder(page)
            page.update()

    def replace(self, name: str, **params) -> None:
        """Replace the current screen without adding to the stack."""
        if name not in self._routes:
            raise ValueError(f"Route {name!r} not defined.")

        self._current_route = name
        route = self._routes[name]

        if self._app is not None:
            page = self._app.page
            page.clear()
            route.builder(page)
            page.update()

    def handle_back(self) -> bool:
        """Handle a back navigation request (from Android back button).

        Returns True if the back was handled (navigated back), or
        False if the stack is at the root and Android should finish
        the activity.
        """
        if self._stack.can_pop():
            self.pop()
            return True
        return False

    # ── Builder & helpers ────────────────────────────────────────────────

    def build_root(self) -> Callable:
        """Return a page builder that renders the current route.

        This is the function passed to ``App(target=...)``.
        """
        def _builder(page):
            if self._current_route is not None:
                route = self._routes.get(self._current_route)
                if route:
                    route.builder(page)
        return _builder

    def initial(self, name: str) -> "Router":
        """Set the initial route (called before App.run())."""
        self._current_route = name
        return self

    def attach(self, app: Any) -> None:
        """Attach this router to an App instance."""
        self._app = app

    # ── State ────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear the navigation stack and route state."""
        self._stack.clear()
        self._current_route = None

    @property
    def current_route(self) -> Optional[str]:
        return self._current_route

    @property
    def stack_size(self) -> int:
        return self._stack.size()

    def __repr__(self) -> str:
        return f"Router(current={self._current_route!r}, stack={self._stack.size()})"
