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


class TestStarterShowcaseScreen(TestStarterAppEndToEnd):
    """The v1.2 showcase screen of the generated starter app."""

    def open_showcase(self):
        self.device.click("to_showcase")
        self.assertTrue(self.device.wait_for_text("Showcase"))

    def test_showcase_is_reachable_and_renders_tabs(self):
        self.open_showcase()
        tabs = self.device.root.find("showcase_tabs")
        self.assertIsNotNone(tabs)
        labels = [t["label"] for t in tabs.props["tabs"]]
        self.assertEqual(labels, ["Components", "Data", "Actions"])
        # Only the selected tab's body is rendered.
        self.assertIn("Swipe me away", self.device.texts)
        self.assertNotIn("Weekly taps", self.device.texts)

    def test_switching_tabs_swaps_the_body(self):
        self.open_showcase()
        self.device.change("showcase_tabs", 1)
        self.assertTrue(self.device.wait_for_text("Weekly taps"))
        chart = self.device.root.find("showcase_chart")
        self.assertEqual(chart.props["kind"], "bar")
        self.assertEqual(len(chart.props["values"]), 7)

        self.device.change("showcase_tabs", 2)
        self.assertTrue(self.device.wait_for_text("Native power, from Python."))

    def test_filter_chips_toggle(self):
        self.open_showcase()
        chip = self.device.root.find("chip_Flutter")
        self.assertFalse(chip.props.get("selected"))
        self.device.send_event("change", "chip_Flutter", {"selected": True})
        self.assertTrue(self.device.wait_for(
            lambda d: d.root.find("chip_Flutter").props.get("selected")))

    def test_rating_updates_label(self):
        self.open_showcase()
        self.device.change("showcase_rating", 2.5)
        self.assertTrue(self.device.wait_for_text("You rated this 2.5/5"))

    def test_dialog_and_storage_calls_reach_the_device(self):
        self.open_showcase()
        self.device.change("showcase_tabs", 2)
        self.assertTrue(self.device.wait_for_text("Confirm dialog"))

        self.device.on_command("dialog", True)
        self.device.click("dialog_btn")
        request = self.device.wait_for_request("dialog")
        self.assertEqual(request["kind"], "confirm")
        self.assertTrue(self.device.wait_for_command("toast"))

        self.device.on_command("prefs_set", True)
        self.device.on_command("vibrate", True)
        self.device.click("storage_btn")
        self.assertEqual(self.device.wait_for_request("prefs_set")["key"], "note")
        self.assertTrue(self.device.wait_for_command("snackbar"))

    def test_gestures_on_the_actions_tab(self):
        self.open_showcase()
        self.device.change("showcase_tabs", 2)
        self.assertTrue(self.device.wait_for_text("Double-tap or swipe me"))
        box = self.device.root.find("gesture_box")
        self.assertEqual(box.props["gestures"],
                         ["double_tap", "swipe_left", "swipe_right"])
        self.device.gesture("gesture_box", "double_tap")
        self.assertTrue(self.device.wait_for_command("toast"))

    def test_back_from_showcase_returns_home(self):
        self.open_showcase()
        self.device.back()
        self.assertTrue(self.device.wait_for_command("back_result"))
        handled = [c for c in self.device.commands
                   if c.get("cmd") == "back_result"][-1]
        self.assertTrue(handled["handled"])
        self.assertTrue(self.device.wait_for_text("taps so far"))
