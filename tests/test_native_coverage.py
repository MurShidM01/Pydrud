"""
The Python API and the generated Java runtime must agree.

Two silent-failure modes used to slip through every other test:

* a Python service sends a command no Java class handles — the
  :class:`~pydrud.core.results.Result` never settles and the app hangs;
* the Java side emits an event ``App._handle_event`` ignores — the feature
  looks wired up but nothing happens.

Both are structural, so they can be checked statically.
"""

from __future__ import annotations

import os
import re
import unittest

from pydrud.services.native import UNIMPLEMENTED_COMMANDS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "pydrud", "android", "templates", "android")

#: Python modules that talk to the bridge.
SENDERS = [
    os.path.join("pydrud", "runtime", "app.py"),
    os.path.join("pydrud", "runtime", "page.py"),
    os.path.join("pydrud", "runtime", "_bridge.py"),
    os.path.join("pydrud", "services", "native.py"),
    os.path.join("pydrud", "runtime", "navigation.py"),
    os.path.join("pydrud", "data", "database.py"),
    os.path.join("pydrud", "commands", "packages.py"),
]

#: Commands the bridge answers structurally rather than by name.
INTERNAL = {"render", "full_render", "patch", "theme", "job_result"}


def read(path: str) -> str:
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return handle.read()


def java_source() -> str:
    return "".join(
        read(os.path.join("pydrud", "android", "templates", "android", name))
        for name in sorted(os.listdir(TEMPLATES)) if name.endswith(".java.j2")
    )


def python_commands() -> set:
    pattern = re.compile(
        r'(?:_invoke|_send|invoke|encode_command)\(\s*"([a-z][a-z0-9_]*)"')
    found: set = set()
    for module in SENDERS:
        found |= set(pattern.findall(read(module)))
    return found - INTERNAL


class TestNativeCommandCoverage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.java = java_source()
        cls.commands = python_commands()

    def test_commands_are_handled_or_declared_unimplemented(self):
        unhandled = {cmd for cmd in self.commands
                     if f'"{cmd}"' not in self.java}
        surprises = sorted(unhandled - UNIMPLEMENTED_COMMANDS)
        self.assertEqual(
            [], surprises,
            "these Python commands reach no Java handler — implement them or "
            "add them to UNIMPLEMENTED_COMMANDS: " + ", ".join(surprises))

    def test_unimplemented_list_has_no_stale_entries(self):
        """Once a command is implemented natively, drop it from the list."""
        stale = sorted(cmd for cmd in UNIMPLEMENTED_COMMANDS
                       if f'"{cmd}"' in self.java)
        self.assertEqual([], stale,
                         "now handled in Java, remove from "
                         "UNIMPLEMENTED_COMMANDS: " + ", ".join(stale))

    def test_unimplemented_commands_are_all_reachable_from_python(self):
        orphans = sorted(UNIMPLEMENTED_COMMANDS - self.commands)
        self.assertEqual([], orphans,
                         "listed but no longer sent by any Python API: "
                         + ", ".join(orphans))

    def test_unknown_commands_get_an_error_reply(self):
        """A command nobody handles must fail the pending Result."""
        bridge = read(os.path.join(
            "pydrud", "android", "templates", "android",
            "BridgeService.java.j2"))
        self.assertIn("replyUnsupported", bridge)
        self.assertIn("unsupported native command", bridge)


class TestNativeEventCoverage(unittest.TestCase):

    def test_every_native_event_is_handled_in_python(self):
        java = java_source()
        events = set(re.findall(r'sendEvent\(\s*"([a-z_]+)"', java))
        main = read(os.path.join("pydrud", "runtime", "app.py"))
        missing = sorted(e for e in events if f'"{e}"' not in main)
        self.assertEqual(
            [], missing,
            "native events with no handler in App._handle_event: "
            + ", ".join(missing))


class TestWidgetCoverage(unittest.TestCase):

    def test_every_widget_type_is_rendered_natively(self):
        import inspect

        java = "".join(
            read(os.path.join("pydrud", "android", "templates", "android", n))
            for n in sorted(os.listdir(TEMPLATES)) if n.endswith(".j2"))
        types = set()
        for module in ("basic", "layout", "material", "advanced", "forms"):
            mod = __import__(f"pydrud.widgets.{module}", fromlist=["x"])
            for _name, obj in vars(mod).items():
                widget_type = getattr(obj, "_widget_type", None)
                if (inspect.isclass(obj) and isinstance(widget_type, str)
                        and widget_type != "Widget"):
                    types.add(widget_type)
        missing = sorted(t for t in types if f'"{t}"' not in java)
        self.assertEqual([], missing,
                         "widgets with no native renderer: " + ", ".join(missing))


class TestPreviewParity(unittest.TestCase):
    """`tools/preview_ui.py` must agree with the renderer about layout.

    The previewer exists to show what the device will draw; when its
    fill-width list drifts from ``ViewFactory.fillsWidthByDefault`` it
    quietly lies about every screen.
    """

    #: Types the renderer stretches through a dedicated branch rather than
    #: the switch (they fill both axes).
    SPECIAL = {"Stack", "Center"}

    def test_fill_width_lists_match(self):
        java = read(os.path.join(
            "pydrud", "android", "templates", "android", "ViewFactory.java.j2"))
        body = re.search(
            r"fillsWidthByDefault\(String type\) \{(.*?)\n    \}",
            java, re.S)
        self.assertIsNotNone(body, "fillsWidthByDefault() not found")
        native = set(re.findall(r'case "(\w+)"', body.group(1)))

        preview = read(os.path.join("tools", "preview_ui.py"))
        listing = re.search(r"FILL_BY_DEFAULT = \{(.*?)\}", preview, re.S)
        self.assertIsNotNone(listing, "FILL_BY_DEFAULT not found")
        previewed = set(re.findall(r'"(\w+)"', listing.group(1)))

        self.assertEqual(set(), native - previewed,
                         "renderer stretches types the previewer does not")
        self.assertEqual(set(), previewed - native - self.SPECIAL,
                         "previewer stretches types the renderer does not")


if __name__ == "__main__":
    unittest.main()
