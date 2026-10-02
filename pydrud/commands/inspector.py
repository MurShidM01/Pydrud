"""
``pydrud inspect`` — a devtools window onto a running app.

The bridge is a plain NDJSON socket, so the inspector simply attaches as a
second listener: it can dump the current widget tree, stream every event
and command with timings, and report render statistics — no instrumentation
in your app, nothing to enable in the build.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from typing import Optional

from pydrud.utils import tui

BOX = {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│",
       "t": "├", "l": "└"}


def _flatten(node: dict, depth: int = 0, out: Optional[list] = None,
             prefix: str = "") -> list[str]:
    out = [] if out is None else out
    kind = node.get("type", "?")
    key = node.get("key", "")
    props = node.get("props") or {}
    label = props.get("value") or props.get("title") or props.get("text") or ""
    if isinstance(label, str) and len(label) > 28:
        label = label[:27] + "…"
    events = ",".join(node.get("events") or [])
    line = f"{prefix}{kind}"
    if label:
        line += f"  '{label}'"
    line += f"   [{key}]"
    if events:
        line += f"  ({events})"
    out.append(line)
    children = node.get("children") or []
    for index, child in enumerate(children):
        last = index == len(children) - 1
        branch = "  " * depth + ("└─ " if last else "├─ ")
        _flatten(child, depth + 1, out, branch)
    return out


def count_nodes(node: dict) -> int:
    return 1 + sum(count_nodes(child) for child in node.get("children") or [])


def summarise(tree: dict) -> dict:
    """Node count, depth, widget histogram and how many nodes have handlers."""
    kinds: dict[str, int] = {}
    interactive = 0
    deepest = 0

    def walk(node: dict, depth: int) -> None:
        nonlocal interactive, deepest
        deepest = max(deepest, depth)
        kinds[node.get("type", "?")] = kinds.get(node.get("type", "?"), 0) + 1
        if node.get("has_events") or node.get("events"):
            interactive += 1
        for child in node.get("children") or []:
            walk(child, depth + 1)

    walk(tree, 1)
    return {"nodes": sum(kinds.values()), "depth": deepest,
            "interactive": interactive,
            "widgets": dict(sorted(kinds.items(), key=lambda kv: -kv[1]))}


def render_tree(tree: dict) -> str:
    """Pretty, indented rendering of a serialised widget tree."""
    return "\n".join(_flatten(tree))


def run_inspector(*, port: int = 8595, dump_tree: bool = False,
                  follow: bool = False, host: str = "127.0.0.1",
                  timeout: float = 5.0) -> int:
    """Attach to a running app. Returns a process exit code."""
    print(tui.render_command_header(
        "inspect",
        "Widget tree and bridge traffic",
        subtitle="Inspecting application structure, events and render activity",
        details=(("Endpoint", f"{host}:{port}"),
                 ("Mode", "follow" if follow else "snapshot")),
    ))
    local_tree = _local_tree()
    if local_tree is not None and not follow:
        _report_local(local_tree, dump_tree)
        return 0

    try:
        connection = socket.create_connection((host, port), timeout=timeout)
    except OSError as exc:
        print(tui.error_badge(f"No app listening on {host}:{port} ({exc})."))
        print(tui.info_badge(
            "Start with 'pydrud run', or inspect from inside a project."))
        return 1

    print(tui.ok_badge(f"Attached to {host}:{port} — Ctrl-C to detach"))
    print(tui.render_section("Live bridge traffic"))
    started = time.time()
    counts: dict[str, int] = {}
    try:
        buffer = b""
        while True:
            chunk = connection.recv(65536)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    message = json.loads(line.decode())
                except ValueError:
                    continue
                kind = message.get("cmd") or message.get("type") or "?"
                counts[kind] = counts.get(kind, 0) + 1
                if dump_tree and kind == "full_render":
                    print(render_tree(message.get("tree") or {}))
                    if not follow:
                        return 0
                elif follow:
                    stamp = f"{time.time() - started:7.2f}s"
                    print(f"  {stamp}  {kind:<14} "
                          f"{json.dumps(_trim(message))[:120]}")
    except KeyboardInterrupt:
        pass
    finally:
        connection.close()

    print(tui.render_section("Traffic summary"))
    if counts:
        print(tui.render_table(
            ("MESSAGE", "COUNT"),
            ((kind, count) for kind, count in
             sorted(counts.items(), key=lambda item: -item[1])),
        ))
    else:
        print(tui.neutral_badge("No bridge messages received."))
    return 0


def _trim(message: dict) -> dict:
    """Drop bulky payloads so the live log stays readable."""
    trimmed = dict(message)
    if "tree" in trimmed:
        trimmed["tree"] = f"<{count_nodes(trimmed['tree'])} nodes>"
    if "patches" in trimmed:
        trimmed["patches"] = f"<{len(trimmed['patches'])} patches>"
    return trimmed


def _local_tree() -> Optional[dict]:
    """Build the project's tree in-process (works with no device attached)."""
    src = os.path.join(os.getcwd(), "src")
    if not os.path.isdir(src):
        return None
    # An inspector embedded in a test runner or IDE may already have another
    # project's ``app`` package cached. Isolate this project for the render,
    # then restore the caller's modules afterwards.
    previous_app_modules = {
        name: module for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in previous_app_modules:
        sys.modules.pop(name, None)
    sys.path.insert(0, src)
    try:
        from pydrud import App

        module = __import__("app.main", fromlist=["x"])
        target = getattr(module, "main", None)
        router = getattr(module, "router", None)
        if target is None and router is not None:
            target = router.build_root()
        if target is None:
            return None
        app = App(target=target)
        if router is not None:
            app.attach_router(router)
        return app.build().to_dict()
    except Exception as exc:
        print(tui.warn_badge(f"Could not build the tree locally: {exc}"))
        return None
    finally:
        if src in sys.path:
            sys.path.remove(src)
        for name in [name for name in sys.modules
                     if name == "app" or name.startswith("app.")]:
            sys.modules.pop(name, None)
        sys.modules.update(previous_app_modules)


def _report_local(tree: dict, dump_tree: bool) -> None:
    stats = summarise(tree)
    print(tui.info_badge(
        "No running app detected — using a static local render."))
    if dump_tree:
        print(tui.render_section("Widget tree"))
        print(render_tree(tree))
    print(tui.render_section("Tree metrics"))
    print(tui.render_key_values((
        ("Nodes:", stats["nodes"]),
        ("Max depth:", stats["depth"]),
        ("Interactive:", f"{stats['interactive']} widget(s) with handlers"),
    )))
    print(tui.render_section("Widgets"))
    print(tui.render_table(
        ("WIDGET", "COUNT"),
        ((name, count) for name, count in list(stats["widgets"].items())[:12]),
    ))
    heavy = [name for name, count in stats["widgets"].items() if count > 200]
    if heavy:
        print(tui.warn_badge(
            f"{', '.join(heavy)} appears often — consider InfiniteList."))
    if stats["depth"] > 20:
        print(tui.warn_badge(
            "The tree is deep; flatten nested Containers to speed up diffing."))
