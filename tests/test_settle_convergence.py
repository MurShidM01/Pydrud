"""AppTester.settle() must wait for render convergence (DX-001 / IC-001).

An empty socket queue is not enough: a handler can request several renders
in a row (only the first is sent, the rest are deferred until the ACK), so
a test that read the screen straight after ``tap()`` used to observe an
intermediate frame.
"""

from __future__ import annotations

import unittest

from pydrud import Button, Text
from pydrud.testing import AppTester


class TestSettleConvergence(unittest.TestCase):

    def test_a_storm_of_updates_converges_on_the_final_frame(self):
        def main(page):
            label = Text("idle", key="status")

            def storm(_event):
                for i in range(1, 6):
                    label.value = f"n={i}"
                    page.update(label)          # deferred after the first

            page.add(label, Button("Go", key="go", on_click=storm))

        with AppTester(main) as app:
            app.tap("go")                       # tap() settles internally
            self.assertTrue(app.exists("n=5"),
                            "settle() returned before the final render")
            self.assertIn("n=5", app.texts)

    def test_pending_ui_work_is_not_quiet(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main) as app:
            app.settle()
            # A UI callback is always paired with a __ui__ wake-up; settle
            # must wait for the callback to actually run.
            app.app._ui_queue.put_nowait((lambda: None, (), {}))
            app.app._event_queue.put_nowait("__ui__")
            self.assertFalse(app._quiet(app.device.events_sent))
            app.settle(timeout=2)
            self.assertTrue(app.app._ui_queue.empty())

    def test_epoch_tracks_the_render_revision(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main) as app:
            app.settle()
            before = app._epoch(app.device.events_sent)
            self.assertIsInstance(before, tuple)
            # Nothing changes -> the epoch is stable across calls.
            self.assertEqual(before, app._epoch(app.device.events_sent))


if __name__ == "__main__":
    unittest.main()
