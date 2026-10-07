"""
End-to-end tests for the generated counter starter app.

The scaffolded screen is run against :class:`FakeDevice` and exercised like
an app user would: incrementing from the floating action button, decrementing,
resetting, and resizing to a tablet-sized window.
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


class TestStarterCounterAppEndToEnd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pydrud-e2e-")
        cls.cwd = os.getcwd()
        os.chdir(cls.tmp)
        create_project("tour_app", org="com.example", runtime="chaquopy")
        cls.project = os.path.join(cls.tmp, "tour_app")
        cls.src = os.path.join(cls.project, "src")
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
        from app.state import counter

        self.starter = starter
        self.counter_state = counter
        self.counter_state.value = 0
        starter.router.reset()
        self.device = FakeDevice().start()
        self.app = App(
            target=starter.router.build_root(),
            title="tour_app",
            stylesheet=os.path.join(self.project, "src", "app", "theme.pss"),
        )
        self.app.attach_router(starter.router)
        run_app(self.app, self.device)
        self.assertTrue(self.device.wait_for(lambda d: d.root is not None))

    def tearDown(self):
        self.app.stop()
        self.device.stop()

    def counter(self) -> str:
        return self.device.root.find("counter_value").props["value"]

    def test_initial_screen_is_a_focused_counter_app(self):
        texts = self.device.texts
        self.assertIn("tour_app", texts)
        self.assertIn("Count the things that matter.", texts)
        self.assertIn("A little progress, one tap at a time.", texts)
        self.assertIn("YOUR PERSONAL TALLY", texts)
        self.assertIn("TOTAL COUNT", texts)
        self.assertEqual(self.counter(), "0")

        for key in ("counter_panel", "counter_actions", "dec_btn",
                    "reset_btn", "inc_btn"):
            with self.subTest(key=key):
                self.assertIsNotNone(self.device.root.find(key))
        self.assertIsNone(self.device.root.find("name_input"))
        self.assertIsNone(self.device.root.find("toast_btn"))

    def test_floating_action_button_increments_without_full_renders(self):
        device = self.device
        before = device.full_renders

        device.click("inc_btn")
        self.assertTrue(device.wait_for(lambda d: self.counter() == "1"))
        self.assertEqual(device.root.find("counter_unit").props["value"], "count")
        device.click("inc_btn")
        self.assertTrue(device.wait_for(lambda d: self.counter() == "2"))
        self.assertEqual(device.root.find("counter_unit").props["value"], "counts")
        self.assertEqual(device.full_renders, before,
                         "counter taps should update incrementally")

    def test_decrement_and_reset_controls(self):
        device = self.device
        device.click("inc_btn")
        device.click("inc_btn")
        device.click("dec_btn")
        self.assertTrue(device.wait_for(lambda d: self.counter() == "1"))

        device.click("reset_btn")
        self.assertTrue(device.wait_for(lambda d: self.counter() == "0"))
        device.click("dec_btn")
        self.assertTrue(device.wait_for(lambda d: self.counter() == "0"))

    def test_starter_pss_applies_and_content_caps_on_wide_screens(self):
        panel = self.device.root.find("counter_panel")
        number = self.device.root.find("counter_value")
        fab = self.device.root.find("inc_btn")
        self.assertTrue(fab.props.get("_fab"))
        self.assertEqual(panel.style.get("borderRadius"), 28)
        self.assertEqual(number.style.get("font", {}).get("size"), 76)
        self.assertEqual(fab.semantics, "Add one to the counter")

        self.device.resize(1024, 768)
        self.assertTrue(self.device.wait_for(
            lambda d: d.root.find("counter_wrap") is not None))
        self.assertEqual(self.device.root.find("counter_wrap").style.get("width"), 720)


if __name__ == "__main__":
    unittest.main()
