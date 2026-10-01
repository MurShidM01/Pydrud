"""
Advanced widgets: camera, maps, rich text and high-performance lists.

These are the components that need a real native view to be worth having —
a camera surface, a map, a ``RecyclerView`` that recycles rows instead of
inflating ten thousand of them, and a span-aware ``TextView``.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional, Sequence, Union

from pydrud.widgets.base import Widget
from pydrud.widgets.theme import Colors


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# ──────────────────────────────────────────────────────────────────────────
# Camera
# ──────────────────────────────────────────────────────────────────────────


class CameraPreview(Widget):
    """A live CameraX preview surface.

    The widget only *shows* the feed; capturing is driven imperatively from
    :class:`~pydrud.services.native.Camera`::

        page.add(CameraPreview(key="cam", facing="back",
                               on_scan=lambda e: open_url(e.data["value"])))

        page.camera.capture(key="cam").then(lambda path: upload(path))

    Requires the ``camera`` permission — request it before mounting.
    """

    _widget_type = "CameraPreview"
    FACINGS = ("back", "front")
    FITS = ("cover", "contain")

    def __init__(
        self,
        *,
        facing: str = "back",
        fit: str = "cover",
        flash: str = "auto",
        torch: bool = False,
        scan: bool = False,
        scan_formats: Optional[Sequence[str]] = None,
        aspect_ratio: Optional[str] = None,
        on_scan: Optional[Callable] = None,
        on_ready: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        if facing not in self.FACINGS:
            raise ValueError(f"facing must be one of {self.FACINGS}")
        if fit not in self.FITS:
            raise ValueError(f"fit must be one of {self.FITS}")
        if flash not in ("on", "off", "auto", "torch"):
            raise ValueError("flash must be on/off/auto/torch")
        super().__init__(key=key, on_scan=on_scan, on_ready=on_ready,
                         on_error=on_error, **kwargs)
        self.facing = facing
        self.fit = fit
        self.flash = flash
        self.torch = bool(torch)
        self.scan = bool(scan) or on_scan is not None
        self.scan_formats = [str(f) for f in (scan_formats or [])]
        self.aspect_ratio = aspect_ratio
        self.style.setdefault("width", "match")
        self.style.setdefault("height", kwargs.pop("height", 320))

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "facing": self.facing,
            "fit": self.fit,
            "flash": self.flash,
            "torch": self.torch or None,
            "scan": self.scan or None,
            "scanFormats": self.scan_formats or None,
            "aspectRatio": self.aspect_ratio,
        }))
        return props


# ──────────────────────────────────────────────────────────────────────────
# Maps
# ──────────────────────────────────────────────────────────────────────────


class Marker:
    """A pin on a :class:`MapView`."""

    __slots__ = ("lat", "lon", "title", "snippet", "color", "id", "draggable")

    def __init__(self, lat: float, lon: float, *, title: str = "",
                 snippet: str = "", color: str = Colors.ERROR,
                 id: str = "", draggable: bool = False):
        if not -90 <= float(lat) <= 90:
            raise ValueError("lat must be between -90 and 90")
        if not -180 <= float(lon) <= 180:
            raise ValueError("lon must be between -180 and 180")
        self.lat = float(lat)
        self.lon = float(lon)
        self.title = title
        self.snippet = snippet
        self.color = color
        self.id = id or f"{lat:.5f},{lon:.5f}"
        self.draggable = bool(draggable)

    def to_dict(self) -> dict:
        return {"id": self.id, "lat": self.lat, "lon": self.lon,
                "title": self.title, "snippet": self.snippet,
                "color": self.color, "draggable": self.draggable}

    def __repr__(self) -> str:
        return f"Marker({self.lat}, {self.lon}, {self.title!r})"


class MapView(Widget):
    """An OpenStreetMap-backed map (no API key) or Google Maps when available.

    ::

        MapView(center=(24.86, 67.00), zoom=12,
                markers=[Marker(24.86, 67.00, title="Karachi")],
                on_tap=lambda e: add_pin(e.data["lat"], e.data["lon"]))
    """

    _widget_type = "MapView"
    PROVIDERS = ("osm", "google")
    TYPES = ("standard", "satellite", "terrain", "hybrid")

    def __init__(
        self,
        *,
        center: Sequence[float] = (0.0, 0.0),
        zoom: float = 13.0,
        markers: Optional[Sequence[Union[Marker, dict]]] = None,
        polyline: Optional[Sequence[Sequence[float]]] = None,
        provider: str = "osm",
        map_type: str = "standard",
        show_user: bool = False,
        controls: bool = True,
        interactive: bool = True,
        on_tap: Optional[Callable] = None,
        on_marker: Optional[Callable] = None,
        on_move: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        if provider not in self.PROVIDERS:
            raise ValueError(f"provider must be one of {self.PROVIDERS}")
        if map_type not in self.TYPES:
            raise ValueError(f"map_type must be one of {self.TYPES}")
        if not 1 <= float(zoom) <= 21:
            raise ValueError("zoom must be between 1 and 21")
        super().__init__(key=key, on_tap=on_tap, on_marker=on_marker,
                         on_move=on_move, **kwargs)
        self.center = (float(center[0]), float(center[1]))
        self.zoom = float(zoom)
        self.markers = [m if isinstance(m, Marker) else Marker(**m)
                        for m in (markers or [])]
        self.polyline = [[float(p[0]), float(p[1])] for p in (polyline or [])]
        self.provider = provider
        self.map_type = map_type
        self.show_user = bool(show_user)
        self.controls = bool(controls)
        self.interactive = bool(interactive)
        self.style.setdefault("width", "match")
        self.style.setdefault("height", kwargs.pop("height", 280))

    def add_marker(self, marker: Marker) -> "MapView":
        self.markers.append(marker)
        return self

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "lat": self.center[0],
            "lon": self.center[1],
            "zoom": self.zoom,
            "markers": [m.to_dict() for m in self.markers] or None,
            "polyline": self.polyline or None,
            "provider": self.provider,
            "mapType": self.map_type,
            "showUser": self.show_user or None,
            "controls": self.controls,
            "interactive": self.interactive,
        }))
        return props


# ──────────────────────────────────────────────────────────────────────────
# Rich text
# ──────────────────────────────────────────────────────────────────────────


class Span:
    """A styled run of text inside :class:`RichText`."""

    __slots__ = ("text", "color", "size", "weight", "italic", "underline",
                 "strike", "link", "bg", "mono")

    def __init__(self, text: str, *, color: Optional[str] = None,
                 size: Optional[float] = None, weight: Optional[int] = None,
                 italic: bool = False, underline: bool = False,
                 strike: bool = False, link: str = "",
                 bg: Optional[str] = None, mono: bool = False):
        self.text = str(text)
        self.color = color
        self.size = size
        self.weight = weight
        self.italic = bool(italic)
        self.underline = bool(underline) or bool(link)
        self.strike = bool(strike)
        self.link = link
        self.bg = bg
        self.mono = bool(mono)

    def to_dict(self) -> dict:
        return _clean({
            "text": self.text, "color": self.color, "size": self.size,
            "weight": self.weight, "italic": self.italic or None,
            "underline": self.underline or None, "strike": self.strike or None,
            "link": self.link or None, "bg": self.bg, "mono": self.mono or None,
        })

    def __repr__(self) -> str:
        return f"Span({self.text!r})"


class RichText(Widget):
    """Mixed-style text in a single native ``TextView`` (spans, not layouts).

    ::

        RichText([
            Span("Signed in as "),
            Span("ada@example.com", weight=700),
            Span(" — sign out", link="app://signout"),
        ], on_link=lambda e: route(e.data["link"]))
    """

    _widget_type = "RichText"

    def __init__(
        self,
        spans: Optional[Sequence[Union[Span, str, dict]]] = None,
        *,
        size: float = 14,
        color: str = Colors.TEXT,
        align: str = "left",
        line_height: Optional[float] = None,
        max_lines: Optional[int] = None,
        selectable: bool = False,
        on_link: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_link=on_link, **kwargs)
        self.spans: list[Span] = []
        for span in spans or []:
            self.add(span)
        self.size = float(size)
        self.color = color
        self.align = align
        self.line_height = line_height
        self.max_lines = max_lines
        self.selectable = bool(selectable)

    def add(self, span: Union[Span, str, dict]) -> "RichText":
        if isinstance(span, Span):
            self.spans.append(span)
        elif isinstance(span, dict):
            self.spans.append(Span(**span))
        else:
            self.spans.append(Span(str(span)))
        return self

    @property
    def text(self) -> str:
        """The plain-text content, spans flattened."""
        return "".join(span.text for span in self.spans)

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "spans": [s.to_dict() for s in self.spans],
            "size": self.size,
            "color": self.color,
            "align": self.align,
            "lineHeight": self.line_height,
            "maxLines": self.max_lines,
            "selectable": self.selectable or None,
        }))
        return props


_MD_INLINE = re.compile(
    r"(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|`[^`]+`|~~[^~]+~~|"
    r"\[[^\]]+\]\([^)]+\))")


class Markdown(Widget):
    """Render a Markdown subset — headings, lists, code, links, emphasis.

    The parsing happens in Python (predictable, testable, no WebView); the
    device receives ready-made styled blocks.
    """

    _widget_type = "Markdown"

    def __init__(
        self,
        source: str = "",
        *,
        size: float = 14,
        color: str = Colors.TEXT,
        code_bg: str = Colors.SURFACE_VARIANT,
        link_color: str = Colors.PRIMARY,
        selectable: bool = True,
        on_link: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_link=on_link, **kwargs)
        self.source = str(source)
        self.size = float(size)
        self.color = color
        self.code_bg = code_bg
        self.link_color = link_color
        self.selectable = bool(selectable)

    # ── parsing ──────────────────────────────────────────────────────────

    def blocks(self) -> list[dict]:
        """The parsed document: a list of ``{"kind", ...}`` blocks."""
        blocks: list[dict] = []
        lines = self.source.splitlines()
        index = 0
        while index < len(lines):
            line = lines[index]
            stripped = line.strip()

            if stripped.startswith("```"):
                language = stripped[3:].strip()
                index += 1
                body: list[str] = []
                while index < len(lines) and not lines[index].strip().startswith("```"):
                    body.append(lines[index])
                    index += 1
                index += 1
                blocks.append({"kind": "code", "language": language,
                               "text": "\n".join(body)})
                continue

            if not stripped:
                index += 1
                continue

            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                blocks.append({"kind": "heading", "level": min(level, 6),
                               "spans": self._inline(stripped[level:].strip())})
                index += 1
                continue

            if stripped.startswith(">"):
                blocks.append({"kind": "quote",
                               "spans": self._inline(stripped[1:].strip())})
                index += 1
                continue

            if re.match(r"^([-*_])\1{2,}$", stripped.replace(" ", "")):
                blocks.append({"kind": "rule"})
                index += 1
                continue

            bullet = re.match(r"^[-*+]\s+(.*)$", stripped)
            ordered = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
            if bullet or ordered:
                items = []
                is_ordered = ordered is not None
                while index < len(lines):
                    current = lines[index].strip()
                    match = (re.match(r"^(\d+)[.)]\s+(.*)$", current)
                             if is_ordered else
                             re.match(r"^[-*+]\s+(.*)$", current))
                    if not match:
                        break
                    text = match.group(2) if is_ordered else match.group(1)
                    checked = None
                    task = re.match(r"^\[([ xX])\]\s+(.*)$", text)
                    if task:
                        checked = task.group(1).lower() == "x"
                        text = task.group(2)
                    items.append({"spans": self._inline(text),
                                  "checked": checked})
                    index += 1
                blocks.append({"kind": "list", "ordered": is_ordered,
                               "items": items})
                continue

            paragraph = [stripped]
            index += 1
            while index < len(lines) and lines[index].strip() and \
                    not re.match(r"^(#|>|```|[-*+]\s|\d+[.)]\s)",
                                 lines[index].strip()):
                paragraph.append(lines[index].strip())
                index += 1
            blocks.append({"kind": "paragraph",
                           "spans": self._inline(" ".join(paragraph))})
        return blocks

    def _inline(self, text: str) -> list[dict]:
        spans: list[dict] = []
        for part in _MD_INLINE.split(text):
            if not part:
                continue
            if part.startswith("**") and part.endswith("**"):
                spans.append(Span(part[2:-2], weight=700).to_dict())
            elif part.startswith("__") and part.endswith("__"):
                spans.append(Span(part[2:-2], weight=700).to_dict())
            elif part.startswith("~~") and part.endswith("~~"):
                spans.append(Span(part[2:-2], strike=True).to_dict())
            elif part.startswith("`") and part.endswith("`"):
                spans.append(Span(part[1:-1], mono=True,
                                  bg=self.code_bg).to_dict())
            elif (part.startswith("*") and part.endswith("*")) or \
                    (part.startswith("_") and part.endswith("_")):
                spans.append(Span(part[1:-1], italic=True).to_dict())
            elif part.startswith("[") and part.endswith(")"):
                label, _, href = part[1:-1].partition("](")
                spans.append(Span(label, link=href,
                                  color=self.link_color).to_dict())
            else:
                spans.append(Span(part).to_dict())
        return spans

    @property
    def text(self) -> str:
        """Plain text with the markup removed."""
        out = []
        for block in self.blocks():
            if block["kind"] == "code":
                out.append(block["text"])
            elif block["kind"] == "list":
                out.extend("".join(s["text"] for s in item["spans"])
                           for item in block["items"])
            elif "spans" in block:
                out.append("".join(s["text"] for s in block["spans"]))
        return "\n".join(out)

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "blocks": self.blocks(),
            "size": self.size,
            "color": self.color,
            "codeBg": self.code_bg,
            "linkColor": self.link_color,
            "selectable": self.selectable,
        })
        return props


# ──────────────────────────────────────────────────────────────────────────
# High-performance lists
# ──────────────────────────────────────────────────────────────────────────


class ReorderableList(Widget):
    """A list whose rows can be dragged into a new order.

    ``on_reorder`` receives an event whose data holds ``from`` and ``to``
    indices — reorder your own data and re-render::

        ReorderableList(rows, on_reorder=lambda e: move(e.data["from"],
                                                        e.data["to"]))
    """

    _widget_type = "ReorderableList"

    def __init__(
        self,
        children: Optional[Sequence[Widget]] = None,
        *,
        spacing: int = 0,
        handle: bool = True,
        long_press: bool = True,
        swipe_to_remove: bool = False,
        on_reorder: Optional[Callable] = None,
        on_remove: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, on_reorder=on_reorder, on_remove=on_remove,
                         **kwargs)
        for child in children or []:
            if not isinstance(child, Widget):
                raise TypeError("ReorderableList children must be widgets")
            self.children.append(child)
        self.spacing = int(spacing)
        self.handle = bool(handle)
        self.long_press = bool(long_press)
        self.swipe_to_remove = bool(swipe_to_remove)

    def reorder(self, items: list, source: int, target: int) -> list:
        """Helper that applies a reorder event to your own list."""
        moved = list(items)
        moved.insert(target, moved.pop(source))
        return moved

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "spacing": self.spacing or None,
            "handle": self.handle,
            "longPress": self.long_press,
            "swipeToRemove": self.swipe_to_remove or None,
        }))
        return props


class InfiniteList(Widget):
    """A virtualised, endlessly scrolling list backed by ``RecyclerView``.

    Only the visible window is rendered. When the user approaches the end,
    ``on_load_more`` fires and you append the next page::

        InfiniteList(rows, has_more=cursor is not None, loading=busy,
                     on_load_more=fetch_next_page)

    Unlike ``ListView`` this never serialises off-screen rows, so a 50 000
    item feed costs the same as a 20 item one.
    """

    _widget_type = "InfiniteList"

    def __init__(
        self,
        children: Optional[Sequence[Widget]] = None,
        *,
        has_more: bool = False,
        loading: bool = False,
        threshold: int = 5,
        window: int = 40,
        spacing: int = 0,
        empty: Optional[Widget] = None,
        on_load_more: Optional[Callable] = None,
        on_scroll: Optional[Callable] = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        if int(threshold) < 1:
            raise ValueError("threshold must be at least 1")
        if int(window) < 1:
            raise ValueError("window must be at least 1")
        super().__init__(key=key, on_load_more=on_load_more,
                         on_scroll=on_scroll, **kwargs)
        rows = list(children or [])
        for child in rows:
            if not isinstance(child, Widget):
                raise TypeError("InfiniteList children must be widgets")
        self.total = len(rows)
        self.window = int(window)
        # Virtualisation: only the first *window* rows cross the bridge; the
        # rest arrive as the user scrolls and the app appends more.
        self.children = rows[: self.window]
        self.truncated = self.total > self.window
        self.has_more = bool(has_more) or self.truncated
        self.loading = bool(loading)
        self.threshold = int(threshold)
        self.spacing = int(spacing)
        if empty is not None:
            empty.key = f"{self.key}_empty"
            empty._auto_key = False
            self.empty = empty
            if not rows:
                self.children = [empty]
        else:
            self.empty = None

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update(_clean({
            "hasMore": self.has_more or None,
            "loading": self.loading or None,
            "threshold": self.threshold,
            "window": self.window,
            "total": self.total,
            "spacing": self.spacing or None,
            "virtualized": True,
        }))
        return props
