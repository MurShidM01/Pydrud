"""Cross-platform neutrality assertions.

These tests verify that the widget tree, style engine, diff engine,
protocol and the (future) PSS engine can be imported and exercised with
no Android-specific module reachable from them. A violation here means
some core module quietly depends on the Android toolchain and would
crash on an iOS client.
"""
from __future__ import annotations

import importlib
import json
import os
import pkgutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def _probe(module_names: list[str]) -> dict[str, list[str]]:
    """Import each module and list platform-specific symbols reachable from it.

    This is the child half of :func:`_leaks_in_fresh_interpreter`; it is what
    runs when this file is executed as a script.
    """
    report = {
        name: _android_dependent_modules(importlib.import_module(name))
        for name in module_names
    }
    report["__loaded_android_modules__"] = sorted(
        name for name in sys.modules
        if name == "pydrud.android"
        or name.startswith("pydrud.android.")
        or name == "pydrud.platforms.android"
        or name.startswith("pydrud.platforms.android.")
    )
    return report


def _all_core_modules() -> list[str]:
    """Discover every Python module below ``pydrud/core`` for isolation tests."""
    import pydrud.core

    discovered = [pydrud.core.__name__]
    discovered.extend(
        module.name for module in pkgutil.walk_packages(
            pydrud.core.__path__, prefix="pydrud.core.")
    )
    return sorted(set(discovered))


def _leaks_in_fresh_interpreter(
        module_names: list[str]) -> dict[str, list[str]]:
    """Run :func:`_probe` in a brand-new interpreter.

    "Imported on its own, with no previous test state" has to be answered by
    a process that has none. It must *not* be answered by deleting the modules
    from ``sys.modules`` and importing them again here: that leaves two copies
    of ``pydrud.core.responsive``, ``pydrud.core.tasks``,
    ``pydrud.widgets.styling`` and friends in the test process. Everything
    bound at import time (``from pydrud import MediaQuery``) then keeps the old
    copy while everything resolved at call time gets the new one, and
    unrelated tests start failing depending on whether this one ran first.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (ROOT, env.get("PYTHONPATH")) if p)
    result = subprocess.run(
        [sys.executable, os.path.abspath(__file__), *module_names],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        f"the neutrality probe crashed:\n{result.stderr}")
    return json.loads(result.stdout.strip().splitlines()[-1])


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
        # A fresh interpreter, so previous test state cannot leak in and the
        # modules this process has already loaded are never touched.
        module_names = sorted(set(self._CORE_MODULES + _all_core_modules()))
        report = _leaks_in_fresh_interpreter(module_names)
        for mod_name in module_names:
            leaks = report[mod_name]
            assert not leaks, (
                f"Module {mod_name!r} pulls in Android-dependent symbols: "
                + "; ".join(leaks)
            )
        assert report["__loaded_android_modules__"] == [], (
            "Importing the complete core/PSS surface loaded a platform adapter: "
            + ", ".join(report["__loaded_android_modules__"])
        )

    def test_neutrality_probe_leaves_loaded_modules_alone(self) -> None:
        """Regression: the probe once re-imported core modules in-process.

        Re-importing split ``pydrud.core.responsive`` (``MediaQuery``),
        ``pydrud.core.tasks`` (``GLOBAL_JOBS``) and ``pydrud.widgets.styling``
        (``Border``) in two, which broke the five tests that happened to run
        after it (``test_container_border_property``, the adaptive scaffold,
        both ``AppMetricsEvents`` tests and ``test_standalone_job_decorator``).
        """
        before = {name: importlib.import_module(name)
                  for name in self._CORE_MODULES}

        self.test_core_imports_are_android_free()

        for name, module in before.items():
            assert sys.modules[name] is module, (
                f"{name} was replaced in sys.modules; every later "
                f"call-time import of it now resolves to a second copy")
            parent, _, child = name.rpartition(".")
            if parent:
                assert getattr(sys.modules[parent], child, module) is module, (
                    f"{parent}.{child} no longer points at the loaded module")

        import pydrud
        from pydrud.core.responsive import MediaQuery
        from pydrud.core.tasks import GLOBAL_JOBS
        from pydrud.widgets.styling import Border

        assert pydrud.MediaQuery is MediaQuery
        assert pydrud.Border is Border
        assert pydrud.core.tasks.GLOBAL_JOBS is GLOBAL_JOBS

    def test_public_runtime_import_does_not_load_android_adapters(self) -> None:
        """Importing App is safe for host preview before target selection."""
        report = _leaks_in_fresh_interpreter([
            "pydrud", "pydrud.runtime.app", "pydrud.runtime._lifecycle",
        ])
        assert report["__loaded_android_modules__"] == []

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
        child = Widget(style={"color": "#FFFFFFFF"})  # no explicit key
        root.children.append(child)

        assign_stable_keys(root)
        assert root.key == "root"
        assert child.key == "root.0Widget"  # structural key: root.<index><Type>

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


if __name__ == "__main__":  # the child process of _leaks_in_fresh_interpreter
    print(json.dumps(_probe(sys.argv[1:])))
