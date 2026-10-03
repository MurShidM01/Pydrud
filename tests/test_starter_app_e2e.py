"""
Full-app end-to-end test of the generated starter app.

Scaffolds a real project with ``pydrud init``, imports the generated
**Pydrud Native Playground**, runs it against :class:`FakeDevice` and
drives it like a user would: tapping the native service demos (toast,
snackbar, dialog, haptics, clipboard), typing into the components,
dragging the slider, incrementing the counter, pushing the details
screen and pressing the hardware back button.
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

    # ── helpers ───────────────────────────────────────────────────────────

    def counter(self) -> str:
        return self.device.root.find("counter_value").props["value"]

    def open_details(self) -> None:
        self.device.click("open_details")
        self.assertTrue(self.device.wait_for_text("This is a second screen"))

    # ── the playground screen ─────────────────────────────────────────────

    def test_initial_screen_renders_the_playground(self):
        texts = self.device.texts
        self.assertIn("tour_app", texts)                 # app bar title
        self.assertIn("Pydrud Native Playground", texts)  # hero branding
        self.assertIn("Native Android, powered by Python", texts)
        self.assertIn("NATIVE ANDROID", texts)           # section labels
        self.assertIn("COMPONENTS", texts)
        self.assertIn("STATE & INTERACTION", texts)
        self.assertIn("NAVIGATION", texts)
        # Every advertised demo control exists.
        for key in ("toast_btn", "snack_btn", "dialog_btn", "vibrate_btn",
                    "copy_btn", "share_btn", "device_btn", "perm_btn",
                    "name_input", "dark_switch", "like_box", "amount_slider",
                    "inc_btn", "dec_btn", "reset_btn", "open_details"):
            with self.subTest(key=key):
                self.assertIsNotNone(self.device.root.find(key))

    def test_counter_buttons_and_reset_snackbar(self):
        device = self.device
        device.click("inc_btn")
        self.assertTrue(device.wait_for(lambda d: self.counter() == "1"))
        device.click("inc_btn")
        self.assertTrue(device.wait_for(lambda d: self.counter() == "2"))
        device.click("dec_btn")
        self.assertTrue(device.wait_for(lambda d: self.counter() == "1"))

        device.click("reset_btn")
        self.assertTrue(device.wait_for(lambda d: self.counter() == "0"))
        self.assertTrue(device.wait_for_command("snackbar"))

    def test_typing_updates_the_greeting(self):
        device = self.device
        device.change("name_input", "Ada")
        self.assertTrue(device.wait_for(
            lambda d: d.root.find("greeting").props["value"] == "Hello, Ada 👋"))

    def test_slider_drives_the_label_and_progress_bar(self):
        device = self.device
        device.change("amount_slider", 80)
        self.assertTrue(device.wait_for(
            lambda d: d.root.find("amount_label").props["value"] == "80%"))
        self.assertTrue(device.wait_for(
            lambda d: d.root.find("amount_progress").props["value"] == 0.8))

    def test_dark_mode_switch_rethemes_natively(self):
        device = self.device
        device.change("dark_switch", True)
        # Theme changes reach the native layer as a palette + a mode switch.
        self.assertTrue(device.wait_for_command("theme_mode"))
        self.assertTrue(device.wait_for_command("theme"))

    def test_checkbox_toggles(self):
        device = self.device
        device.change("like_box", True)
        self.assertTrue(device.wait_for(
            lambda d: d.root.find("like_box").props["checked"] is True))

    def test_updates_stay_incremental(self):
        device = self.device
        before = device.full_renders
        for _ in range(5):
            device.click("inc_btn")
        self.assertTrue(device.wait_for(lambda d: self.counter() == "5"))
        self.assertEqual(device.full_renders, before,
                         "counter taps should patch, not re-render the page")


class TestPlaygroundNativeDemos(TestStarterAppEndToEnd):
    """Every Native Android tile produces a visible native command."""

    def test_toast_demo(self):
        self.device.click("toast_btn")
        self.assertTrue(self.device.wait_for_command("toast"))

    def test_snackbar_demo(self):
        self.device.click("snack_btn")
        self.assertTrue(self.device.wait_for_command("snackbar"))

    def test_dialog_demo_and_its_answer(self):
        self.device.on_command("dialog", True)
        self.device.click("dialog_btn")
        request = self.device.wait_for_request("dialog")
        self.assertEqual(request["kind"], "confirm")
        self.assertTrue(self.device.wait_for_command("toast"))

    def test_vibrate_demo(self):
        self.device.on_command("vibrate", True)
        self.device.click("vibrate_btn")
        self.assertTrue(self.device.wait_for_command("vibrate"))
        self.assertTrue(self.device.wait_for_command("toast"))

    def test_clipboard_demo(self):
        self.device.on_command("clipboard_set", True)
        self.device.click("copy_btn")
        request = self.device.wait_for_request("clipboard_set")
        self.assertIn("tour_app", request["text"])
        self.assertTrue(self.device.wait_for_command("toast"))

    def test_share_demo(self):
        self.device.click("share_btn")
        request = self.device.wait_for_request("share")
        self.assertEqual(request["kind"], "text")

    def test_device_info_demo_opens_a_dialog(self):
        self.device.on_command("device_info",
                               {"manufacturer": "Pydrud", "model": "Fake",
                                "sdk": 34})
        self.device.on_command("dialog", True)
        self.device.click("device_btn")
        self.assertEqual(self.device.wait_for_request("device_info")["cmd"],
                         "device_info")
        request = self.device.wait_for_request("dialog")
        self.assertEqual(request["kind"], "alert")
        self.assertIn("Pydrud Fake", request["message"])

    def test_permission_demo_reports_the_result(self):
        self.device.on_command(
            "permission_request",
            {"android.permission.POST_NOTIFICATIONS": True})
        self.device.click("perm_btn")
        request = self.device.wait_for_request("permission_request")
        self.assertIn("android.permission.POST_NOTIFICATIONS",
                      request["permissions"])
        self.assertTrue(self.device.wait_for_command("toast"))


class TestPlaygroundNavigation(TestStarterAppEndToEnd):
    """router.push / router.pop and the hardware back button."""

    def test_details_screen_opens_and_shares_state(self):
        self.device.click("inc_btn")
        self.assertTrue(self.device.wait_for(lambda d: self.counter() == "1"))

        self.open_details()
        self.assertIsNotNone(self.device.root.find("details_card"))
        self.assertIsNotNone(self.device.root.find("details_back"))
        # The shared counter State is visible on the pushed screen.
        tile = self.device.root.find("details_counter")
        self.assertIn("still 1", tile.props["subtitle"])

    def test_back_button_pops_to_the_playground(self):
        self.open_details()
        self.device.click("back_btn")
        self.assertTrue(self.device.wait_for_text("Pydrud Native Playground"))
        self.assertEqual(self.starter.router.current_route, "playground")

    def test_app_bar_arrow_pops_to_the_playground(self):
        self.open_details()
        self.device.click("details_back")
        self.assertTrue(self.device.wait_for_text("Pydrud Native Playground"))

    def test_hardware_back_pops_the_stack_and_is_handled(self):
        self.open_details()
        self.device.commands.clear()
        self.device.back()
        self.assertTrue(self.device.wait_for_text("Pydrud Native Playground"))
        self.assertTrue(self.device.wait_for_command("back_result"))
        result = [c for c in self.device.commands
                  if c.get("cmd") == "back_result"][-1]
        self.assertTrue(result["handled"])


if __name__ == "__main__":
    unittest.main()
