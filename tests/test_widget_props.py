"""
Every widget property a Python widget serialises should mean something to
the native renderer.

When it does not, the app silently ignores it — the hardest kind of bug to
notice, because nothing fails. The ones that exist today are pinned in
``NATIVE_IGNORED_PROPS``; this test asserts the ledger is exact in both
directions, so the set can only shrink on purpose.
"""

from __future__ import annotations

import inspect
import os
import unittest

from pydrud.compatibility import NATIVE_IGNORED_PROPS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "pydrud", "android", "templates", "android")
MODULES = ("basic", "layout", "material", "advanced", "forms")


def java_source() -> str:
    parts = []
    for name in sorted(os.listdir(TEMPLATES)):
        if name.endswith(".j2"):
            with open(os.path.join(TEMPLATES, name), encoding="utf-8") as fh:
                parts.append(fh.read())
    return "".join(parts)


def serialised_props() -> dict:
    """``{widget type: {prop names}}`` for every default-constructible widget."""
    found: dict = {}
    for module in MODULES:
        mod = __import__(f"pydrud.widgets.{module}", fromlist=["x"])
        for _name, obj in vars(mod).items():
            if not (inspect.isclass(obj)
                    and isinstance(getattr(obj, "_widget_type", None), str)
                    and hasattr(obj, "_serialise_props")):
                continue
            instance = None
            for args in ((), ("x",)):
                try:
                    instance = obj(*args)
                    break
                except Exception:
                    continue
            if instance is None:
                continue
            try:
                props = instance._serialise_props()
            except Exception:
                continue
            if isinstance(props, dict):
                found.setdefault(obj._widget_type, set()).update(props)
    return found


class TestWidgetPropCoverage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.java = java_source()
        cls.props = serialised_props()

    def test_widgets_are_discoverable(self):
        self.assertGreater(len(self.props), 30, "widget scan found too little")

    def test_no_undocumented_ignored_props(self):
        surprises = {}
        for widget, props in sorted(self.props.items()):
            known = set(NATIVE_IGNORED_PROPS.get(widget, ()))
            ignored = {p for p in props if f'"{p}"' not in self.java}
            extra = sorted(ignored - known)
            if extra:
                surprises[widget] = extra
        self.assertEqual(
            {}, surprises,
            "these props are serialised but never read natively — implement "
            f"them or add them to NATIVE_IGNORED_PROPS: {surprises}")

    def test_ledger_has_no_stale_entries(self):
        stale = {}
        for widget, props in NATIVE_IGNORED_PROPS.items():
            handled = sorted(p for p in props if f'"{p}"' in self.java)
            if handled:
                stale[widget] = handled
        self.assertEqual(
            {}, stale,
            "now handled natively, remove from NATIVE_IGNORED_PROPS: "
            f"{stale}")

    def test_ledger_only_mentions_real_widgets(self):
        unknown = sorted(set(NATIVE_IGNORED_PROPS) - set(self.props))
        self.assertEqual([], unknown,
                         "NATIVE_IGNORED_PROPS names unknown widgets: "
                         + ", ".join(unknown))


if __name__ == "__main__":
    unittest.main()
