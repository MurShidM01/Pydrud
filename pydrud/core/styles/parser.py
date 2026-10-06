"""
PSS (Pydrud Style Sheet) AST and parser.

AST nodes
---------
* ``StyleSheet`` — top-level container of rules
* ``Rule``       — a selector + declaration block
* ``Selector``   — one or more compound selectors joined by combinators
* ``CompoundSelector`` — type, class, and/or id components
* ``DeclarationBlock`` — ordered list of (key, value) pairs
* ``Diagnostic`` — error/warning with file, line, column

Parser rules
------------
* Type selector: ``Button { color: red; }``
* Class selector: ``.primary { bg: #FF0000; }``
* Id selector: ``#header { padding: 10; }``
* Compound selector: ``.primary.Button { bg: red; }``
* Descendant combinator (space): ``.sidebar Button { bg: blue; }``
* Direct-child combinator (``>``): ``.card > Button { bg: green; }``
* List combinator (comma): ``.btn, .link { bg: red; }``
* Kebab-case keys normalised via :func:`pydrud.core.styles.normalize_key`

Diagnostics
-----------
Errors carry ``(filename, line, col, message)`` so callers can surface
clear messages. The parser performs basic error recovery: on a syntax
error it skips tokens until the next ``}`` (or EOF) and continues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pydrud.core.styles.lexer import Token, TokenKind, LexerError


@dataclass(frozen=True)
class Diagnostic:
    filename: str
    line: int
    col: int
    message: str
    kind: str = "error"  # "error" | "warning"


@dataclass
class CompoundSelector:
    widget_type: Optional[str] = None
    classes: tuple[str, ...] = ()
    id: Optional[str] = None


@dataclass
class Selector:
    """One or more compound selectors separated by combinators."""
    compounds: tuple[CompoundSelector, ...] = ()
    combinators: tuple[str, ...] = ()  # same length as compounds minus 1


@dataclass
class DeclarationBlock:
    declarations: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Rule:
    selector: Selector
    body: DeclarationBlock


@dataclass
class StyleSheet:
    rules: list[Rule] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    filename: str = ""


class Parser:
    def __init__(self, tokens: list[Token], filename: str = "") -> None:
        self.tokens = tokens
        self.pos = 0
        self.filename = filename
        self.diagnostics: list[Diagnostic] = []

    def current(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if 0 <= idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # EOF

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind: TokenKind, value: str | None = None) -> Token:
        tok = self.current()
        if tok.kind != kind or (value is not None and tok.value != value):
            self.error(
                f"Expected {kind.name} {value!r}"
                if value else f"Expected {kind.name}",
            )
        return self.advance()

    def error(self, message: str) -> None:
        tok = self.current()
        self.diagnostics.append(Diagnostic(
            filename=self.filename, line=tok.line, col=tok.col, message=message,
        ))

    def parse(self) -> StyleSheet:
        rules: list[Rule] = []
        while self.current().kind != TokenKind.EOF:
            try:
                rule = self.parse_rule()
                if rule is not None:
                    rules.append(rule)
            except Exception:
                self.skip_to_next_rule()
        return StyleSheet(rules=rules, diagnostics=self.diagnostics, filename=self.filename)

    def parse_rule(self) -> Optional[Rule]:
        selector = self.parse_selector()
        if selector is None:
            return None
        self.expect(TokenKind.LBRACE)
        body = self.parse_declarations()
        self.expect(TokenKind.RBRACE)
        return Rule(selector=selector, body=body)

    def parse_selector(self) -> Optional[Selector]:
        compounds: list[CompoundSelector] = []
        combinators: list[str] = []

        while True:
            comp = self.parse_compound_selector()
            if comp is None:
                break
            compounds.append(comp)
            tok = self.current()
            if tok.kind == TokenKind.COMBINATOR:
                combinators.append(tok.value)
                self.advance()
            elif tok.kind in (TokenKind.LBRACE, TokenKind.EOF, TokenKind.RBRACE):
                break
            else:
                # unexpected token — skip to recover
                self.error(f"Unexpected token {tok.value!r}")
                break

        if not compounds:
            return None
        return Selector(
            compounds=tuple(compounds),
            combinators=tuple(combinators),
        )

    def parse_compound_selector(self) -> Optional[CompoundSelector]:
        widget_type: Optional[str] = None
        classes: list[str] = []
        id_val: Optional[str] = None

        while True:
            tok = self.current()
            if tok.kind == TokenKind.TYPE_SEL:
                widget_type = tok.value
                self.advance()
            elif tok.kind == TokenKind.CLASS_SEL:
                # If we've already seen a type or id in this compound, and
                # the class starts with uppercase, treat it as part of a
                # compound selector (e.g. ".btn.Button"). Otherwise keep it
                # as a pure class selector.
                if (widget_type is not None or id_val is not None) and \
                        tok.value and tok.value[0].isupper():
                    widget_type = tok.value
                    self.advance()
                else:
                    classes.append(tok.value)
                    self.advance()
            elif tok.kind == TokenKind.ID_SEL:
                id_val = tok.value
                self.advance()
            else:
                break

        # Post-process: when a compound starts with classes only and the last
        # class looks like a widget type (uppercase start), promote it.
        # This handles patterns like ".btn.Button" where both tokens are
        # CLASS_SEL but the intent is "class btn on a Button widget".
        if not widget_type and classes and len(classes) > 1 \
                and classes[-1][0].isupper():
            widget_type = classes.pop()

        if widget_type is None and not classes and id_val is None:
            return None
        return CompoundSelector(
            widget_type=widget_type,
            classes=tuple(classes),
            id=id_val,
        )

    def parse_declarations(self) -> DeclarationBlock:
        decls: list[tuple[str, str]] = []
        while self.current().kind not in (TokenKind.RBRACE, TokenKind.EOF):
            prop_tok = self.current()
            if prop_tok.kind != TokenKind.PROP:
                self.error(f"Expected property name, got {prop_tok.kind.name}")
                self.advance()
                continue
            self.advance()
            tok = self.current()
            if tok.kind == TokenKind.COLON:
                self.advance()
            else:
                self.error("Expected ':' after property name")
                # Skip to semicolon or brace to recover
                while self.current().kind not in (TokenKind.SEMI, TokenKind.RBRACE, TokenKind.EOF):
                    self.advance()
                if self.current().kind == TokenKind.SEMI:
                    self.advance()
                continue
            # value runs until semicolon or brace
            parts: list[str] = []
            while self.current().kind not in (TokenKind.SEMI, TokenKind.RBRACE, TokenKind.EOF):
                t = self.advance()
                parts.append(t.value)
            if self.current().kind == TokenKind.SEMI:
                self.advance()
            decls.append((prop_tok.value, " ".join(parts)))
        return DeclarationBlock(declarations=decls)

    def skip_to_next_rule(self) -> None:
        """Skip tokens until we hit the next rule start or EOF."""
        while self.current().kind != TokenKind.EOF:
            if self.current().kind == TokenKind.RBRACE:
                self.advance()
                return
            self.advance()


def parse_pss(source: str, filename: str = "") -> StyleSheet:
    """Parse a .pss stylesheet source string into a :class:`StyleSheet`."""
    from pydrud.core.styles.lexer import lex
    tokens = lex(source, filename)
    parser = Parser(tokens, filename)
    return parser.parse()
