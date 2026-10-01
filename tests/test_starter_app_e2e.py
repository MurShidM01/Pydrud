"""
Full-app end-to-end test.

Scaffolds a real project with ``pydrud init``, imports the generated starter
app, runs it against :class:`FakeDevice` and drives it like a user would:
tapping the counter, adding and deleting to-dos, navigating to settings,
toggling switches and pressing the hardware back button.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

from pydrud import App
from pydrud.commands.project import create_project
from tests.fake_device import FakeDevice, run_app


class TestStarterAppEndToEnd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pydrud-e2e-")
        cls.cwd = os.getcwd()
        os.chdir(cls.tmp)
        create_project("tour_app", org="com.example")
        cls.src = os.path.join(cls.tmp, "tour_app", "src")
        sys.path.insert(0, cls.src)

    @classmethod
    def tearDownClass(cls):
        if cls.src in sys.path:
            sys.path.remove(cls.src)
        for mod in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
            del sys.modules[mod]
        os.chdir(cls.cwd)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        for mod in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
            del sys.modules[mod]
        import app.main as starter  # noqa: WPS433

        self.starter = starter
        self.device = FakeDevice().start()
        self.app = App(target=starter.router.build_root(), title="tour_app")
        self.app.attach_router(starter.router)
        starter.app = self.app  # the module-level handle used by refresh()
        run_app(self.app, self.device)
        # Initial render + the re-render triggered by the `ready` metrics.
        self.assertTrue(self.device.wait_for(lambda d: d.full_renders >= 2))

    def tearDown(self):
        self.app.stop()
        self.device.stop()

    # ── tests ─────────────────────────────────────────────────────────────

    def test_initial_screen_renders_full_tour(self):
        texts = self.device.texts
        self.assertIn("tour_app", texts)        # app bar title
        self.assertIn("taps so far", texts)
        self.assertIn("To-do", texts)
        self.assertIn("Nothing yet — add your first task.", texts)
        self.assertIsNotNone(self.device.root.find("fab"))

    def test_counter_button_and_fab(self):
        device = self.device
        device.click("tap_btn")
        self.assertTrue(device.wait_for(
            lambda d: d.root.find("counter_value").props["value"] == "1"))

        device.click("fab")
        self.assertTrue(device.wait_for(
            lambda d: d.root.find("counter_value").props["value"] == "2"))

        device.click("reset_btn")
        self.assertTrue(device.wait_for(
            lambda d: d.root.find("counter_value").props["value"] == "0"))
        self.assertTrue(device.wait_for_command("toast"))

    def test_todo_add_and_delete(self):
        device = self.device
        device.change("todo_input", "Buy milk")
        device.click("todo_add")
        self.assertTrue(device.wait_for_text("Buy milk"))

        device.change("todo_input", "Walk dog")
        device.click("todo_add")
        self.assertTrue(device.wait_for_text("Walk dog"))

        device.click("todo_del_Buy milk")
        self.assertTrue(device.wait_for(lambda d: "Buy milk" not in d.texts))
        self.assertIn("Walk dog", device.texts)

    def test_navigate_to_settings_and_back(self):
        device = self.device
        device.click("to_settings")
        self.assertTrue(device.wait_for_text("Settings"))

        device.change("dark_switch", True)
        self.assertTrue(device.wait_for_command("set_system_ui"))

        device.change("volume_slider", 80)
        self.assertTrue(device.wait_for(
            lambda d: d.root.find("volume_label").props["value"] == "Volume: 80"))

        device.change("agree_box", True)
        self.assertTrue(device.wait_for(
            lambda d: d.root.find("agree_box").props["checked"] is True))

        device.click("snack_btn")
        self.assertTrue(device.wait_for_command("snackbar"))

        # Hardware back returns to home and reports "handled".
        device.commands.clear()
        device.back()
        self.assertTrue(device.wait_for_text("taps so far"))
        self.assertTrue(device.wait_for_command("back_result"))
        result = [c for c in device.commands if c.get("cmd") == "back_result"][-1]
        self.assertTrue(result["handled"])

    def test_updates_stay_incremental(self):
        device = self.device
        before = device.full_renders
        for _ in range(5):
            device.click("tap_btn")
        self.assertTrue(device.wait_for(
            lambda d: d.root.find("counter_value").props["value"] == "5"))
        self.assertEqual(device.full_renders, before,
                         "counter taps should patch, not re-render the page")


if __name__ == "__main__":
    unittest.main()
