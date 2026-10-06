"""The date/time pickers and the modal bottom sheet.

PYDRUD §15.2 lists date/time pickers and a bottom sheet as high-priority
gaps. They already exist as native service calls (``page.dialog.date()`` /
``.time()`` / ``.bottom_sheet()``), but shipped with **no tests** and with
two silent drop bugs: the date picker ignored ``min``/``max`` and the time
picker ignored ``initial``. These tests pin the round trip, the payload and
the validation that makes a typo loud instead of a no-op.
"""

from __future__ import annotations

import os
import unittest

from pydrud import Button
from pydrud.testing import AppTester

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NATIVE_SERVICES = os.path.join(ROOT, "pydrud", "android", "templates",
                               "android", "NativeServices.java.j2")


def _java() -> str:
    with open(NATIVE_SERVICES, encoding="utf-8") as handle:
        return handle.read()


class _PickerCase(unittest.TestCase):
    """Runs ``call(page)`` from a button tap and returns the request."""

    def _drive(self, call, command, answer):
        results = []

        def main(page):
            def go(_event):
                call(page).then(results.append)

            page.add(Button("Open", key="open", on_click=go))

        with AppTester(main) as app:
            app.answer(command, answer)
            app.tap("open")
            request = app.requested(command)
            app.device.wait_for(lambda d: bool(results))
            return request, results

    def _reject(self, call, message):
        """Bad arguments must raise at the call site, before any I/O.

        An exception raised inside an event handler is reported by the app
        rather than propagated to the caller, so the validation is pinned
        directly on the service object.
        """
        from pydrud.services.native import Dialogs

        dialog = Dialogs(lambda *a, **k: None)
        with self.assertRaises(ValueError) as caught:
            call(dialog)
        self.assertIn(message, str(caught.exception))


class TestDatePicker(_PickerCase):

    def test_the_round_trip_resolves_an_iso_date(self):
        request, results = self._drive(
            lambda page: page.dialog.date(initial="2026-10-06"),
            "date_picker", "2026-10-06")
        self.assertEqual(request["initial"], "2026-10-06")
        self.assertEqual(results, ["2026-10-06"])

    def test_min_and_max_reach_the_device(self):
        request, _ = self._drive(
            lambda page: page.dialog.date(min="1900-01-01", max="2026-12-31"),
            "date_picker", "2000-01-01")
        self.assertEqual(request["min"], "1900-01-01")
        self.assertEqual(request["max"], "2026-12-31")

    def test_omitted_bounds_are_left_out_of_the_payload(self):
        request, _ = self._drive(
            lambda page: page.dialog.date(),
            "date_picker", "2026-10-06")
        # Unset values are dropped so the frame stays small; the native
        # picker already defaults to "today".
        for key in ("initial", "min", "max"):
            with self.subTest(key=key):
                self.assertNotIn(key, request)

    def test_cancelling_resolves_none(self):
        _, results = self._drive(lambda page: page.dialog.date(),
                                 "date_picker", None)
        self.assertEqual(results, [None])

    def test_a_malformed_bound_is_rejected(self):
        for bad in ("2026/10/06", "26-10-06", "2026-10", "not-a-date", "2026-1-6"):
            with self.subTest(value=bad):
                self._reject(lambda d, b=bad: d.date(initial=b), "ISO date")

    def test_an_impossible_date_is_rejected(self):
        self._reject(lambda d: d.date(min="2026-13-01"),
                     "not a real calendar date")

    def test_min_after_max_is_rejected(self):
        self._reject(lambda d: d.date(min="2026-01-01", max="2025-01-01"),
                     "is after")


class TestTimePicker(_PickerCase):

    def test_the_round_trip_resolves_an_hh_mm(self):
        request, results = self._drive(
            lambda page: page.dialog.time(initial="09:30"),
            "time_picker", "09:30")
        self.assertEqual(request["initial"], "09:30")
        self.assertEqual(results, ["09:30"])

    def test_the_twenty_four_hour_flag_reaches_the_device(self):
        request, _ = self._drive(
            lambda page: page.dialog.time(use_24h=False),
            "time_picker", "09:30")
        self.assertFalse(request["use24h"])

    def test_cancelling_resolves_none(self):
        _, results = self._drive(lambda page: page.dialog.time(),
                                 "time_picker", None)
        self.assertEqual(results, [None])

    def test_a_malformed_time_is_rejected(self):
        for bad in ("9:30", "09-30", "0930", "09:3", "noon"):
            with self.subTest(value=bad):
                self._reject(lambda d, b=bad: d.time(initial=b),
                             "24-hour time")

    def test_an_impossible_time_is_rejected(self):
        for bad in ("24:00", "09:60", "-1:00"):
            with self.subTest(value=bad):
                self._reject(lambda d, b=bad: d.time(initial=b),
                             "not a real time of day")


class TestBottomSheet(_PickerCase):

    def test_it_resolves_the_chosen_index(self):
        request, results = self._drive(
            lambda page: page.dialog.bottom_sheet(
                ["Camera", "Gallery"], title="Add photo"),
            "bottom_sheet", 1)
        self.assertEqual(request["options"], ["Camera", "Gallery"])
        self.assertEqual(request["title"], "Add photo")
        self.assertEqual(results, [1])

    def test_icons_are_forwarded(self):
        request, _ = self._drive(
            lambda page: page.dialog.bottom_sheet(
                ["Camera", "Gallery"], icons=["camera", "image"]),
            "bottom_sheet", 0)
        self.assertEqual(request["icons"], ["camera", "image"])

    def test_cancelling_resolves_minus_one(self):
        _, results = self._drive(
            lambda page: page.dialog.bottom_sheet(["Only"]),
            "bottom_sheet", -1)
        self.assertEqual(results, [-1])

    def test_an_empty_sheet_is_rejected(self):
        self._reject(lambda d: d.bottom_sheet([]),
                     "at least one option")


class TestNativeHandlers(unittest.TestCase):
    """The generated Java must honour every argument the Python API sends."""

    def setUp(self):
        self.source = _java()

    def test_every_command_is_dispatched(self):
        for cmd in ("date_picker", "time_picker", "bottom_sheet"):
            with self.subTest(cmd=cmd):
                self.assertIn(f'case "{cmd}":', self.source)

    def test_the_date_picker_applies_both_bounds(self):
        self.assertIn("setMinDate(", self.source)
        self.assertIn("setMaxDate(", self.source)

    def test_the_date_picker_reads_the_initial_value(self):
        self.assertIn("parseIsoDate(msg.optString(\"initial\", \"\"), now)",
                      self.source)

    def test_the_time_picker_reads_the_initial_value(self):
        self.assertIn('msg.optString("initial", "")', self.source)
        self.assertIn('initial.charAt(2) == \':\'', self.source)

    def test_the_time_picker_reads_the_use24h_flag(self):
        self.assertIn('msg.optBoolean("use24h", true)', self.source)

    def test_the_bottom_sheet_reports_cancellation(self):
        self.assertIn("setOnCancelListener(dialog -> reply(requestId, -1))",
                      self.source)


if __name__ == "__main__":
    unittest.main()
