"""Tests for the 1.2 runtime: Store, Computed, ReactiveList, tasks, Results, forms."""

import threading
import time
import unittest

from pydrud import (
    Computed, ReactiveList, Result, ResultError, State, Store, TaskRunner,
    debounce, throttle,
)
from pydrud.core.tasks import Timer as CoreTimer
from pydrud.widgets.forms import (
    Form, FormField, between, custom, email, matches, max_length, min_length,
    numeric, pattern, phone, required, url,
)
from pydrud import Checkbox, TextField, Text


class TestStore(unittest.TestCase):

    def setUp(self):
        self.store = Store({"count": 0, "todos": []})

    def test_update_only_notifies_on_real_change(self):
        seen = []
        self.store.subscribe(lambda state, changed: seen.append(changed))
        self.store.set("count", 0)          # same value → no notification
        self.assertEqual(seen, [])
        self.store.set("count", 1)
        self.assertEqual(seen, [{"count"}])

    def test_state_copy_is_defensive(self):
        snapshot = self.store.state
        snapshot["count"] = 99
        self.assertEqual(self.store["count"], 0)

    def test_action_decorator(self):
        @self.store.action
        def add_todo(state, text):
            return {"todos": state["todos"] + [text]}

        add_todo("Buy milk")
        self.assertEqual(self.store["todos"], ["Buy milk"])

    def test_mutate_with_draft(self):
        self.store.mutate(lambda draft: draft["todos"].append("x"))
        self.assertEqual(self.store["todos"], ["x"])

    def test_selector_fires_only_for_its_slice(self):
        counts, todos = [], []
        self.store.select("count").listen(counts.append)
        self.store.select("todos").listen(todos.append)
        self.store.set("count", 5)
        self.assertEqual(counts, [5])
        self.assertEqual(todos, [])

    def test_selector_accepts_projection(self):
        lengths = []
        self.store.select(lambda s: len(s["todos"])).listen(lengths.append)
        self.store.update({"todos": ["a", "b"]})
        self.assertEqual(lengths, [2])

    def test_batch_coalesces_notifications(self):
        calls = []
        self.store.subscribe(lambda *_: calls.append(1))
        with self.store.batch():
            self.store.set("count", 1)
            self.store.set("count", 2)
            self.store.set("count", 3)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.store["count"], 3)

    def test_undo_restores_previous_state(self):
        self.store.set("count", 1)
        self.store.set("count", 2)
        self.assertTrue(self.store.can_undo)
        self.store.undo()
        self.assertEqual(self.store["count"], 1)

    def test_middleware_sees_action_name(self):
        log = []
        self.store.use(lambda action, old, new: log.append(action))
        self.store.update({"count": 7}, action="bump")
        self.assertEqual(log, ["bump"])

    def test_update_rejects_non_dict(self):
        with self.assertRaises(TypeError):
            self.store.update(["count", 1])

    def test_unsubscribe(self):
        seen = []
        off = self.store.subscribe(lambda *_: seen.append(1))
        off()
        self.store.set("count", 3)
        self.assertEqual(seen, [])

    def test_bad_subscriber_does_not_break_others(self):
        seen = []

        def boom(*_):
            raise RuntimeError("bad listener")

        self.store.subscribe(boom)
        self.store.subscribe(lambda *_: seen.append(1))
        self.store.set("count", 1)
        self.assertEqual(seen, [1])


class TestComputed(unittest.TestCase):

    def test_caches_until_source_changes(self):
        calls = []
        base = State(2)

        def compute():
            calls.append(1)
            return base.value * 10

        derived = Computed(compute, sources=[base])
        self.assertEqual(derived.value, 20)
        self.assertEqual(derived.value, 20)
        self.assertEqual(len(calls), 1)      # cached
        base.value = 3
        self.assertEqual(derived.value, 30)

    def test_notifies_subscribers(self):
        seen = []
        base = State(1)
        derived = Computed(lambda: base.value + 1, sources=[base])
        derived.subscribe(seen.append)
        base.value = 5
        self.assertEqual(seen, [6])

    def test_tracks_a_store(self):
        store = Store({"items": [1, 2, 3]})
        total = Computed(lambda: sum(store["items"]), sources=[store])
        self.assertEqual(total.value, 6)
        store.set("items", [1])
        self.assertEqual(total.value, 1)


class TestReactiveList(unittest.TestCase):

    def setUp(self):
        self.items = ReactiveList(["a", "b"])
        self.events = []
        self.items.subscribe(lambda value: self.events.append(list(value)))

    def test_mutations_notify(self):
        self.items.append("c")
        self.items.remove("a")
        self.items.move(0, 1)
        self.assertEqual(len(self.events), 3)
        self.assertEqual(self.items.value, ["c", "b"])

    def test_no_notification_for_missing_remove(self):
        self.assertFalse(self.items.remove("zzz"))
        self.assertEqual(self.events, [])

    def test_queries(self):
        items = ReactiveList([1, 2, 3, 4])
        self.assertEqual(items.where(lambda n: n % 2 == 0), [2, 4])
        self.assertEqual(items.first(lambda n: n > 2), 3)
        self.assertIsNone(items.first(lambda n: n > 99))
        self.assertEqual(items.index_where(lambda n: n == 3), 2)
        self.assertEqual(items.index_where(lambda n: n == 9), -1)

    def test_list_protocol(self):
        self.assertEqual(len(self.items), 2)
        self.assertEqual(self.items[0], "a")
        self.assertIn("b", self.items)
        self.assertEqual(list(self.items), ["a", "b"])


class TestResults(unittest.TestCase):

    def test_then_runs_once_and_late_registration_fires_immediately(self):
        result = Result("r1", "dialog")
        seen = []
        result.then(seen.append)
        result.complete(True)
        result.then(seen.append)          # already done → immediate
        self.assertEqual(seen, [True, True])

    def test_cannot_settle_twice(self):
        result = Result("r2")
        self.assertTrue(result.complete(1))
        self.assertFalse(result.complete(2))
        self.assertFalse(result.fail("nope"))
        self.assertEqual(result.wait(0.1), 1)

    def test_failure_path(self):
        result = Result("r3", "prefs_get")
        errors = []
        result.catch(errors.append)
        result.fail("disk full")
        self.assertEqual(errors, ["disk full"])
        self.assertIsNone(result.wait(0.1))
        with self.assertRaises(ResultError):
            result.result(0.1)

    def test_timeout_marks_failed(self):
        result = Result("r4", "slow")
        self.assertEqual(result.wait(0.01, default="fallback"), "fallback")
        self.assertEqual(result.error, "timeout")

    def test_wait_unblocks_from_another_thread(self):
        result = Result("r5")
        threading.Timer(0.05, lambda: result.complete("hi")).start()
        self.assertEqual(result.wait(2), "hi")

    def test_cancel(self):
        result = Result("r6")
        self.assertTrue(result.cancel())
        self.assertTrue(result.cancelled)
        self.assertFalse(result.complete("late"))

    def test_callback_errors_do_not_propagate(self):
        result = Result("r7")
        result.then(lambda v: 1 / 0)
        result.complete(1)                 # must not raise
        self.assertTrue(result.done)


class TestTasks(unittest.TestCase):

    def setUp(self):
        self.runner = TaskRunner(max_workers=2)

    def tearDown(self):
        self.runner.shutdown()

    def test_runs_off_the_calling_thread(self):
        where = {}
        self.runner.run(lambda: where.setdefault(
            "thread", threading.current_thread().name)).result(timeout=3)
        self.assertNotEqual(where["thread"], threading.current_thread().name)

    def test_runs_coroutines(self):
        async def work():
            return 42

        self.assertEqual(self.runner.run(work).result(timeout=3), 42)

    def test_errors_are_reported_not_raised(self):
        seen = []
        runner = TaskRunner(on_error=seen.append)
        runner.run(lambda: 1 / 0).result(timeout=3)
        self.assertEqual(len(seen), 1)
        runner.shutdown()

    def test_after_runs_once(self):
        calls = []
        timer = self.runner.after(0.02, lambda: calls.append(1))
        time.sleep(0.15)
        self.assertEqual(calls, [1])
        self.assertFalse(timer.repeat)

    def test_every_repeats_until_cancelled(self):
        calls = []
        timer = self.runner.every(0.01, lambda: calls.append(1))
        time.sleep(0.08)
        timer.cancel()
        count = len(calls)
        self.assertGreaterEqual(count, 2)
        time.sleep(0.05)
        self.assertEqual(len(calls), count)

    def test_shutdown_cancels_timers(self):
        calls = []
        self.runner.every(0.01, lambda: calls.append(1))
        self.runner.shutdown()
        time.sleep(0.05)
        self.assertLessEqual(len(calls), 2)

    def test_timer_survives_a_failing_callback(self):
        ticks = []

        def flaky():
            ticks.append(1)
            raise RuntimeError("boom")

        timer = CoreTimer(0.01, flaky, repeat=True).start()
        time.sleep(0.06)
        timer.cancel()
        self.assertGreaterEqual(len(ticks), 2)


class TestRateLimiting(unittest.TestCase):

    def test_debounce_collapses_bursts(self):
        calls = []
        fn = debounce(0.05)(lambda value: calls.append(value))
        for char in "pydrud":
            fn(char)
        time.sleep(0.2)
        self.assertEqual(calls, ["d"])

    def test_throttle_limits_rate(self):
        calls = []
        fn = throttle(0.1)(lambda: calls.append(1))
        for _ in range(5):
            fn()
        self.assertEqual(len(calls), 1)
        time.sleep(0.12)
        fn()
        self.assertEqual(len(calls), 2)


class TestValidators(unittest.TestCase):

    def test_required(self):
        check = required()
        self.assertIsNotNone(check(""))
        self.assertIsNotNone(check("   "))
        self.assertIsNotNone(check(None))
        self.assertIsNotNone(check([]))
        self.assertIsNotNone(check(False))
        self.assertIsNone(check("x"))
        self.assertIsNone(check(0))        # zero is a real value

    def test_lengths(self):
        self.assertIsNotNone(min_length(3)("ab"))
        self.assertIsNone(min_length(3)(""))       # empty → required's job
        self.assertIsNotNone(max_length(2)("abc"))

    def test_email(self):
        for good in ("a@b.co", "ada.lovelace+dev@example.org"):
            self.assertIsNone(email()(good), good)
        for bad in ("a@b", "a b@c.com", "@b.com", "nope"):
            self.assertIsNotNone(email()(bad), bad)

    def test_phone_url_numeric_between(self):
        self.assertIsNone(phone()("+92 300 1234567"))
        self.assertIsNotNone(phone()("abc"))
        self.assertIsNone(url()("https://pydrud.dev/docs"))
        self.assertIsNotNone(url()("pydrud.dev"))
        self.assertIsNone(numeric()("3.14"))
        self.assertIsNotNone(numeric()("pi"))
        self.assertIsNone(between(1, 10)(5))
        self.assertIsNotNone(between(1, 10)(50))

    def test_pattern_and_custom(self):
        self.assertIsNone(pattern(r"^[A-Z]{3}$")("ABC"))
        self.assertIsNotNone(pattern(r"^[A-Z]{3}$")("abc"))
        even = custom(lambda v: int(v) % 2 == 0, "must be even")
        self.assertIsNone(even(4))
        self.assertEqual(even(3), "must be even")
        self.assertEqual(even("x"), "must be even")   # exception → invalid


class TestForms(unittest.TestCase):

    def build(self):
        return Form(
            FormField("email", TextField(""), label="Email",
                      validators=[required(), email()]),
            FormField("password", TextField(""), label="Password",
                      validators=[required(), min_length(8)]),
            FormField("terms", Checkbox("Accept"), validators=[required()]),
        )

    def test_invalid_form_does_not_submit(self):
        submitted = []
        form = self.build()
        form._on_submit = submitted.append
        self.assertFalse(form.submit())
        self.assertEqual(submitted, [])
        self.assertEqual(set(form.errors), {"email", "password", "terms"})

    def test_valid_form_submits_values(self):
        submitted = []
        form = self.build()
        form._on_submit = submitted.append
        form.set_value("email", "ada@example.com")
        form.set_value("password", "lovelace1")
        form.set_value("terms", True)
        self.assertTrue(form.submit())
        self.assertEqual(submitted[0]["email"], "ada@example.com")
        self.assertEqual(form.errors, {})

    def test_change_events_track_values_and_clear_errors(self):
        form = self.build()
        form.submit()                               # mark everything invalid
        self.assertIn("email", form.errors)
        control = form.field("email").control
        control.event_handlers["change"]({"key": "x",
                                          "data": {"value": "a@b.co"}})
        self.assertEqual(form.field("email").value, "a@b.co")
        self.assertNotIn("email", form.errors)
        self.assertTrue(form.dirty)

    def test_user_on_change_handler_is_preserved(self):
        seen = []
        form = Form(FormField("name", TextField("", on_change=seen.append)))
        form.field("name").control.event_handlers["change"](
            {"data": {"value": "x"}})
        self.assertEqual(len(seen), 1)

    def test_matches_validator_is_cross_field(self):
        form = Form(
            FormField("password", TextField("secret123")),
            FormField("confirm", TextField("different"),
                      validators=[matches("password")]),
        )
        self.assertIn("confirm", form.validate())
        form.set_value("confirm", "secret123")
        self.assertEqual(form.validate(), {})

    def test_duplicate_names_rejected(self):
        with self.assertRaises(ValueError):
            Form(FormField("a", TextField("")), FormField("a", TextField("")))

    def test_plain_widgets_are_decoration(self):
        form = Form(Text("Sign in"), FormField("a", TextField("")))
        self.assertEqual(list(form.fields), ["a"])
        self.assertEqual(len(form.children), 2)

    def test_server_side_error_and_reset(self):
        form = self.build()
        form.set_error("email", "already registered")
        self.assertEqual(form.errors["email"], "already registered")
        form.reset()
        self.assertEqual(form.errors, {})
        self.assertFalse(form.dirty)

    def test_field_requires_a_name(self):
        with self.assertRaises(ValueError):
            FormField("", TextField(""))

    def test_validate_on_change(self):
        form = Form(FormField("email", TextField(""), validators=[email()]),
                    validate_on_change=True)
        control = form.field("email").control
        control.event_handlers["change"]({"data": {"value": "nope"}})
        self.assertIn("email", form.errors)


if __name__ == "__main__":
    unittest.main()
