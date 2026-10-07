"""Tests for the PSS (Pydrud Style Sheets) engine."""

import unittest
from pydrud.core.styles.lexer import lex, TokenKind
from pydrud.core.styles.parser import parse_pss
from pydrud.core.styles.resolver import resolve_styles
from pydrud.platforms.android.styles import AndroidRendererProfile
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
        self.assertEqual(len(non_eof), 7)  # Button, {, color, :, value, ;, }
        self.assertIn(TokenKind.VALUE, [token.kind for token in tokens])

    def test_kebab_key(self):
        source = "Button { text-align: center; }"
        tokens = lex(source)
        prop_tokens = [t for t in tokens if t.kind == TokenKind.PROP]
        self.assertTrue(any(t.value == "text-align" for t in prop_tokens))

    def test_color_hash_is_a_value_not_an_id_selector(self):
        tokens = lex("Button { bg: #FF00AA; }")
        self.assertEqual(
            [token.value for token in tokens if token.kind == TokenKind.VALUE],
            ["#FF00AA"],
        )

    def test_descendant_and_child_combinators(self):
        tokens = lex(".sidebar Button > .primary { color: blue; }")
        combinators = [token.value for token in tokens
                       if token.kind == TokenKind.COMBINATOR]
        self.assertEqual(combinators, [" ", ">"])


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

    def test_parse_multiple_declarations_and_typed_values(self):
        source = 'Button { color: red; bg: #FF00AA; opacity: 0.5; visible: false; }'
        sheet = parse_pss(source)
        decls = sheet.rules[0].body.declarations
        self.assertEqual(decls, [
            ("color", "red"), ("bg", "#FF00AA"),
            ("opacity", 0.5), ("visible", False),
        ])

    def test_parse_composite_json_value_and_normalized_key(self):
        sheet = parse_pss('Button { text-align: center; padding: {"all": 12}; }')
        self.assertEqual(sheet.rules[0].body.declarations, [
            ("textAlign", "center"), ("padding", {"all": 12}),
        ])

    def test_parse_list_selector(self):
        source = ".btn, .link { color: red; }"
        sheet = parse_pss(source)
        # A selector list expands to separate rules with a shared declaration block.
        self.assertEqual(len(sheet.rules), 2)
        self.assertEqual(sheet.rules[0].body.declarations,
                         sheet.rules[1].body.declarations)

    def test_parse_combinators(self):
        sheet = parse_pss(".sidebar Button > .primary { bg: blue; }")
        selector = sheet.rules[0].selector
        self.assertEqual(selector.combinators, (" ", ">"))
        self.assertEqual(len(selector.compounds), 3)

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

    def test_class_selector_matches_python_only_class_attribute(self):
        source = ".primary { color: blue; }"
        sheet = parse_pss(source)
        btn = Button(key="mybtn", class_=["primary"])
        result, warnings = resolve_styles(sheet, [btn])
        self.assertEqual(result["mybtn"].get("color"), "blue")

    def test_legacy_class_style_marker_still_matches(self):
        sheet = parse_pss(".primary { color: blue; }")
        btn = Button(key="mybtn")
        btn.style["class_primary"] = True
        result, _ = resolve_styles(sheet, [btn])
        self.assertEqual(result["mybtn"].get("color"), "blue")

    def test_specificity_higher_wins(self):
        # Class selector has higher specificity than type
        source = """.Button { color: red; }
                   Button { color: blue; }"""
        sheet = parse_pss(source)
        btn = Button(key="mybtn", class_=["Button"])
        result, warnings = resolve_styles(sheet, [btn])
        # Both match, but class selector (.Button) has higher specificity
        self.assertEqual(result["mybtn"].get("color"), "red")

    def test_descendant_and_direct_child_matching(self):
        root = Container(key="root", class_=["sidebar"])
        middle = Container(key="middle")
        direct = Button(key="direct", class_=["primary"])
        nested = Container(key="nested", children=[Button(
            key="nested-button", class_=["primary"])])
        root.children = [middle, direct, nested]
        sheet = parse_pss(
            ".sidebar Button { color: blue; }\n"
            ".sidebar > .primary { bg: green; }"
        )
        result, _ = resolve_styles(sheet, root)
        self.assertEqual(result["direct"]["bg"], "green")
        self.assertEqual(result["direct"]["color"], "blue")
        self.assertEqual(result["nested-button"]["color"], "blue")
        self.assertNotIn("bg", result["nested-button"])

    def test_android_profile_is_supplied_from_the_platform_layer(self):
        sheet = parse_pss("Button { bg: #FF0000; }")
        button = Button(key="hero")
        result, warnings = resolve_styles(
            sheet, [button], profile=AndroidRendererProfile())
        self.assertIn("hero", result)
        self.assertTrue(any("Button" in warning and "background" in warning
                            for warning in warnings))


class TestWidgetClassIntegration(unittest.TestCase):
    """Test that Widget class_ parameter works correctly."""

    def test_class_param_stored(self):
        btn = Button(class_=["primary", "large"])
        self.assertEqual(btn.class_, ["primary", "large"])

    def test_class_is_separate_from_inline_style(self):
        btn = Button(class_=["primary"])
        self.assertEqual(btn.class_, ["primary"])
        self.assertNotIn("class_primary", btn.style)

    def test_class_attribute_and_legacy_markers_are_not_serialized(self):
        btn = Button(class_=["primary"], style={"class_legacy": True, "color": "red"})
        d = btn.to_dict()
        self.assertNotIn("class_", d)
        self.assertNotIn("class_primary", d["style"])
        self.assertNotIn("class_legacy", d["style"])
        self.assertEqual(d["style"]["color"], "red")

    def test_class_attribute_is_not_a_native_ignored_property(self):
        from pydrud.compatibility import NATIVE_IGNORED_PROPS

        self.assertFalse(any(
            "class_" in props for props in NATIVE_IGNORED_PROPS.values()))

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
