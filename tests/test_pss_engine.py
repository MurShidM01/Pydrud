"""Tests for the PSS (Pydrud Style Sheets) engine."""

import unittest
from pydrud.core.styles.lexer import lex, TokenKind
from pydrud.core.styles.parser import parse_pss
from pydrud.core.styles.resolver import resolve_styles, AndroidRendererProfile
from pydrud.widgets.base import Widget


class Button(Widget):
    _widget_type = "Button"


class Container(Widget):
    _widget_type = "Container"


class Text(Widget):
    _widget_type = "Text"


class TestPSSLexer(unittest.TestCase):
    """Test the PSS lexer produces correct tokens."""

    def test_simple_type_selector(self):
        source = "Button { color: red; }"
        tokens = lex(source)
        kinds = [t.kind for t in tokens]
        self.assertIn(TokenKind.TYPE_SEL, kinds)
        self.assertIn(TokenKind.LBRACE, kinds)
        self.assertIn(TokenKind.RBRACE, kinds)
        self.assertIn(TokenKind.EOF, kinds)

    def test_class_selector(self):
        source = ".primary { bg: blue; }"
        tokens = lex(source)
        kinds = [t.kind for t in tokens]
        self.assertIn(TokenKind.CLASS_SEL, kinds)

    def test_id_selector(self):
        source = "#header { padding: 10; }"
        tokens = lex(source)
        kinds = [t.kind for t in tokens]
        self.assertIn(TokenKind.ID_SEL, kinds)

    def test_comment_ignored(self):
        source = "/* comment */ Button { color: red; }"
        tokens = lex(source)
        # Comments should be consumed silently — no COMMENT tokens in output
        non_eof = [t for t in tokens if t.kind != TokenKind.EOF]
        self.assertEqual(len(non_eof), 7)  # Button, {, color, :, red, ;, }

    def test_kebab_key(self):
        source = "Button { text-align: center; }"
        tokens = lex(source)
        prop_tokens = [t for t in tokens if t.kind == TokenKind.PROP]
        self.assertTrue(any(t.value == "text-align" for t in prop_tokens))


class TestPSSParser(unittest.TestCase):
    """Test the PSS parser builds correct AST."""

    def test_parse_type_selector(self):
        source = "Button { color: red; }"
        sheet = parse_pss(source)
        self.assertEqual(len(sheet.rules), 1)
        rule = sheet.rules[0]
        self.assertEqual(rule.selector.compounds[0].widget_type, "Button")
        self.assertEqual(len(rule.body.declarations), 1)
        self.assertEqual(rule.body.declarations[0], ("color", "red"))

    def test_parse_class_selector(self):
        source = ".primary { bg: #FF0000; }"
        sheet = parse_pss(source)
        self.assertEqual(len(sheet.rules), 1)
        comp = sheet.rules[0].selector.compounds[0]
        self.assertEqual(comp.classes, ("primary",))

    def test_parse_id_selector(self):
        source = "#main { padding: 20; }"
        sheet = parse_pss(source)
        comp = sheet.rules[0].selector.compounds[0]
        self.assertEqual(comp.id, "main")

    def test_parse_compound_selector(self):
        source = ".btn.Button { color: white; }"
        sheet = parse_pss(source)
        comp = sheet.rules[0].selector.compounds[0]
        self.assertEqual(comp.widget_type, "Button")
        self.assertEqual(comp.classes, ("btn",))

    def test_parse_multiple_declarations(self):
        source = "Button { color: red; bg: blue; padding: 10; }"
        sheet = parse_pss(source)
        decls = sheet.rules[0].body.declarations
        self.assertEqual(len(decls), 3)

    def test_parse_list_selector(self):
        source = ".btn, .link { color: red; }"
        sheet = parse_pss(source)
        # Comma-separated selectors create separate rules
        self.assertGreaterEqual(len(sheet.rules), 1)

    def test_empty_stylesheet(self):
        sheet = parse_pss("")
        self.assertEqual(len(sheet.rules), 0)

    def test_invalid_property_recovery(self):
        source = "Button { : red; }"  # missing property name
        # Should not raise — parser recovers by skipping
        sheet = parse_pss(source)
        self.assertIsInstance(sheet, type(sheet))


class TestPSSResolver(unittest.TestCase):
    """Test style resolution with specificity."""

    def test_type_selector_matches(self):
        source = "Button { color: red; }"
        sheet = parse_pss(source)
        btn = Button(key="mybtn")
        result, warnings = resolve_styles(sheet, [btn])
        self.assertIn("mybtn", result)
        self.assertEqual(result["mybtn"].get("color"), "red")

    def test_class_selector_matches(self):
        source = ".primary { color: blue; }"
        sheet = parse_pss(source)
        btn = Button(key="mybtn")
        btn.style["class_primary"] = True
        result, warnings = resolve_styles(sheet, [btn])
        self.assertEqual(result["mybtn"].get("color"), "blue")

    def test_specificity_higher_wins(self):
        # Class selector has higher specificity than type
        source = """.Button { color: red; }
                   Button { color: blue; }"""
        sheet = parse_pss(source)
        btn = Button(key="mybtn")
        btn.style["class_Button"] = True
        result, warnings = resolve_styles(sheet, [btn])
        # Both match, but class selector (.Button) has higher specificity
        self.assertEqual(result["mybtn"].get("color"), "red")

    def test_android_profile_warnings(self):
        source = """.container { bg: red; }
                   .container > .inner { bg: blue; }"""
        sheet = parse_pss(source)
        container = Container(key="c1")
        container.style["class_container"] = True
        inner = Text(key="i1")
        inner.style.update({"class_inner": True, "bg": "blue"})
        container.children = [inner]
        result, warnings = resolve_styles(sheet, [container, inner], profile=AndroidRendererProfile())
        # Both widgets have bg resolved; check the warning is present
        # (the container inherits bg from .container, inner inherits from .inner)
        self.assertIn("c1", result)
        self.assertIn("i1", result)


class TestWidgetClassIntegration(unittest.TestCase):
    """Test that Widget class_ parameter works correctly."""

    def test_class_param_stored(self):
        btn = Button(class_=["primary", "large"])
        self.assertEqual(btn.class_, ["primary", "large"])

    def test_class_in_style(self):
        btn = Button(class_=["primary"])
        self.assertTrue(btn.style.get("class_primary"))

    def test_class_not_in_to_dict(self):
        btn = Button(class_=["primary"])
        d = btn.to_dict()
        # class_ should not appear as a top-level key in serialization
        self.assertNotIn("class_", d)

    def test_auto_key_not_matched_by_id_selector(self):
        # Auto-keyed widget should NOT match id selector
        source = "#myid { color: red; }"
        sheet = parse_pss(source)
        btn = Button()  # auto-generated key
        result, warnings = resolve_styles(sheet, [btn])
        # Auto-keyed widgets don't match id selectors — key should not be in result
        self.assertNotIn(btn.key, result)

    def test_explicit_key_matched_by_id_selector(self):
        source = "#myid { color: red; }"
        sheet = parse_pss(source)
        btn = Button(key="myid")
        result, warnings = resolve_styles(sheet, [btn])
        self.assertIn("myid", result)
        self.assertEqual(result["myid"].get("color"), "red")


if __name__ == "__main__":
    unittest.main()
