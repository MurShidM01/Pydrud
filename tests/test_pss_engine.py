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


class Column(Widget):
    _widget_type = "Column"


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

    def test_parse_css_style_composite_bare_keys(self):
        sheet = parse_pss(
            "Button { font: { size: 18, weight: 600, family: sans }; "
            "gradient: { colors: [red, #FFFFFF] }; }"
        )
        self.assertEqual(sheet.rules[0].body.declarations, [
            ("font", {"size": 18, "weight": 600, "family": "sans"}),
            ("gradient", {"colors": ["red", "#FFFFFF"]}),
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


class TestNewStyleKeys(unittest.TestCase):
    """The per-corner radius, ripple, shadow and blur keys added for the
    design system are recognised and normalise from their CSS spellings."""

    def test_new_keys_are_known(self):
        from pydrud.core.styles.schema import VALID_STYLE_KEYS

        for key in ("borderTopLeftRadius", "borderTopRightRadius",
                    "borderBottomLeftRadius", "borderBottomRightRadius",
                    "ripple"):
            self.assertIn(key, VALID_STYLE_KEYS)

    def test_kebab_spellings_normalise(self):
        from pydrud.core.styles.schema import normalize_key

        self.assertEqual(normalize_key("border-top-left-radius"),
                         "borderTopLeftRadius")
        self.assertEqual(normalize_key("border-bottom-right-radius"),
                         "borderBottomRightRadius")

    def test_blur_is_a_known_number_key(self):
        from pydrud.core.styles.schema import KEY_KIND, VALID_STYLE_KEYS

        self.assertIn("blur", VALID_STYLE_KEYS)
        self.assertEqual(KEY_KIND["blur"], "number")

    def test_blur_resolves_without_warnings(self):
        sheet = parse_pss("Container { blur: 12; }")
        result, warnings = resolve_styles(sheet, [Container(key="glass")])
        self.assertEqual(result["glass"].get("blur"), 12)
        self.assertEqual(warnings, [])

    def test_blur_is_declared_by_the_android_profile(self):
        sheet = parse_pss("Container { blur: 12; }")
        _, warnings = resolve_styles(
            sheet, [Container(key="glass")], AndroidRendererProfile())
        self.assertEqual(
            [w for w in warnings if "blur" in str(w)], [],
            "the Android renderer implements blur, so it must declare it")

    def test_shadow_accepts_number_and_composite(self):
        # A plain number and the full dict must both pass without a kind
        # warning, because ``shadow`` is intentionally dual-kind.
        for value in ("4", "{ offsetX: 0, offsetY: 2, blur: 8, color: #00000040 }"):
            source = f"Button {{ shadow: {value}; }}"
            sheet = parse_pss(source)
            _, warnings = resolve_styles(sheet, [Button(key="b")])
            kind_warnings = [w for w in warnings if "shadow" in str(w)]
            self.assertEqual(kind_warnings, [], f"unexpected warning for {value}")

    def test_space_between_alignment_resolves(self):
        source = "Container { mainAxisAlignment: space_between; }"
        sheet = parse_pss(source)
        result, _ = resolve_styles(sheet, [Container(key="row")])
        self.assertEqual(result["row"].get("mainAxisAlignment"),
                         "space_between")

    def test_composite_blocks_accept_semicolon_separators(self):
        # Inside a composite block the natural PSS separator is ';' (as in a
        # declaration block) as well as ','. Both must produce a real object
        # rather than one collapsed string value.
        source = (
            ".card {\n"
            "    shadow: {\n"
            "        color: #40000000;\n"
            "        offsetX: 0;\n"
            "        offsetY: 10;\n"
            "        blur: 24;\n"
            "        spread: 0;\n"
            "    };\n"
            "    gradient: { angle: 135; colors: [#FFFFFFFF, #FFF1F3FF]; stops: [0, 1] };\n"
            "}\n"
        )
        sheet = parse_pss(source)
        self.assertEqual(sheet.diagnostics, [])
        decls = dict(sheet.rules[0].body.declarations)
        self.assertEqual(decls["shadow"], {
            "color": "#40000000", "offsetX": 0, "offsetY": 10,
            "blur": 24, "spread": 0,
        })
        self.assertEqual(decls["gradient"], {
            "angle": 135, "colors": ["#FFFFFFFF", "#FFF1F3FF"], "stops": [0, 1],
        })


class TestPSSValueExpressions(unittest.TestCase):
    """The CSS numeric value language: calc/min/max/clamp/env and viewport units."""

    def setUp(self):
        from pydrud.core.styles.values import ValueContext

        self.context = ValueContext(
            width=360, height=640, safe_top=24, safe_bottom=34)

    def _eval(self, text, **overrides):
        from pydrud.core.styles.values import ValueContext, evaluate_expression

        context = ValueContext(
            width=overrides.get("width", self.context.width),
            height=overrides.get("height", self.context.height),
            safe_top=overrides.get("safe_top", self.context.safe_top),
            safe_bottom=overrides.get("safe_bottom", self.context.safe_bottom),
        )
        return evaluate_expression(text, context)

    def test_clamp_picks_the_viewport_proportional_ideal(self):
        self.assertAlmostEqual(self._eval("clamp(16px, 5vw, 24px)"), 18.0)

    def test_clamp_floor(self):
        self.assertAlmostEqual(self._eval("clamp(16px, 5vw, 24px)", width=200),
                               16.0)

    def test_clamp_ceiling(self):
        self.assertAlmostEqual(self._eval("clamp(16px, 5vw, 24px)", width=600),
                               24.0)

    def test_negative_clamp_matches_the_design(self):
        # `clamp(-12px, -2.5vw, -18px)` — CSS returns the min when max < min.
        self.assertAlmostEqual(self._eval("clamp(-12px, -2.5vw, -18px)"), -12.0)

    def test_max_with_calc_and_env(self):
        self.assertAlmostEqual(
            self._eval("max(16px, calc(18px + env(safe-area-inset-bottom)))"),
            52.0)

    def test_env_reports_a_defined_zero_inset(self):
        # A device that reports no inset still *defines* the variable, so the
        # value is 0 — the fallback only applies to an unknown name.
        self.assertAlmostEqual(
            self._eval("env(safe-area-inset-top, 4px)", safe_top=0), 0.0)

    def test_env_fallback_for_an_unknown_name(self):
        self.assertAlmostEqual(self._eval("env(viewport-foo, 4px)"), 4.0)

    def test_viewport_height_units(self):
        self.assertAlmostEqual(self._eval("100dvh"), 640.0)
        self.assertAlmostEqual(self._eval("50vh"), 320.0)

    def test_calc_arithmetic(self):
        self.assertAlmostEqual(self._eval("calc(18px + 6px * 2)"), 30.0)

    def test_vmin_uses_the_shorter_side(self):
        self.assertAlmostEqual(self._eval("10vmin"), 36.0)

    def test_unresolvable_fragments_are_left_alone(self):
        for text in ("100%", "50%", "430px", "#FF00AA", "red", "1.12s",
                     "calc(100% - 20px)", "sans-serif", "none"):
            self.assertIsNone(self._eval(text), f"{text!r} should not resolve")

    def test_evaluate_recurses_into_composites(self):
        from pydrud.core.styles.values import evaluate

        result = evaluate({"top": "clamp(18px, 7vh, 64px)", "color": "#FF0000"},
                          self.context)
        self.assertAlmostEqual(result["top"], 44.8)
        self.assertEqual(result["color"], "#FF0000")

    def test_decompose_transform(self):
        from pydrud.core.styles.values import decompose_transform

        self.assertEqual(decompose_transform("scale(.92)", self.context),
                         {"scale": 0.92})
        self.assertEqual(
            decompose_transform("translate(-50%,-50%) scale(.55)", self.context),
            {"scale": 0.55})
        self.assertEqual(decompose_transform("rotate(45deg)", self.context),
                         {"rotation": 45.0})

    def test_from_media_query_uses_live_metrics(self):
        from pydrud.core.responsive import MediaQuery
        from pydrud.core.styles.values import ValueContext

        previous = MediaQuery.width
        try:
            MediaQuery.update(width=411, height=891)
            context = ValueContext.from_media_query()
            self.assertAlmostEqual(context.width, 411.0)
            self.assertAlmostEqual(context.height, 891.0)
        finally:
            MediaQuery.update(width=previous)


class TestPSSAtRulesAndPseudo(unittest.TestCase):
    """Universal selector, pseudo-classes, @media and @keyframes parse."""

    def test_universal_and_pseudo_tokens(self):
        from pydrud.core.styles.lexer import TokenKind

        tokens = lex("* { a: 1; } .fab:active { b: 2; }")
        kinds = [t.kind for t in tokens]
        self.assertIn(TokenKind.UNIVERSAL_SEL, kinds)
        self.assertIn(TokenKind.PSEUDO, kinds)
        pseudos = [t.value for t in tokens if t.kind == TokenKind.PSEUDO]
        self.assertEqual(pseudos, [":active"])

    def test_at_rule_and_keyframe_tokens(self):
        from pydrud.core.styles.lexer import TokenKind

        tokens = lex("@media (max-width: 699px) { .a { b: 1 } }"
                     "@keyframes glow { 0% { opacity: 0 } to { opacity: 1 } }")
        self.assertIn(TokenKind.AT, [t.kind for t in tokens])
        self.assertIn(TokenKind.PRELUDE, [t.kind for t in tokens])
        keyframe_selectors = [t.value for t in tokens
                              if t.kind == TokenKind.KEYFRAME_SEL]
        self.assertEqual(keyframe_selectors, ["0%", "to"])

    def test_parse_root_variables(self):
        sheet = parse_pss(":root { --bg: #FFF; --heart: #E85D68; }")
        self.assertEqual(sheet.variables,
                         {"--bg": "#FFF", "--heart": "#E85D68"})

    def test_parse_media_condition(self):
        from pydrud.core.styles.parser import parse_media_condition

        sheet = parse_pss(
            "@media (max-width: 360px) and (min-height: 500px) { .a { b: 1 } }")
        condition = sheet.rules[0].media
        self.assertIsNotNone(condition)
        features = condition.alternatives[0]
        self.assertEqual([(f.name, f.op, f.value) for f in features],
                         [("width", "max", 360.0), ("height", "min", 500.0)])
        # A comma list is an OR of alternatives.
        self.assertEqual(
            len(parse_media_condition("(max-width: 1px), (min-width: 2px)"
                                      ).alternatives), 2)

    def test_parse_keyframes(self):
        sheet = parse_pss(
            "@keyframes glow { 0% { opacity: .18; transform: scale(.78) }"
            " 100% { opacity: 0 } }")
        glow = sheet.keyframes["glow"]
        self.assertEqual([f.offset for f in glow.frames], [0.0, 1.0])
        self.assertEqual(glow.frames[0].declarations,
                         [("opacity", 0.18), ("transform", "scale(.78)")])

    def test_parse_pseudo_on_compound(self):
        sheet = parse_pss(".fab:active { a: 1; }")
        compound = sheet.rules[0].selector.compounds[0]
        self.assertEqual(compound.classes, ("fab",))
        self.assertEqual([p.name for p in compound.pseudos], [":active"])

    def test_parse_box_and_border_shorthands(self):
        sheet = parse_pss(
            ".a { padding: 1px 2px 3px 4px; margin: 10px 0;"
            " border: 1px solid transparent; }")
        decls = dict(sheet.rules[0].body.declarations)
        self.assertEqual(decls["padding"],
                         {"top": "1px", "right": "2px",
                          "bottom": "3px", "left": "4px"})
        self.assertEqual(decls["margin"],
                         {"top": "10px", "bottom": "10px",
                          "left": 0, "right": 0})
        self.assertEqual(decls["border"],
                         {"width": "1px", "color": "transparent"})

    def test_single_value_box_shorthand_becomes_all_sides(self):
        # CSS `padding: 24` / `margin: 8px` is the uniform shorthand; the
        # renderer reads a composite, so a bare scalar must be wrapped.
        sheet = parse_pss(
            ".a { padding: 24; margin: 8px; padding-right: 4; }")
        decls = dict(sheet.rules[0].body.declarations)
        self.assertEqual(decls["padding"], {"all": 24})
        self.assertEqual(decls["margin"], {"all": "8px"})

    def test_animation_shorthand(self):
        from pydrud.core.styles.parser import parse_animation_shorthand

        self.assertEqual(
            parse_animation_shorthand("ring 1.12s .37s ease-out infinite"),
            {"name": "ring", "curve": "ease_out", "iterations": "infinite",
             "duration": 1120.0, "delay": 370.0})

    def test_transition_shorthand(self):
        from pydrud.core.styles.parser import parse_transition_shorthand

        self.assertEqual(
            parse_transition_shorthand("transform .12s ease, background .18s"),
            [{"property": "transform", "curve": "ease_in_out",
              "duration": 120.0},
             {"property": "background", "duration": 180.0}])


class TestPSSResolverCSSParity(unittest.TestCase):
    """The CSS authoring surface resolves against the widget tree."""

    def setUp(self):
        from pydrud.core.styles.values import ValueContext

        self.context = ValueContext(width=360, height=640, safe_bottom=34)

    def _resolve(self, source, root):
        sheet = parse_pss(source)
        return resolve_styles(sheet, root, context=self.context)

    def test_root_variable_resolves(self):
        root = Container(key="a", class_="app")
        result, _ = self._resolve(
            ":root { --bg: #F8F7F3; } .app { bg: var(--bg); }", root)
        self.assertEqual(result["a"]["bg"], "#F8F7F3")

    def test_variable_inherits_from_an_ancestor(self):
        child = Container(key="child", class_="tinted")
        root = Container(key="root", class_="running", children=[child])
        result, _ = self._resolve(
            ".running { --tint: #E85D68; } .tinted { bg: var(--tint); }", root)
        self.assertEqual(result["child"]["bg"], "#E85D68")

    def test_variable_fallback_and_unknown_warning(self):
        root = Container(key="a", class_="app")
        result, warnings = self._resolve(
            ".app { bg: var(--missing, #123456); }", root)
        self.assertEqual(result["a"]["bg"], "#123456")
        _, warnings = self._resolve(".app { bg: var(--nope); }", root)
        self.assertTrue(any("--nope" in w for w in warnings))

    def test_clamp_and_env_resolve_to_dp(self):
        root = Container(key="a", class_="app")
        result, _ = self._resolve(
            ".app { padding-top: max(16px, calc(18px + env(safe-area-inset-bottom)));"
            " width: clamp(150px, 50vw, 230px); }", root)
        self.assertAlmostEqual(result["a"]["padding"]["top"], 52.0)
        self.assertAlmostEqual(result["a"]["width"], 180.0)

    def test_media_max_width_applies_and_min_width_is_skipped(self):
        root = Container(key="a", class_="fab")
        result, _ = self._resolve(
            "@media (max-width: 699px) { .fab { right: 14px; } }"
            "@media (min-width: 700px) { .fab { right: 40px; } }", root)
        self.assertAlmostEqual(result["a"]["right"], 14.0)

    def test_active_becomes_a_press_subspec(self):
        root = Container(key="a", class_="fab")
        result, _ = self._resolve(
            ".fab:active { transform: scale(.92); }", root)
        self.assertEqual(result["a"]["press"], {"scale": 0.92})

    def test_structural_pseudo_classes(self):
        rows = [Container(key=f"r{i}", class_="row") for i in range(3)]
        root = Column(key="list", class_="list", children=rows)
        result, _ = self._resolve(
            ".list .row:first-child { bg: #111; }"
            ".list .row:last-child { bg: #333; }"
            ".list .row:nth-child(2) { bg: #222; }", root)
        self.assertEqual(result["r0"]["bg"], "#111")
        self.assertEqual(result["r1"]["bg"], "#222")
        self.assertEqual(result["r2"]["bg"], "#333")

    def test_not_pseudo_class(self):
        root = Column(key="root", children=[
            Container(key="a", class_="item special"),
            Container(key="b", class_="item"),
        ])
        result, _ = self._resolve(".item:not(.special) { bg: #0F0; }", root)
        self.assertNotIn("bg", result.get("a", {}))
        self.assertEqual(result["b"]["bg"], "#0F0")

    def test_universal_selector_applies_to_every_widget(self):
        root = Column(key="root", children=[Container(key="a"),
                                            Container(key="b")])
        result, _ = self._resolve("* { opacity: .5; }", root)
        self.assertEqual(result["a"]["opacity"], 0.5)
        self.assertEqual(result["b"]["opacity"], 0.5)

    def test_keyframes_animation_attaches(self):
        glow = Container(key="glow", class_="glow")
        root = Container(key="root", class_="running", children=[glow])
        result, _ = self._resolve(
            ".running .glow { animation: glow 1.12s ease-out infinite; }"
            "@keyframes glow { 0% { opacity: .18; transform: scale(.78) }"
            " 100% { opacity: 0; transform: scale(1.7) } }", root)
        spec = result["glow"]["animation"]
        self.assertEqual(spec["duration"], 1120.0)
        self.assertEqual(spec["iterations"], "infinite")
        self.assertEqual(spec["keyframes"][0][1],
                         {"opacity": 0.18, "scale": 0.78})

    def test_transition_attaches_a_spec(self):
        root = Container(key="a", class_="dot")
        result, _ = self._resolve(
            ".dot { transition: background .2s ease; }", root)
        self.assertEqual(result["a"]["transition"],
                         [{"property": "background", "curve": "ease_in_out",
                           "duration": 200.0}])

    def test_font_longhands_fold_into_the_composite(self):
        root = Text(key="a", class_="title")
        result, _ = self._resolve(
            ".title { font-size: 24px; font-weight: 700; color: #111; }", root)
        self.assertEqual(result["a"]["font"],
                         {"size": 24.0, "weight": 700, "color": "#111"})

    def test_box_longhands_fold_and_expand_all(self):
        root = Container(key="a", class_="card")
        result, _ = self._resolve(
            ".card { padding: { all: 5 }; padding-top: 12px; }", root)
        self.assertEqual(result["a"]["padding"],
                         {"left": 5.0, "top": 12.0, "right": 5.0, "bottom": 5.0})

    def test_border_longhands_fold(self):
        root = Container(key="a", class_="ring")
        result, _ = self._resolve(
            ".ring { border: 1px solid transparent; border-color: #E85D68; }",
            root)
        self.assertEqual(result["a"]["border"],
                         {"width": 1.0, "color": "#E85D68"})

    def test_percentage_radius_becomes_a_circle(self):
        root = Container(key="a", class_="dot")
        result, _ = self._resolve(".dot { border-radius: 50%; }", root)
        self.assertEqual(result["a"]["borderRadius"], 999)

    def test_web_only_declarations_are_dropped_with_one_warning(self):
        root = Container(key="a", class_="app")
        result, warnings = self._resolve(
            "* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }"
            ".app { display: flex; }", root)
        self.assertNotIn("boxSizing", result["a"])
        self.assertNotIn("display", result["a"])
        ignored = [w for w in warnings if "web-only" in w]
        self.assertEqual(len(ignored), 1)


class TestPSSSchemaParity(unittest.TestCase):
    """The schema recognises the CSS spellings the fold relies on."""

    def test_css_aliases_normalise(self):
        from pydrud.core.styles.schema import normalize_key

        self.assertEqual(normalize_key("font-size"), "fontSize")
        self.assertEqual(normalize_key("padding-top"), "paddingTop")
        self.assertEqual(normalize_key("border-color"), "borderColor")
        self.assertEqual(normalize_key("background-color"), "bg")
        self.assertEqual(normalize_key("background"), "bg")
        self.assertEqual(normalize_key("z-index"), "zIndex")
        self.assertEqual(normalize_key("gap"), "spacing")
        self.assertEqual(normalize_key("-webkit-appearance"), "appearance")

    def test_web_only_keys_are_recognised(self):
        from pydrud.core.styles.schema import (
            VALID_STYLE_KEYS, WEB_ONLY_STYLE_KEYS)

        for key in ("display", "boxSizing", "pointerEvents", "flexDirection"):
            self.assertIn(key, WEB_ONLY_STYLE_KEYS)
            self.assertIn(key, VALID_STYLE_KEYS)


if __name__ == "__main__":
    unittest.main()
