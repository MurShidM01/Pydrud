"""PSS (Pydrud Style Sheet) syntax tree and parser.

PSS supports type, class, and id selectors; compounds; descendant and direct
child combinators; comma-separated selector lists; and typed, schema-aware
style declarations. Parsing is non-fatal: malformed input is returned as
source-located diagnostics so an editor can keep the last known-good sheet.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from pydrud.core.styles.lexer import LexerError, Token, TokenKind, lex
from pydrud.core.styles.schema import normalize_key


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
    """A chain of compound selectors joined by CSS-like combinators."""

    compounds: tuple[CompoundSelector, ...] = ()
    combinators: tuple[str, ...] = ()  # one fewer than compounds


@dataclass
class DeclarationBlock:
    declarations: list[tuple[str, Any]] = field(default_factory=list)


@dataclass
class Rule:
    selector: Selector
    body: DeclarationBlock


@dataclass
class StyleSheet:
    rules: list[Rule] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    filename: str = ""


_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def _parse_value(source: str) -> Any:
    """Convert PSS scalar/JSON-style values to Python primitives.

    Bare names, CSS units, colour literals and renderer-specific function
    expressions remain strings. JSON arrays/objects are accepted for style
    properties whose schema kind is ``composite``.
    """
    raw = source.strip()
    if not raw:
        return ""
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower == "null":
        return None
    if _NUMBER.fullmatch(raw):
        try:
            number = float(raw) if any(c in raw for c in ".eE") else int(raw)
            if isinstance(number, float) and number.is_integer() and not any(
                    c in raw for c in ".eE"):
                return int(number)
            return number
        except (ValueError, OverflowError):  # pragma: no cover - guarded by regex
            return raw

    if raw[:1] in ("'", '"') and raw[-1:] == raw[:1]:
        try:
            value = ast.literal_eval(raw)
            if isinstance(value, str):
                return value
        except (SyntaxError, ValueError):
            return raw[1:-1]
        return raw[1:-1]

    if raw[:1] in ("{", "["):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            try:
                value = ast.literal_eval(raw)
                if isinstance(value, (dict, list, tuple)):
                    return value
            except (SyntaxError, ValueError):
                pass

    return raw


class Parser:
    """Recursive-descent parser with rule-level error recovery."""

    def __init__(self, tokens: list[Token], filename: str = "") -> None:
        self.tokens = tokens
        self.pos = 0
        self.filename = filename
        self.diagnostics: list[Diagnostic] = []

    def current(self) -> Token:
        return self.tokens[min(self.pos, len(self.tokens) - 1)]

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def advance(self) -> Token:
        token = self.current()
        if token.kind != TokenKind.EOF:
            self.pos += 1
        return token

    def error(self, message: str, token: Token | None = None,
              *, kind: str = "error") -> None:
        token = token or self.current()
        self.diagnostics.append(Diagnostic(
            filename=self.filename,
            line=token.line,
            col=token.col,
            message=message,
            kind=kind,
        ))

    def parse(self) -> StyleSheet:
        rules: list[Rule] = []
        while self.current().kind != TokenKind.EOF:
            before = self.pos
            try:
                rules.extend(self.parse_rule())
            except Exception as exc:  # keep the editor/runtime resilient
                self.error(f"Could not parse rule: {exc}")
                self.skip_to_next_rule()
            if self.pos == before:
                self.advance()
        return StyleSheet(
            rules=rules,
            diagnostics=self.diagnostics,
            filename=self.filename,
        )

    def parse_rule(self) -> list[Rule]:
        selectors = self.parse_selector_list()
        if self.current().kind != TokenKind.LBRACE:
            self.error("Expected '{' after selector")
            self.skip_to_next_rule()
            return []
        self.advance()
        body = self.parse_declarations()
        if self.current().kind == TokenKind.RBRACE:
            self.advance()
        else:
            self.error("Expected '}' to close declaration block")
        return [Rule(selector=selector, body=body) for selector in selectors]

    def parse_selector_list(self) -> list[Selector]:
        selectors: list[Selector] = []
        compounds: list[CompoundSelector] = []
        combinators: list[str] = []

        while self.current().kind not in (TokenKind.LBRACE, TokenKind.EOF,
                                          TokenKind.RBRACE):
            compound = self.parse_compound_selector()
            if compound is not None:
                compounds.append(compound)
                token = self.current()
                if token.kind == TokenKind.COMBINATOR and token.value in (" ", ">"):
                    combinators.append(token.value)
                    self.advance()
                    if self.current().kind in (
                            TokenKind.LBRACE, TokenKind.EOF, TokenKind.RBRACE):
                        self.error("Expected selector after combinator", token)
                        break
                    continue
                if token.kind == TokenKind.COMBINATOR and token.value == ",":
                    self._append_selector(selectors, compounds, combinators, token)
                    compounds, combinators = [], []
                    self.advance()
                    if self.current().kind in (
                            TokenKind.LBRACE, TokenKind.EOF, TokenKind.RBRACE):
                        self.error("Expected selector after ','", token)
                        break
                    continue
                if token.kind == TokenKind.LBRACE:
                    break
                if token.kind == TokenKind.EOF:
                    break
                self.error(f"Unexpected token {token.value!r} in selector", token)
                self._recover_selector()
                break

            token = self.current()
            self.error(f"Expected selector, got {token.kind.name}", token)
            self._recover_selector()
            break

        if compounds:
            self._append_selector(selectors, compounds, combinators, self.current())
        return selectors

    def _append_selector(
        self,
        selectors: list[Selector],
        compounds: list[CompoundSelector],
        combinators: list[str],
        token: Token,
    ) -> None:
        if not compounds:
            self.error("Empty selector", token)
            return
        if len(combinators) != len(compounds) - 1:
            self.error("Selector combinator is missing a compound selector", token)
            return
        selectors.append(Selector(tuple(compounds), tuple(combinators)))

    def parse_compound_selector(self) -> Optional[CompoundSelector]:
        widget_type: Optional[str] = None
        classes: list[str] = []
        id_value: Optional[str] = None
        consumed = False

        while True:
            token = self.current()
            if token.kind == TokenKind.TYPE_SEL:
                consumed = True
                if widget_type is not None:
                    self.error("A compound selector cannot contain two type selectors", token)
                widget_type = token.value
                self.advance()
            elif token.kind == TokenKind.CLASS_SEL:
                consumed = True
                # Preserve the established .name.Widget shorthand: a final
                # uppercase class in a multi-part compound is its widget type.
                if (widget_type is not None or id_value is not None) and token.value[:1].isupper():
                    widget_type = token.value
                else:
                    classes.append(token.value)
                self.advance()
            elif token.kind == TokenKind.ID_SEL:
                consumed = True
                if id_value is not None:
                    self.error("A compound selector cannot contain two id selectors", token)
                id_value = token.value
                self.advance()
            else:
                break

        if not consumed:
            return None
        if widget_type is None and len(classes) > 1 and classes[-1][:1].isupper():
            widget_type = classes.pop()
        # Keep source order but discard duplicated class names.
        unique_classes = tuple(dict.fromkeys(classes))
        return CompoundSelector(widget_type, unique_classes, id_value)

    def parse_declarations(self) -> DeclarationBlock:
        declarations: list[tuple[str, Any]] = []
        while self.current().kind not in (TokenKind.RBRACE, TokenKind.EOF):
            token = self.current()
            if token.kind == TokenKind.SEMI:
                self.advance()
                continue
            if token.kind != TokenKind.PROP:
                self.error(f"Expected property name, got {token.kind.name}", token)
                self._recover_declaration()
                continue

            property_token = self.advance()
            if self.current().kind != TokenKind.COLON:
                self.error("Expected ':' after property name", self.current())
                self._recover_declaration()
                continue
            self.advance()
            if self.current().kind != TokenKind.VALUE:
                self.error("Expected declaration value", self.current())
                self._recover_declaration()
                continue
            value_token = self.advance()

            canonical = normalize_key(property_token.value)
            property_name = canonical or property_token.value
            if canonical is None:
                self.error(
                    f"Unknown style property {property_token.value!r}",
                    property_token,
                    kind="warning",
                )
            declarations.append((property_name, _parse_value(value_token.value)))

            if self.current().kind == TokenKind.SEMI:
                self.advance()
            elif self.current().kind not in (TokenKind.RBRACE, TokenKind.EOF):
                self.error("Expected ';' between declarations", self.current())
                self._recover_declaration()

        return DeclarationBlock(declarations)

    def _recover_selector(self) -> None:
        while self.current().kind not in (
                TokenKind.COMBINATOR, TokenKind.LBRACE, TokenKind.RBRACE,
                TokenKind.EOF):
            self.advance()
        if self.current().kind == TokenKind.COMBINATOR:
            self.advance()

    def _recover_declaration(self) -> None:
        while self.current().kind not in (
                TokenKind.SEMI, TokenKind.RBRACE, TokenKind.EOF):
            self.advance()
        if self.current().kind == TokenKind.SEMI:
            self.advance()

    def skip_to_next_rule(self) -> None:
        """Skip a malformed rule body without consuming the next valid rule."""
        while self.current().kind not in (TokenKind.LBRACE, TokenKind.RBRACE,
                                          TokenKind.EOF):
            self.advance()
        if self.current().kind == TokenKind.LBRACE:
            self.advance()
            depth = 1
            while self.current().kind != TokenKind.EOF and depth:
                token = self.advance()
                if token.kind == TokenKind.LBRACE:
                    depth += 1
                elif token.kind == TokenKind.RBRACE:
                    depth -= 1
        elif self.current().kind == TokenKind.RBRACE:
            self.advance()


def parse_pss(source: str, filename: str = "") -> StyleSheet:
    """Parse *source* to a :class:`StyleSheet`, returning diagnostics on errors."""
    try:
        tokens = lex(source, filename)
    except (LexerError, TypeError) as exc:
        return StyleSheet(
            rules=[],
            diagnostics=[Diagnostic(
                filename=filename,
                line=getattr(exc, "line", 1),
                col=getattr(exc, "col", 1),
                message=str(exc),
            )],
            filename=filename,
        )
    parser = Parser(tokens, filename)
    return parser.parse()
