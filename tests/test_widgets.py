"""
Unit tests for the Pydrud widget system.
"""

import json
import unittest
from pydrud.widgets import (
    Widget, Text, Button, Container, Column, Row, Center, Spacer,
    TextField, Image, Icon, Checkbox, Switch, Style, EdgeInsets, Alignment,
)


class TestWidgetBasics(unittest.TestCase):
    """Core widget creation and serialisation."""

    def test_widget_auto_key(self):
        w = Widget()
        self.assertTrue(len(w.key) == 12)

    def test_widget_explicit_key(self):
        w = Widget(key="my_key")
        self.assertEqual(w.key, "my_key")

    def test_widget_to_dict(self):
        w = Text("Hello", key="t1")
        d = w.to_dict()
        self.assertEqual(d["type"], "Text")
        self.assertEqual(d["key"], "t1")
        self.assertEqual(d["props"]["value"], "Hello")

    def test_widget_to_json(self):
        w = Text("Hello", key="t1")
        s = w.to_json()
        parsed = json.loads(s)
        self.assertEqual(parsed["props"]["value"], "Hello")


class TestTextWidget(unittest.TestCase):
    def test_text_creation(self):
        t = Text("Hello, World!")
        self.assertEqual(t.value, "Hello, World!")
        self.assertEqual(t._widget_type, "Text")

    def test_text_props(self):
        t = Text("Test", size=18, color="#FF0000", weight=700, italic=True)
        self.assertEqual(t.style["font"]["size"], 18)
        self.assertEqual(t.style["font"]["color"], "#FF0000")
        self.assertEqual(t.style["font"]["weight"], 700)
        self.assertTrue(t.style["font"]["italic"])

    def test_text_value_update(self):
        t = Text("A")
        t.value = "B"
        self.assertEqual(t.value, "B")


class TestButtonWidget(unittest.TestCase):
    def test_button_default(self):
        btn = Button("Click me")
        self.assertEqual(btn.text, "Click me")

    def test_button_variants(self):
        filled = Button("Filled", variant="filled")
        outlined = Button("Outlined", variant="outlined")
        text = Button("Text", variant="text")
        self.assertEqual(filled.style["variant"], "filled")
        self.assertEqual(outlined.style["variant"], "outlined")
        self.assertEqual(text.style["variant"], "text")

    def test_button_on_click(self):
        calls = []
        def handler(data):
            calls.append(1)

        btn = Button("Go").on_click(handler)
        self.assertIn("click", btn.event_handlers)
        btn.event_handlers["click"]({})
        self.assertEqual(len(calls), 1)


class TestLayoutWidgets(unittest.TestCase):
    def test_column(self):
        col = Column(children=[Text("A"), Text("B")], spacing=8)
        self.assertEqual(len(col.children), 2)
        self.assertEqual(col.style["spacing"], 8)

    def test_row(self):
        row = Row(children=[Text("A"), Text("B")], spacing=12)
        self.assertEqual(len(row.children), 2)
        self.assertEqual(row.style["spacing"], 12)

    def test_row_main_axis_alignment(self):
        # horizontal_alignment packs children along the main axis;
        # vertical_alignment stays the cross axis.
        row = Row(children=[Text("A")], horizontal_alignment="center",
                  vertical_alignment="center")
        self.assertEqual(row.style["mainAxisAlignment"], "center")
        self.assertEqual(row.style["crossAxisAlignment"], "center")

    def test_column_main_axis_alignment(self):
        col = Column(children=[Text("A")], vertical_alignment="center",
                     horizontal_alignment="end")
        self.assertEqual(col.style["mainAxisAlignment"], "center")
        self.assertEqual(col.style["crossAxisAlignment"], "end")

    def test_layouts_without_alignment_emit_no_axis_keys(self):
        # The native renderer keeps its legacy both-axis gravity mapping
        # when mainAxisAlignment is absent, so it must stay absent unless
        # the app asks for it.
        for widget in (Row(children=[]), Column(children=[])):
            self.assertNotIn("mainAxisAlignment", widget.style)
            self.assertNotIn("crossAxisAlignment", widget.style)

    def test_container_with_child(self):
        c = Container(
            child=Text("Hello"),
            padding=EdgeInsets.all(16),
            bg="#FFFFFF",
            border_radius=8,
        )
        self.assertEqual(len(c.children), 1)
        self.assertEqual(c.style["padding"], {"left": 16, "top": 16, "right": 16, "bottom": 16})
        self.assertEqual(c.style["bg"], "#FFFFFFFF")

    def test_center_centers_child(self):
        c = Center(child=Text("Centred"))
        self.assertEqual(len(c.children), 1)

    def test_spacer_has_expand(self):
        s = Spacer(expand=2)
        self.assertEqual(s.expand, 2)

    def test_column_builder(self):
        col = Column(spacing=8)
        col.add(Text("A"), Text("B"))
        self.assertEqual(len(col.children), 2)


class TestInputWidgets(unittest.TestCase):
    def test_textfield(self):
        tf = TextField(value="Hello", hint="Enter text")
        self.assertEqual(tf.value, "Hello")

    def test_textfield_props(self):
        tf = TextField(password=True, multiline=False)
        self.assertTrue(tf.style["password"])

    def test_checkbox(self):
        cb = Checkbox(label="Agree", checked=True)
        self.assertTrue(cb.checked)
        self.assertEqual(cb.label, "Agree")

    def test_switch(self):
        sw = Switch(label="Wifi", active=True)
        self.assertTrue(sw.active)
        self.assertEqual(sw.label, "Wifi")


class TestImageIcon(unittest.TestCase):
    def test_image_src(self):
        img = Image(src="photo.png", width=200, height=200)
        self.assertEqual(img.src, "photo.png")
        self.assertEqual(img.style["width"], 200)

    def test_icon(self):
        ic = Icon(name="home", size=32, color="#FF0000")
        self.assertEqual(ic._icon_name, "home")
        self.assertIn("font", ic.style)


class TestEvents(unittest.TestCase):
    def test_event_handler_chaining(self):
        btn = Button("Go")
        btn.on_click(lambda d: None)
        self.assertIn("click", btn.event_handlers)

    def test_multiple_handlers(self):
        tf = TextField()
        tf.on_change(lambda d: None).on_submit(lambda d: None)
        self.assertIn("change", tf.event_handlers)
        self.assertIn("submit", tf.event_handlers)


class TestTreeWalk(unittest.TestCase):
    def test_walk_counts(self):
        tree = Column(children=[
            Text("A"),
            Row(children=[Text("B"), Text("C")]),
            Container(child=Text("D")),
        ])
        nodes = list(tree.walk())
        self.assertEqual(len(nodes), 7)  # Column + A + Row + B + C + Container + D

    def test_find_by_key(self):
        target = Text("Found me", key="target")
        tree = Column(children=[
            Text("A"),
            Row(children=[Text("B"), target]),
        ])
        found = tree.find_by_key("target")
        self.assertIsNotNone(found)
        self.assertEqual(found.value, "Found me")

    def test_find_by_key_missing(self):
        t = Text("Alone")
        self.assertIsNone(t.find_by_key("nope"))


if __name__ == "__main__":
    unittest.main()
