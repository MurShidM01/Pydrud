"""
Unit tests for Pydrud styling helpers.
"""

import unittest
from pydrud.widgets.styling import Style, EdgeInsets, Alignment, FontStyle, Border, BorderRadius


class TestStyleBuilder(unittest.TestCase):
    def test_basic_style(self):
        s = Style().bg("#FF0000").width(100).height(50).build()
        self.assertEqual(s["bg"], "#FFFF0000")
        self.assertEqual(s["width"], 100)
        self.assertEqual(s["height"], 50)

    def test_color_normalisation(self):
        s = Style().bg("FF0000").build()
        self.assertEqual(s["bg"], "#FFFF0000")

    def test_padding_edge_insets(self):
        s = Style().padding(EdgeInsets.all(16)).build()
        self.assertEqual(s["padding"], {"left": 16, "top": 16, "right": 16, "bottom": 16})

    def test_padding_value(self):
        s = Style().padding(EdgeInsets.symmetric(horizontal=10, vertical=20)).build()
        self.assertEqual(s["padding"]["left"], 10)
        self.assertEqual(s["padding"]["right"], 10)
        self.assertEqual(s["padding"]["top"], 20)
        self.assertEqual(s["padding"]["bottom"], 20)

    def test_font_style(self):
        s = Style().font(FontStyle(size=18, color="#333333", weight=700, italic=True)).build()
        font = s["font"]
        self.assertEqual(font["size"], 18)
        self.assertEqual(font["weight"], 700)
        self.assertTrue(font["italic"])

    def test_margin_float(self):
        s = Style().margin(8).build()
        self.assertEqual(s["margin"], {"all": 8})


class TestEdgeInsets(unittest.TestCase):
    def test_all(self):
        e = EdgeInsets.all(10)
        self.assertEqual(e.left, 10)
        self.assertEqual(e.top, 10)
        self.assertEqual(e.right, 10)
        self.assertEqual(e.bottom, 10)

    def test_symmetric(self):
        e = EdgeInsets.symmetric(horizontal=5, vertical=15)
        self.assertEqual(e.left, 5)
        self.assertEqual(e.right, 5)
        self.assertEqual(e.top, 15)
        self.assertEqual(e.bottom, 15)

    def test_only(self):
        e = EdgeInsets.only(left=1, top=2, right=3, bottom=4)
        self.assertEqual(e.left, 1)
        self.assertEqual(e.top, 2)
        self.assertEqual(e.right, 3)
        self.assertEqual(e.bottom, 4)

    def test_to_dict(self):
        e = EdgeInsets.all(12)
        self.assertEqual(e.to_dict(), {"left": 12, "top": 12, "right": 12, "bottom": 12})


class TestAlignment(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(Alignment.center, "center")
        self.assertEqual(Alignment.top_left, "topLeft")
        self.assertEqual(Alignment.bottom_right, "bottomRight")


class TestFontStyle(unittest.TestCase):
    def test_empty(self):
        f = FontStyle()
        self.assertEqual(f.to_dict(), {})

    def test_full(self):
        f = FontStyle(size=14, color="#FFF", weight=600, italic=True, family="sans")
        d = f.to_dict()
        self.assertEqual(d["size"], 14)
        self.assertEqual(d["color"], "#FFF")
        self.assertEqual(d["weight"], 600)
        self.assertTrue(d["italic"])
        self.assertEqual(d["family"], "sans")


class TestBorder(unittest.TestCase):
    def test_default(self):
        b = Border()
        self.assertEqual(b.left.color, "#FF000000")
        self.assertEqual(b.left.width, 1.0)

    def test_custom(self):
        b = Border(color="#FF00FF00", width=2)
        d = b.to_dict()
        self.assertEqual(d["left"]["color"], "#FF00FF00")
        self.assertEqual(d["left"]["width"], 2)
        self.assertEqual(d["top"]["color"], "#FF00FF00")


class TestBorderRadius(unittest.TestCase):
    def test_creation(self):
        br = BorderRadius(12)
        self.assertEqual(br.radius, 12)
        self.assertEqual(br.to_dict(), {"radius": 12})


class TestStyleChaining(unittest.TestCase):
    def test_full_example(self):
        s = (
            Style()
            .bg("#FFFFFF")
            .padding(EdgeInsets.all(16))
            .border(Border("#CCCCCC", 1))
            .border_radius(8)
            .font(FontStyle(size=16, color="#FF0000"))
            .width(200)
            .height(48)
            .alignment(Alignment.center)
            .elevation(4)
            .build()
        )
        self.assertEqual(s["bg"], "#FFFFFFFF")
        self.assertEqual(s["width"], 200)
        self.assertEqual(s["height"], 48)
        self.assertEqual(s["borderRadius"], 8)
        self.assertEqual(s["alignment"], "center")
        self.assertEqual(s["elevation"], 4)


if __name__ == "__main__":
    unittest.main()
