"""
End-to-end tests for the generated Heartbeat starter app.

The scaffolded screen is run against :class:`FakeDevice` and exercised the
way a user would: reading the resting screen, starting the rhythm, watching
the rate wander, and stopping it again. The animation maths is unit-tested
alongside it, because a frame loop is much easier to pin down directly than
through a renderer.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

from pydrud import Theme
from pydrud.commands.project import create_project
from tests.fake_device import FakeDevice, run_app


class TestHeartbeatStarterEndToEnd(unittest.TestCase):

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
        from app import theme
        from app.screens import heartbeat

        self.starter = starter
        self.theme = theme
        self.heartbeat = heartbeat
        # Each test starts from a resting screen and a clean clock.
        heartbeat._anim.update(started=0.0, next_beat=0.0, beat_at=-99.0,
                               timer=None, page=None)
        heartbeat.bpm.value = 72
        heartbeat.running.value = False
        starter.router.reset()

        self.device = FakeDevice().start()
        from pydrud import App
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
        Theme.light()

    # ── helpers ──────────────────────────────────────────────────────────

    def node(self, key: str):
        return self.device.root.find(key)

    def value(self, key: str) -> str:
        return self.node(key).props["value"]

    def ecg_offset(self) -> float:
        """The ECG's horizontal scroll, read from its ``translate`` op."""
        ops = self.node("hb_ecg").props["ops"]
        return next(op["dx"] for op in ops if op.get("op") == "translate")

    def start(self):
        self.device.click("hb_transport")
        self.assertTrue(self.device.wait_for(
            lambda d: self.value("hb_session_text") == "Active"))

    # ── the resting screen ───────────────────────────────────────────────

    def test_initial_screen_matches_the_design(self):
        self.assertEqual(self.device.texts,
                         ["tour_app", "Ready", "72", "BPM",
                          "Tap Start to begin", "Visual rhythm"])

        for key in ("heartbeat_root", "hb_topbar", "hb_app_name",
                    "hb_session_dot", "hb_session_text", "hb_visual",
                    "hb_glow", "hb_ring_one", "hb_ring_two", "hb_heart",
                    "hb_number", "hb_unit", "hb_message", "hb_ecg",
                    "hb_transport", "hb_transport._icon", "hb_bottom",
                    "hb_footnote", "hb_flash"):
            with self.subTest(key=key):
                self.assertIsNotNone(self.node(key), f"{key} is missing")

    def test_the_palette_and_type_follow_the_theme_and_the_window(self):
        """Colour comes from the palette; the ``clamp()``-driven sizes come
        from the live window (see ``heartbeat._layout``)."""
        m = self.heartbeat._layout()
        number = self.node("hb_number")
        self.assertEqual(number.style["font"]["size"], m["number"])
        self.assertEqual(number.style["font"]["weight"], 870)
        self.assertEqual(number.style["font"]["color"], Theme.text)
        self.assertAlmostEqual(number.style["font"]["letterSpacing"],
                               m["track"] / m["number"])

        # The screen background and the pulse field follow the palette.
        self.assertEqual(self.node("heartbeat_screen._stack").style["bg"],
                         Theme.background)
        self.assertEqual(self.node("hb_glow").style["bg"],
                         self.theme.HEART_SOFT)
        self.assertEqual(self.node("hb_ring_one").style["border"]["color"],
                         self.theme.HEART_LINE)
        # Shapes that do not depend on the window stay in the stylesheet.
        self.assertEqual(self.node("hb_glow").style["borderRadius"], 999)
        self.assertEqual(self.node("hb_footnote").style["font"]["size"], 9)

    def test_the_layout_adapts_to_the_window(self):
        """The design's ``clamp()`` rules follow the window: a narrow phone
        gets a smaller reading and pulse field, with no second layout."""
        wide = self.heartbeat._layout()["number"]
        self.device.resize(320, 640)
        self.assertTrue(self.device.wait_for(
            lambda d: self.node("hb_number").style["font"]["size"] == 78),
            "the reading should shrink on a small window")
        self.assertEqual(self.node("hb_visual").style["width"], 150)
        self.assertLess(self.heartbeat._layout()["number"], wide)

    def test_the_footnote_is_centred(self):
        """No trailing padding — the caption centres in the window."""
        self.assertNotIn("padding", self.node("hb_bottom").style)

    def test_the_button_clears_the_safe_area(self):
        """The FAB margin is the design's gap *above* the gesture bar.

        The Python layout keeps the plain design value and leaves safe-area
        handling on, so the renderer adds the inset — the button ends up
        16dp clear of the home indicator instead of sitting on top of it.
        """
        fab = self.node("hb_transport")
        self.assertTrue(fab.style.get("safeAreaBottom", True))
        self.assertEqual(fab.style["bottom"], self.heartbeat._layout()["fab_bottom"])
        self.assertLessEqual(fab.style["bottom"], 20)

    def test_the_reading_never_ellipsises(self):
        """A one-line reading clips instead of flashing a transient '…'."""
        style = self.node("hb_number").style
        self.assertEqual(style.get("maxLines"), 1)
        self.assertEqual(style.get("overflow"), "clip")

    def test_a_stopped_screen_is_completely_still(self):
        """No idle loop: the resting styles never move."""
        self.assertIsNone(self.heartbeat._anim["timer"])
        samples = []
        for _ in range(4):
            time.sleep(0.08)
            samples.append(self.node("hb_glow").style["opacity"])
        self.assertEqual(set(samples), {0.0})
        self.assertEqual(self.node("hb_heart").style["scale"], 1.0)
        self.assertEqual(self.ecg_offset(), 0.0)

    # ── starting and stopping ────────────────────────────────────────────

    def test_the_transport_button_starts_the_rhythm(self):
        self.start()

        self.assertEqual(self.value("hb_session_text"), "Active")
        self.assertEqual(self.value("hb_message"), "Rhythm is running")
        # The chip and the button take the heart's colour while live.
        self.assertEqual(self.node("hb_session_dot").style["bg"],
                         self.theme.HEART)
        self.assertEqual(self.node("hb_transport").style["bg"],
                         self.theme.HEART_SOFT)
        self.assertEqual(self.node("hb_transport._icon").style["font"]["color"],
                         self.theme.HEART)
        # ...and the frame loop is running.
        self.assertIsNotNone(self.heartbeat._anim["timer"])

    def test_the_transport_button_stops_the_rhythm(self):
        self.start()
        self.device.click("hb_transport")
        self.assertTrue(self.device.wait_for(
            lambda d: self.value("hb_session_text") == "Ready"))

        self.assertEqual(self.value("hb_message"), "Tap Start to begin")
        self.assertIsNone(self.heartbeat._anim["timer"])
        self.assertEqual(self.node("hb_glow").style["opacity"], 0.0)
        self.assertEqual(self.node("hb_heart").style["scale"], 1.0)
        self.assertEqual(self.node("hb_transport").style["bg"],
                         Theme.text)

    def test_every_widget_moves_while_the_rhythm_runs(self):
        self.start()
        glows, hearts, offsets = set(), set(), set()
        for _ in range(12):
            time.sleep(0.09)
            glows.add(round(self.node("hb_glow").style["opacity"], 3))
            hearts.add(round(self.node("hb_heart").style["scale"], 3))
            offsets.add(round(self.ecg_offset(), 1))

        self.assertGreater(len(glows), 3, "the pulse field should animate")
        self.assertGreater(len(hearts), 1, "the heart should beat")
        self.assertGreater(len(offsets), 3, "the ECG should scroll")

    def test_the_rate_stays_inside_the_resting_band(self):
        self.start()
        seen = {int(self.value("hb_number"))}
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            seen.add(int(self.value("hb_number")))
            time.sleep(0.05)
        self.assertTrue(all(68 <= value <= 78 for value in seen),
                        f"BPM drifted out of band: {sorted(seen)}")

    # ── the animation maths ──────────────────────────────────────────────

    def test_the_rate_clamps_at_both_ends_of_the_band(self):
        beat = self.heartbeat._beat
        with mock.patch.object(self.heartbeat.random, "choice",
                               return_value=1):
            for _ in range(50):
                beat(time.monotonic())
        self.assertEqual(self.heartbeat.bpm.value, 78)
        with mock.patch.object(self.heartbeat.random, "choice",
                               return_value=-1):
            for _ in range(50):
                beat(time.monotonic())
        self.assertEqual(self.heartbeat.bpm.value, 68)

    def test_keyframe_sampling_is_bounded_and_exact_at_the_ends(self):
        between = self.heartbeat._between
        frames = ((0.0, {"scale": 0.0}), (1.0, {"scale": 2.0}))
        self.assertEqual(between(frames, 0.0)["scale"], 0.0)
        self.assertEqual(between(frames, 1.0)["scale"], 2.0)
        self.assertAlmostEqual(between(frames, 0.5)["scale"], 1.0)

        eased = self.heartbeat._between(frames, 0.5,
                                        self.heartbeat._ease_out)
        self.assertGreater(eased["scale"], 1.0)   # ease-out front-loads

    def test_the_phase_wraps_within_the_period(self):
        phase = self.heartbeat._phase
        self.assertAlmostEqual(phase(0.0, 2.0), 0.0)
        self.assertAlmostEqual(phase(1.0, 2.0), 0.5)
        self.assertAlmostEqual(phase(2.5, 2.0), 0.25)

    # ── the palette ──────────────────────────────────────────────────────

    def test_the_heart_follows_the_project_accent(self):
        """The default accent is the design's coral, and every tint derives
        from it — so ``pydrud create --accent`` re-brands the whole screen."""
        from app import theme
        self.assertEqual(theme.HEART, "#FFE85D68")
        self.assertEqual(theme.ACCENT, theme.HEART)
        self.assertEqual(theme.HEART_SOFT, "#14E85D68")
        self.assertEqual(theme.HEART_LINE, "#2EE85D68")
        self.assertEqual(theme.HEART_FAINT, "#1AE85D68")
        self.assertEqual(theme.LIGHT["primary"], theme.ACCENT)

    def test_switching_to_the_dark_palette_recolours_the_screen(self):
        light_bg = Theme.background
        self.theme.use_dark()
        self.assertTrue(Theme.dark_mode)
        self.assertNotEqual(Theme.background, light_bg)

        self.app.apply_theme()
        self.assertTrue(self.device.wait_for(
            lambda d: d.root.find("heartbeat_screen._stack").style["bg"]
            != light_bg))
        self.assertEqual(self.node("heartbeat_screen._stack").style["bg"],
                         Theme.background)

        self.theme.use_light()
        self.assertFalse(Theme.dark_mode)


if __name__ == "__main__":
    unittest.main()
