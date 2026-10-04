"""
Unit tests for Pydrud v2.0.2 fixes and enhancements.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from pydrud import (
    App, Canvas, Column, Container, Icons, IconButton, Router,
    Stack, Store, Text, job,
)
from pydrud.commands.analyzer import _check_icon_references, _check_shadowing_issues
from pydrud.core.diff import TreeDiff
from pydrud.core.tasks import GLOBAL_JOBS
from pydrud.testing import AppTester
from pydrud.widgets.base import assign_stable_keys


class TestTreeDiffKeylessReorder(unittest.TestCase):
    def test_keyless_reorder_generates_move_patches(self):
        old = Column(children=[
            Container(child=Text("First")),
            Container(child=Text("Second")),
        ])
        assign_stable_keys(old)

        new = Column(children=[
            Container(child=Text("Second")),
            Container(child=Text("First")),
        ])
        assign_stable_keys(new)

        patches = TreeDiff.diff(old, new)
        ops = [p.op for p in patches]
        self.assertIn("move", ops)
        self.assertNotIn("replace", ops)
        # Should not recreate or update the child text
        updates = [p for p in patches if p.op == "update"]
        self.assertEqual(len(updates), 0)


class TestCanvasMethodAliases(unittest.TestCase):
    def test_canvas_draw_aliases_record_ops(self):
        c = Canvas()
        c.draw_circle(0.5, 0.5, 0.2)
        c.draw_rect(0.1, 0.1, 0.3, 0.3)
        c.draw_line(0.0, 0.0, 1.0, 1.0)
        c.draw_oval(0.2, 0.2, 0.4, 0.6)
        c.draw_arc(0.5, 0.5, 0.3, start=0, sweep=90)
        c.draw_polygon([(0, 0), (1, 0), (0.5, 1)])
        c.draw_text("Hello", 0.5, 0.5)
        c.draw_image("res://img.png", 0, 0, 100, 100)
        c.draw_grid(2, 2)
        c.draw_pie([10, 20, 30])
        c.draw_sparkline([1, 5, 2, 8])

        ops = [op["op"] for op in c.ops]
        self.assertIn("circle", ops)
        self.assertIn("rect", ops)
        self.assertIn("line", ops)
        self.assertIn("oval", ops)
        self.assertIn("arc", ops)
        self.assertIn("path", ops)
        self.assertIn("text", ops)
        self.assertIn("image", ops)


class TestStoreDataCompatibility(unittest.TestCase):
    def test_store_data_access_and_mutation(self):
        store = Store({"score": 100, "difficulty": "easy"})
        self.assertEqual(store._data["score"], 100)
        self.assertEqual(store.data["difficulty"], "easy")

        store._data["score"] = 200
        self.assertEqual(store.get("score"), 200)

        # Direct setattr
        setattr(store, "_data", {"score": 300, "difficulty": "hard"})
        self.assertEqual(store.get("score"), 300)
        self.assertEqual(store.get("difficulty"), "hard")


class TestJobDecorator(unittest.TestCase):
    def test_standalone_job_decorator(self):
        @job("custom_sync")
        def sync_worker(inputs):
            return {"synced": True, "count": inputs.get("count", 0)}

        self.assertIn("custom_sync", GLOBAL_JOBS)
        app = App(target=lambda page: None)
        page = app._page
        result = page.background.run_job("custom_sync", {"count": 42})
        self.assertEqual(result, {"synced": True, "count": 42})
        self.assertIn("custom_sync", page.background.jobs)


class TestIconsExpansion(unittest.TestCase):
    def test_gaming_icons_exist(self):
        gaming_icons = [
            "ASTROPHYSICS", "GAMES", "GAMEPAD", "TOUCH_APP",
            "ANIMATION", "CANVAS", "STATE", "VIBRATION",
            "SCREEN_ROTATION", "ARROW_BACK", "ARROW_FORWARD",
        ]
        for name in gaming_icons:
            val = getattr(Icons, name)
            self.assertIsInstance(val, str)
            self.assertTrue(len(val) > 0)


class TestAppTesterConnectedAndRefresh(unittest.TestCase):
    def test_app_tester_connected_and_refresh(self):
        def build(page):
            page.add(Text("Running App", key="txt"))

        with AppTester(build) as tester:
            self.assertTrue(tester.connected)
            tester.refresh()
            self.assertTrue(tester.shows("Running App"))


class TestPageRouter(unittest.TestCase):
    def test_page_router_access(self):
        router = Router()
        router.define("home", lambda page: page.add(Text("Home")))
        router.initial("home")

        app = App(target=router.build_root())
        app.attach_router(router)

        self.assertIs(app.router, router)
        self.assertIs(app._page.router, router)


class TestAnalyzerChecks(unittest.TestCase):
    def test_shadowing_detection(self):
        with tempfile.TemporaryDirectory() as td:
            src_dir = os.path.join(td, "src")
            os.makedirs(os.path.join(src_dir, "app", "components"), exist_ok=True)
            with open(os.path.join(src_dir, "app", "components.py"), "w") as f:
                f.write("# components module\n")

            issues = _check_shadowing_issues(src_dir)
            self.assertTrue(len(issues) > 0)
            self.assertIn("Package shadowing", issues[0]["message"])

    def test_invalid_icon_detection(self):
        import ast
        code = "icon = Icons.NON_EXISTENT_ICON_XYZ"
        tree = ast.parse(code)
        issues = _check_icon_references(tree, "test.py")
        self.assertTrue(len(issues) > 0)
        self.assertIn("Invalid icon reference", issues[0]["message"])


class TestSquareQRCode(unittest.TestCase):
    def test_terminal_qr_is_square(self):
        from pydrud.commands.preview import terminal_qr
        from pydrud.core.preview import PreviewSession, build_preview_uri

        session = PreviewSession.create("com.example.preview", "Preview App")
        uri = build_preview_uri(session, "192.168.1.50", 8597)
        qr_str = terminal_qr(uri, ansi=False)
        lines = qr_str.splitlines()

        # In monospace terminal fonts, 1 line height is ~2 char widths.
        # Width in chars should be approximately 2x height in lines (width == height visually).
        width_chars = len(lines[0])
        height_lines = len(lines)
        visual_height = height_lines * 2

        self.assertGreater(width_chars, 0)
        self.assertGreater(height_lines, 0)
        self.assertAlmostEqual(width_chars, visual_height, delta=4)
        self.assertTrue(any("█▀▀▀▀▀█" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
