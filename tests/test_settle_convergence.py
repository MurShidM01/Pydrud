"""AppTester.settle() must wait for render convergence (DX-001 / IC-001).

An empty socket queue is not enough: a handler can request several renders
in a row (only the first is sent, the rest are deferred until the ACK), so
a test that read the screen straight after ``tap()`` used to observe an
intermediate frame.
"""

from __future__ import annotations

import unittest
from unittest import mock

from pydrud import App, Button, Text
from pydrud.testing import AppTester


def test_preparing_a_frame_is_never_reported_as_idle():
    """IC-002: the pipeline must not look idle mid-render.

    ``_render_pending`` is consumed by the call that serves it, so for the
    whole diff/encode/send window the only evidence of work is
    ``_render_in_progress``. If that flag were not consulted, a harness could
    observe "everything acknowledged" while a frame was still on its way —
    which is what made a tap land as a full re-render instead of a patch.
    """
    from pydrud.testing import _render_converged

    observed = []
    real = App._send_desired_tree_now

    def spy(self, *, force_snapshot):
        observed.append(_render_converged(self))
        return real(self, force_snapshot=force_snapshot)

    def main(page):
        page.add(Text("hi", key="t"), Button("Go", key="go"))

    with mock.patch.object(App, "_send_desired_tree_now", spy):
        with AppTester(main) as app:
            app.tap("go")

    assert observed, "no frame was ever prepared"
    assert not any(observed), "a frame being prepared looked like an idle pipeline"


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
