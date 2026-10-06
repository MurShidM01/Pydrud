"""Cross-platform neutrality assertions.

These tests verify that the widget tree, style engine, diff engine,
protocol and the (future) PSS engine can be imported and exercised with
no Android-specific module reachable from them. A violation here means
some core module quietly depends on the Android toolchain and would
crash on an iOS client.
"""
from __future__ import annotations

import importlib
import sys

import pytest


# Modules that are *allowed* to depend on Android — they live outside core.
_ANDROID_MODULES = frozenset({
    "pydrud.android",
    "pydrud.commands.builder",
    "pydrud.commands.release",
    "pydrud.commands.project.scaffold",
    "pydrud.commands.project.sync",
    "pydrud.commands.project.templates",
    "pydrud.commands.project.bundle",
    "pydrud.commands.project.python_runtime",
    "pydrud.commands.project.paths",
    "pydrud.commands.project_config",
    "pydrud.commands.doctor",
    "pydrud.commands.devrunner",
})


def _android_dependent_modules(mod: object) -> list[str]:
    """Return names of Android-only modules transitively loaded by *mod*."""
    visited: set[str] = set()
    queue: list[str] = [mod.__name__]
    leaks: list[str] = []

    while queue:
        name = queue.pop(0)
        if name in visited:
            continue
        visited.add(name)
        if name in _ANDROID_MODULES:
            continue  # expected
        m = sys.modules.get(name)
        if m is None:
            continue
        for attr_name in dir(m):
            try:
                attr = getattr(m, attr_name)
            except Exception:
                continue
            if not (hasattr(attr, "__module__")
                    and isinstance(attr.__module__, str)):
                continue
            mod_name = attr.__module__
            if (mod_name.startswith("pydrud.android")
                    or mod_name in _ANDROID_MODULES):
                leaks.append(f"{name}.{attr_name} ({mod_name})")
                continue
            if mod_name.startswith("pydrud.") and mod_name not in visited:
                queue.append(mod_name)
    return leaks


class TestCrossPlatformNeutrality:
    """Core and PSS must have no Android dependency."""

    _CORE_MODULES = [
        "pydrud.core.bridge",
        "pydrud.core.controllers",
        "pydrud.core.diff",
        "pydrud.core.elements",
        "pydrud.core.events",
        "pydrud.core.errors",
        "pydrud.core.protocol",
        "pydrud.core.qr",
        "pydrud.core.results",
        "pydrud.core.responsive",
        "pydrud.core.state",
        "pydrud.core.store",
        "pydrud.core.subscriptions",
        "pydrud.core.tasks",
        "pydrud.core.watcher",
        "pydrud.core.styles",
        "pydrud.core.styles.schema",
        "pydrud.widgets.base",
        "pydrud.widgets.styling",
    ]

    def test_core_imports_are_android_free(self) -> None:
        """Every listed core module can be imported without dragging in Android."""
        for mod_name in self._CORE_MODULES:
            # Force a fresh import so previous test state doesn't leak.
            if mod_name in sys.modules:
                del sys.modules[mod_name]
            mod = importlib.import_module(mod_name)
            leaks = _android_dependent_modules(mod)
            assert not leaks, (
                f"Module {mod_name!r} pulls in Android-dependent symbols: "
                + "; ".join(leaks)
            )

    def test_pss_schema_is_android_free(self) -> None:
        """The PSS schema (style vocabulary) has no Android deps."""
        from pydrud.core.styles.schema import VALID_STYLE_KEYS, KEY_KIND
        from pydrud.core.styles import normalize_key

        assert len(VALID_STYLE_KEYS) > 0
        assert isinstance(KEY_KIND, dict)
        assert normalize_key("text-align") == "textAlign"
        assert normalize_key("border-radius") == "borderRadius"
        assert normalize_key("width") == "width"
        assert normalize_key("unknown-prop") is None

    def test_widget_base_has_no_android_deps(self) -> None:
        """Widget.to_dict / _freeze_props / diff fingerprint are neutral."""
        from pydrud.widgets.base import Widget, assign_stable_keys

        root = Widget(key="root", style={"bg": "#FF000000"})
        child = Widget(key="child", style={"color": "#FFFFFFFF"})
        root.children.append(child)

        assign_stable_keys(root)
        assert root.key == "root"
        assert child.key == "root.0.Widget"

        d = root.to_dict()
        assert d["type"] == "Widget"
        assert d["style"]["bg"] == "#FF000000"

    def test_diff_is_android_free(self) -> None:
        """TreeDiff works without any Android machinery."""
        from pydrud.core.diff import TreeDiff
        from pydrud.widgets.base import Widget

        old = Widget(key="a", style={"bg": "#FF000000"})
        new = Widget(key="a", style={"bg": "#FF111111"})

        patches = TreeDiff.diff(old, new)
        assert len(patches) == 1
        assert patches[0].op == "update"
        assert patches[0].style == {"bg": "#FF111111"}
