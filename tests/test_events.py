"""
Unit tests for the event dispatcher.
"""

import unittest
from pydrud.core.events import EventDispatcher
from pydrud.widgets import Text, Button


class TestEventDispatcher(unittest.TestCase):
    def setUp(self):
        self.dispatcher = EventDispatcher()

    def test_register_and_dispatch_click(self):
        btn = Button("Go", key="btn1").on_click(lambda d: "clicked")
        self.dispatcher.register_tree(btn)
        result = self.dispatcher.dispatch('{"type": "click", "key": "btn1", "data": {}}')
        self.assertEqual(result, ["clicked"])

    def test_dispatch_unregistered_key(self):
        result = self.dispatcher.dispatch('{"type": "click", "key": "nonexistent", "data": {}}')
        self.assertEqual(result, [])

    def test_dispatch_change_event(self):
        tf = Text("", key="tf1")
        tf.event_handlers["change"] = lambda d: d.get("value")
        self.dispatcher.register_tree(tf)
        result = self.dispatcher.dispatch('{"type": "change", "key": "tf1", "data": {"value": "hello"}}')
        self.assertEqual(result, ["hello"])

    def test_multiple_widgets(self):
        btn1 = Button("A", key="b1").on_click(lambda d: 1)
        btn2 = Button("B", key="b2").on_click(lambda d: 2)
        root = type("Root", (), {"walk": lambda self: iter([
            (btn1, 0), (btn2, 0)
        ])})()
        self.dispatcher.register_tree(root)
        self.assertEqual(self.dispatcher.dispatch('{"type": "click", "key": "b1", "data": {}}'), [1])
        self.assertEqual(self.dispatcher.dispatch('{"type": "click", "key": "b2", "data": {}}'), [2])

    def test_invalid_json(self):
        result = self.dispatcher.dispatch("{invalid}")
        self.assertEqual(result, [])

    def test_register_tree_walks_children(self):
        from pydrud.widgets.layout import Column
        col = Column(children=[
            Button("A", key="b1").on_click(lambda d: 1),
            Button("B", key="b2").on_click(lambda d: 2),
        ])
        self.dispatcher.register_tree(col)
        self.assertEqual(len(self.dispatcher._handlers), 2)

    def test_create_event_json(self):
        event = self.dispatcher.create_event_json("click", "k1", {"x": 1})
        self.assertIn("click", event)
        self.assertIn("k1", event)
        self.assertIn("x", event)


if __name__ == "__main__":
    unittest.main()
