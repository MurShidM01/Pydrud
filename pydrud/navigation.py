"""
Navigation system for Pydrud — Router, NavigationStack, and Route.

Each screen is a builder function that receives the page object (and,
optionally, the route parameters). The Router manages push/pop with a
navigation stack and syncs with the Android hardware back button.

Usage::

    from pydrud import App, Router, Text

    def home(page):
        page.add(Text("Home"))

    def details(page, params):
        page.add(Text(f"Item {params['id']}"))

    router = Router()
    router.define("home", home).define("details", details)
    router.initial("home")

    app = App(target=router.build_root())
    app.attach_router(router)
    app.run()
"""

from __future__ import annotations
import inspect
from typing import Any, Callable, Optional


class Route:
    """A named screen route."""

    def __init__(self, name: str, builder: Callable, *, title: str = ""):
        if not callable(builder):
            raise TypeError(f"Route {name!r} builder must be callable")
        self.name = name
        self.builder = builder
        self.title = title

    def build(self, page: Any, params: dict | None = None) -> None:
        """Invoke the builder, passing params when the builder accepts them."""
        params = dict(params or {})
        try:
            sig = inspect.signature(self.builder)
            accepts_params = len(
                [
                    p for p in sig.parameters.values()
                    if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                ]
            ) >= 2
        except (TypeError, ValueError):  # builtins / C callables
            accepts_params = False

        if accepts_params:
            self.builder(page, params)
        else:
            self.builder(page)

    def __repr__(self) -> str:
        return f"Route({self.name!r})"


class NavigationStack:
    """A LIFO stack of navigation entries (the top entry is the active screen)."""

    def __init__(self):
        self._stack: list[dict] = []

    def push(self, route_name: str, params: dict | None = None) -> None:
        """Push a new screen onto the stack."""
        self._stack.append({"route": route_name, "params": dict(params or {})})

    def pop(self) -> dict | None:
        """Pop the top screen. Returns the removed entry, or None if empty."""
        if not self._stack:
            return None
        return self._stack.pop()

    def current(self) -> dict | None:
        """Peek at the top entry without removing it."""
        return self._stack[-1] if self._stack else None

    def clear(self) -> None:
        self._stack.clear()

    def can_pop(self) -> bool:
        """True when there is a screen *below* the active one."""
        return len(self._stack) > 1

    def size(self) -> int:
        return len(self._stack)

    def routes(self) -> list[str]:
        return [e["route"] for e in self._stack]

    def reset_to(self, route_name: str, params: dict | None = None) -> None:
        """Clear the stack and set *route_name* as the single root entry."""
        self._stack = [{"route": route_name, "params": dict(params or {})}]

    def replace_top(self, route_name: str, params: dict | None = None) -> None:
        entry = {"route": route_name, "params": dict(params or {})}
        if self._stack:
            self._stack[-1] = entry
        else:
            self._stack.append(entry)


class Router:
    """Manages route definitions and navigation state.

    The router is deliberately decoupled from the App so it can be used
    independently (e.g. in tests or with multiple page instances).
    """

    def __init__(self):
        self._routes: dict[str, Route] = {}
        self._stack = NavigationStack()
        self._app: Optional[Any] = None  # Set by App.attach_router()
        self._on_change: list[Callable[[str], None]] = []

    # ── Route management ─────────────────────────────────────────────────

    def define(self, name: str, builder: Callable, **kwargs) -> "Router":
        """Register a named route with its screen builder function."""
        self._routes[name] = Route(name, builder, **kwargs)
        return self

    def define_many(self, routes: dict[str, Callable]) -> "Router":
        """Register multiple routes at once: ``{"name": builder, ...}``."""
        for name, builder in routes.items():
            self.define(name, builder)
        return self

    def has_route(self, name: str) -> bool:
        return name in self._routes

    @property
    def routes(self) -> list[str]:
        return sorted(self._routes)

    def on_change(self, callback: Callable[[str], None]) -> "Router":
        """Register a callback fired after every successful navigation."""
        self._on_change.append(callback)
        return self

    # ── Navigation ───────────────────────────────────────────────────────

    def push(self, name: str, **params) -> None:
        """Navigate to a route, keeping the current screen on the stack."""
        self._require(name)
        self._stack.push(name, params)
        self._render()

    def pop(self) -> bool:
        """Go back to the previous screen. Returns True when it navigated."""
        if not self._stack.can_pop():
            return False
        self._stack.pop()
        self._render()
        return True

    def replace(self, name: str, **params) -> None:
        """Replace the current screen without growing the stack."""
        self._require(name)
        self._stack.replace_top(name, params)
        self._render()

    def reset(self, name: str | None = None, **params) -> None:
        """Clear the history. With *name*, make it the new root screen."""
        if name is None:
            self._stack.clear()
            return
        self._require(name)
        self._stack.reset_to(name, params)
        self._render()

    def pop_to_root(self) -> bool:
        """Pop every screen except the root one."""
        if not self._stack.can_pop():
            return False
        root = self._stack.routes()[0]
        root_params = self._stack._stack[0]["params"]
        self._stack.reset_to(root, root_params)
        self._render()
        return True

    def handle_back(self) -> bool:
        """Handle a hardware back press.

        Returns True when a screen was popped, or False when the stack is at
        the root and Android should finish the activity.
        """
        return self.pop()

    # ── Builder & helpers ────────────────────────────────────────────────

    def build_root(self) -> Callable:
        """Return the page builder that renders the current route."""
        def _builder(page):
            entry = self._stack.current()
            if entry is None:
                return
            route = self._routes.get(entry["route"])
            if route is not None:
                route.build(page, entry["params"])
        return _builder

    def initial(self, name: str, **params) -> "Router":
        """Set the initial route (called before ``App.run()``)."""
        self._require(name)
        self._stack.reset_to(name, params)
        return self

    def attach(self, app: Any) -> None:
        """Attach this router to an App instance."""
        self._app = app

    # ── State ────────────────────────────────────────────────────────────

    @property
    def current_route(self) -> Optional[str]:
        entry = self._stack.current()
        return entry["route"] if entry else None

    @property
    def current_params(self) -> dict:
        entry = self._stack.current()
        return dict(entry["params"]) if entry else {}

    @property
    def stack_size(self) -> int:
        return self._stack.size()

    @property
    def history(self) -> list[str]:
        return self._stack.routes()

    def can_pop(self) -> bool:
        return self._stack.can_pop()

    # ── internals ────────────────────────────────────────────────────────

    def _require(self, name: str) -> None:
        if name not in self._routes:
            raise ValueError(
                f"Route {name!r} not defined. Available: {sorted(self._routes)}"
            )

    def _render(self) -> None:
        current = self.current_route
        if self._app is not None and current is not None:
            page = self._app.page
            page.clear()
            route = self._routes[current]
            route.build(page, self.current_params)
            page.update()
        for cb in list(self._on_change):
            try:
                cb(current or "")
            except Exception as exc:  # pragma: no cover - user callback
                print(f"[Pydrud] Router on_change error: {exc}")

    def __repr__(self) -> str:
        return f"Router(current={self.current_route!r}, stack={self._stack.size()})"
