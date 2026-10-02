"""AnimationController timing: one curve application per frame."""

import unittest

from pydrud.core.controllers import CURVES, AnimationController


def drive(controller, ticks):
    controller._running = True
    for _ in range(ticks):
        controller._tick()
    return controller.value


class TestCurveTiming(unittest.TestCase):
    def test_every_curve_finishes_in_exactly_one_duration(self):
        """``fps * duration`` ticks must land on the end value.

        The old loop re-derived progress from the *eased* value, so the curve
        compounded: ``ease_in`` never finished and ``ease_out`` finished in 8
        frames instead of 60.
        """
        for name in sorted(CURVES):
            with self.subTest(curve=name):
                controller = AnimationController(1.0, curve=name, fps=60)
                drive(controller, 60)
                self.assertAlmostEqual(controller.progress, 1.0, places=6)
                self.assertAlmostEqual(controller.value, 1.0, places=6)
                self.assertFalse(controller.running)

    def test_half_way_matches_the_curve(self):
        controller = AnimationController(1.0, curve="ease_in", fps=60)
        drive(controller, 30)
        self.assertAlmostEqual(controller.progress, 0.5, places=6)
        self.assertAlmostEqual(controller.value, CURVES["ease_in"](0.5),
                               places=6)

    def test_completion_fires_once(self):
        controller = AnimationController(0.5, curve="ease_out", fps=60)
        done = []
        controller.on_complete(lambda: done.append(1))
        drive(controller, 60)
        self.assertEqual(done, [1])


class TestAnimateTo(unittest.TestCase):
    def test_target_does_not_shrink_the_range(self):
        controller = AnimationController(1.0, curve="linear", fps=60)
        controller.animate_to(0.5)
        drive(controller, 60)
        self.assertAlmostEqual(controller.value, 0.5, places=6)
        self.assertEqual(controller.upper, 1.0)

        controller.forward()
        drive(controller, 60)
        self.assertAlmostEqual(controller.value, 1.0, places=6)

    def test_reverse_returns_to_lower(self):
        controller = AnimationController(1.0, curve="linear", fps=60)
        controller.reset(1.0)
        controller.reverse()
        drive(controller, 60)
        self.assertAlmostEqual(controller.value, 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
