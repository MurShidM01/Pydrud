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
import threading
import warnings
from typing import Any, Callable, Optional


TRANSITIONS = ("none", "fade", "slide_left", "slide_right", "slide_up",
               "slide_down", "scale", "shared_axis")


def parse_url(url: str) -> tuple[str, dict]:
    """Split ``myapp://host/items/7?tab=specs`` into ``("/items/7", {...})``.

    Scheme and host are dropped, the path is normalised to a leading slash
    and query parameters come back as a dict of strings.
    """
    from urllib.parse import parse_qsl, urlsplit

    parts = urlsplit(str(url))
    path = parts.path or "/"
    if parts.scheme and parts.netloc and not path.startswith("/"):
        path = "/" + path
    if parts.scheme and not parts.netloc and parts.path and "://" in url:
        path = "/" + parts.path.lstrip("/")
    if parts.netloc and parts.scheme not in ("http", "https"):
        # myapp://settings  → the host *is* the route
        path = "/" + parts.netloc + ("" if path == "/" else path)
    query = dict(parse_qsl(parts.query))
    if parts.fragment:
        query["fragment"] = parts.fragment
    return (path or "/"), query


class Route:
    """A named screen route.

    The name may be a plain identifier (``"settings"``) or a path pattern
    with parameters (``"/items/:id"``, ``"/files/*rest"``). Patterns are
    matched by :meth:`Router.match`, and the captured values are passed to
    the builder as its second argument.
    """

    def __init__(self, name: str, builder: Callable, *, title: str = "",
                 transition: str = "none", guard: Optional[Callable] = None):
        if not callable(builder):
            raise TypeError(f"Route {name!r} builder must be callable")
        if transition not in TRANSITIONS:
            raise ValueError(f"transition must be one of {TRANSITIONS}")
        if guard is not None and not callable(guard):
            raise TypeError("guard must be callable")
        self.name = name
        self.builder = builder
        self.title = title
        self.transition = transition
        self.guard = guard
        self.segments = [s for s in str(name).split("/") if s]
        self.is_pattern = any(s.startswith((":", "*")) for s in self.segments)

    # ── pattern matching ─────────────────────────────────────────────────

    def match(self, path: str) -> Optional[dict]:
        """Return captured params when *path* matches, else ``None``."""
        wanted = [s for s in str(path).split("/") if s]
        params: dict = {}
        for index, segment in enumerate(self.segments):
            if segment.startswith("*"):
                params[segment[1:] or "rest"] = "/".join(wanted[index:])
                return params
            if index >= len(wanted):
                return None
            if segment.startswith(":"):
                params[segment[1:]] = _coerce(wanted[index])
            elif segment != wanted[index]:
                return None
        return params if len(wanted) == len(self.segments) else None

    def build_path(self, params: dict) -> str:
        """Render this route's pattern with *params* filled in."""
        out = []
        for segment in self.segments:
            if segment.startswith(":"):
                key = segment[1:]
                if key not in params:
                    raise KeyError(f"Route {self.name!r} needs {key!r}")
                out.append(str(params[key]))
            elif segment.startswith("*"):
                out.append(str(params.get(segment[1:] or "rest", "")))
            else:
                out.append(segment)
        return "/" + "/".join(p for p in out if p != "")

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


def _coerce(value: str):
    """URL segments are strings; turn obvious integers into ints."""
    if value.isdigit():
        return int(value)
    return value


class NavigationStack:
    """A LIFO stack of navigation entries (the top entry is the active screen).

    Every operation takes a lock, and the compound ones ("pop unless this
    is the root", "collapse back to the root") are single operations
    rather than a check followed by a mutation — two taps landing on
    different threads can no longer interleave into a corrupted stack.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._stack: list[dict] = []

    def push(self, route_name: str, params: dict | None = None) -> None:
        """Push a new screen onto the stack."""
        with self._lock:
            self._stack.append({"route": route_name,
                                "params": dict(params or {})})

    def pop(self, *, keep_root: bool = False) -> dict | None:
        """Pop the top screen, or return ``None`` when there is none.

        ``keep_root=True`` refuses to pop the last entry, which is the
        atomic form of ``if stack.can_pop(): stack.pop()``.
        """
        with self._lock:
            if not self._stack or (keep_root and len(self._stack) < 2):
                return None
            return self._stack.pop()

    def current(self) -> dict | None:
        """Peek at the top entry without removing it."""
        with self._lock:
            return self._stack[-1] if self._stack else None

    def root(self) -> dict | None:
        """Peek at the bottom (root) entry."""
        with self._lock:
            return self._stack[0] if self._stack else None

    def clear(self) -> None:
        with self._lock:
            self._stack.clear()

    def can_pop(self) -> bool:
        """True when there is a screen *below* the active one."""
        with self._lock:
            return len(self._stack) > 1

    def size(self) -> int:
        with self._lock:
            return len(self._stack)

    def routes(self) -> list[str]:
        with self._lock:
            return [e["route"] for e in self._stack]

    def reset_to(self, route_name: str, params: dict | None = None) -> None:
        """Clear the stack and set *route_name* as the single root entry."""
        with self._lock:
            self._stack = [{"route": route_name, "params": dict(params or {})}]

    def collapse_to_root(self) -> bool:
        """Drop every entry above the root. False when already there."""
        with self._lock:
            if len(self._stack) < 2:
                return False
            del self._stack[1:]
            return True

    def replace_top(self, route_name: str, params: dict | None = None) -> None:
        entry = {"route": route_name, "params": dict(params or {})}
        with self._lock:
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
        self._guards: list[Callable] = []
        self._not_found: Optional[Callable] = None
        self._children: dict[str, "Router"] = {}
        self._parent: Optional["Router"] = None
        self._scheme: str = ""
        self._initial_route: Optional[str] = None
        self._initial_params: dict = {}

    # ── Route management ─────────────────────────────────────────────────

    def define(self, name: str, builder: Callable, **kwargs) -> "Router":
        """Register a route.

        ``name`` is either a plain name (``"settings"``) or a path pattern
        with parameters (``"/items/:id"``). Extra keyword arguments:
        ``title=``, ``transition=`` (see :data:`TRANSITIONS`) and
        ``guard=`` (a callable returning ``False`` or a redirect path).
        """
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

    def not_found(self, builder: Callable) -> "Router":
        """Screen shown when a link matches no route."""
        self._not_found = builder
        return self

    def guard(self, callback: Callable) -> "Router":
        """Register a global navigation guard.

        The guard receives ``(name, params)`` and returns ``True`` to allow,
        ``False`` to block, or a route name/path to redirect to.
        """
        if not callable(callback):
            raise TypeError("guard must be callable")
        self._guards.append(callback)
        return self

    def scheme(self, scheme: str) -> "Router":
        """Declare the custom URL scheme used for deep links (``myapp``)."""
        self._scheme = str(scheme).rstrip(":/")
        return self

    # ── URL-style navigation ─────────────────────────────────────────────

    def match(self, path: str) -> Optional[tuple]:
        """Resolve a path to ``(route, params)``, or ``None``.

        Exact names win over patterns, and more specific patterns (fewer
        wildcards, more literal segments) win over looser ones.
        """
        raw = str(path)
        if raw in self._routes:
            return self._routes[raw], {}
        normalised = "/" + raw.strip("/")
        if normalised in self._routes:
            return self._routes[normalised], {}

        best: Optional[tuple] = None
        best_score = -1
        for route in self._routes.values():
            params = route.match(normalised)
            if params is None:
                continue
            literals = sum(1 for s in route.segments
                           if not s.startswith((":", "*")))
            wildcards = sum(1 for s in route.segments if s.startswith("*"))
            score = literals * 10 - wildcards * 5 - len(params)
            if score > best_score:
                best, best_score = (route, params), score
        return best

    def go(self, path: str, **extra) -> bool:
        """Navigate to a URL-style path, e.g. ``router.go("/items/7")``.

        Returns ``True`` when a route matched. Query parameters and *extra*
        keyword arguments are merged into the route params.
        """
        clean, query = parse_url(path)
        found = self.match(clean)
        if found is None:
            if self._not_found is not None:
                self._stack.push("__not_found__", {"path": clean})
                self._routes.setdefault(
                    "__not_found__", Route("__not_found__", self._not_found))
                self._render()
            return False
        route, params = found
        params.update(query)
        params.update(extra)
        self.push(route.name, **params)
        return True

    def handle_link(self, url: str) -> bool:
        """Entry point for deep links, shortcuts and push notification taps."""
        return self.go(url)

    def path(self) -> str:
        """The current location as a path, with parameters substituted."""
        name = self.current_route
        if name is None:
            return "/"
        route = self._routes[name]
        if route.is_pattern:
            try:
                return route.build_path(self.current_params)
            except KeyError:
                return route.name
        return route.name if route.name.startswith("/") else "/" + route.name

    def url(self) -> str:
        """The current location as a full deep link."""
        prefix = f"{self._scheme}://" if self._scheme else ""
        return prefix + self.path().lstrip("/")

    # ── nested navigators ────────────────────────────────────────────────

    def nest(self, name: str, child: "Router") -> "Router":
        """Attach a child router that owns navigation *inside* one screen.

        The child keeps its own stack, so a tab can have history without
        affecting the outer stack. Hardware back is offered to the active
        child first.
        """
        if not isinstance(child, Router):
            raise TypeError("nest() expects a Router")
        child._parent = self
        child._app = self._app
        self._children[name] = child
        return self

    def child(self, name: str) -> Optional["Router"]:
        return self._children.get(name)

    @property
    def parent(self) -> Optional["Router"]:
        return self._parent

    def active_child(self) -> Optional["Router"]:
        """The nested router belonging to the current screen, if any."""
        return self._children.get(self.current_route or "")

    # ── Navigation ───────────────────────────────────────────────────────

    def _resolve(self, name: str, params: dict) -> tuple[str, dict]:
        """Accept either a route pattern or a concrete path/URL.

        ``push("/items/:id", id=4)`` and ``push("/items/4")`` are equivalent,
        and a full deep link (``myapp://items/4?tab=specs``) works too.
        """
        if name in self._routes:
            return name, params
        path = name
        if "://" in path:
            path, query = parse_url(path)
            params = {**query, **params}
        matched = self.match(path)
        if matched is None:
            self._require(name)          # raises with the available routes
        route, matched_params = matched
        return route.name, {**matched_params, **params}

    def push(self, name: str, **params) -> None:
        """Navigate to a route, keeping the current screen on the stack."""
        name, params = self._resolve(name, params)
        allowed = self._check_guards(name, params)
        if allowed is False:
            return
        if isinstance(allowed, str) and allowed != name:
            self.go(allowed)
            return
        self._stack.push(name, params)
        self._render()

    def pop(self) -> bool:
        """Go back to the previous screen. Returns True when it navigated."""
        if self._stack.pop(keep_root=True) is None:
            return False
        self._render()
        return True

    def replace(self, name: str, **params) -> None:
        """Replace the current screen without growing the stack."""
        name, params = self._resolve(name, params)
        self._stack.replace_top(name, params)
        self._render()

    def reset(self, name: str | None = None, **params) -> None:
        """Clear history and make a route the sole root screen.

        Omitting *name* restores the route passed to :meth:`initial`, which
        makes ``reset()`` a reliable "go home" operation. If no initial route
        was configured there is no safe route to select; the stack is cleared,
        the attached app is updated, and a warning explains the ambiguity.
        """
        if name is None:
            if self._initial_route is None:
                warnings.warn(
                    "Router.reset() has no initial route; clearing the stack.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                self._stack.clear()
                self._render()
                return
            name = self._initial_route
            params = {**self._initial_params, **params}
        name, params = self._resolve(name, params)
        self._stack.reset_to(name, params)
        self._render()

    def pop_to_root(self) -> bool:
        """Pop every screen except the root one."""
        if not self._stack.collapse_to_root():
            return False
        self._render()
        return True

    def handle_back(self) -> bool:
        """Handle a hardware back press.

        A nested navigator on the current screen gets the first chance to
        consume the press; otherwise this router pops. Returns False only
        when nothing could go back and Android should finish the activity.
        """
        child = self.active_child()
        if child is not None and child.can_pop():
            return child.handle_back()
        return self.pop()

    def _check_guards(self, name: str, params: dict):
        """Run global guards and the route's own guard."""
        route = self._routes.get(name)
        checks = list(self._guards)
        if route is not None and route.guard is not None:
            checks.append(route.guard)
        for check in checks:
            try:
                verdict = check(name, dict(params))
            except TypeError:
                verdict = check(name)
            if verdict is False:
                return False
            if isinstance(verdict, str) and verdict:
                return verdict
        return True

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
        self._initial_route = name
        self._initial_params = dict(params)
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
            transition = self._routes[current].transition
            if transition != "none" and hasattr(page, "route_transition"):
                page.route_transition(transition)
            title = self._routes[current].title
            if title and hasattr(page, "set_title"):
                page.set_title(title)
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
