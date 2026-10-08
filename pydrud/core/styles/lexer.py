"""Lexer for PSS (Pydrud Style Sheets).

PSS uses CSS-like selectors and declarations, but declaration values are
captured as complete source fragments. This keeps colours, units, strings,
functions, lists, and object-valued styles intact for the parser instead of
mistaking value punctuation (notably ``#`` in a colour) for selector syntax.

The lexer tracks a small **mode stack** so the same characters mean different
things in different CSS contexts:

* ``selector`` — the top level and the body of a rule-list at-rule
  (``@media``); selectors, at-rules, and ``{`` appear here.
* ``declarations`` — a rule body; ``property: value`` pairs appear here.
* ``keyframes`` — the body of ``@keyframes``; ``from`` / ``to`` / ``45%``
  keyframe selectors appear here.

The stack is what lets ``@keyframes glow { 0% { opacity: 0 } }`` nest a
declaration block inside a keyframe block inside a rule-list context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    TYPE_SEL = auto()
    CLASS_SEL = auto()
    ID_SEL = auto()
    UNIVERSAL_SEL = auto()
    PSEUDO = auto()
    COMBINATOR = auto()
    AT = auto()
    PRELUDE = auto()
    KEYFRAME_SEL = auto()
    LBRACE = auto()
    RBRACE = auto()
    PROP = auto()
    COLON = auto()
    VALUE = auto()
    SEMI = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    line: int
    col: int


class LexerError(RuntimeError):
    """Lexical error with line and column context."""

    def __init__(self, message: str, line: int, col: int) -> None:
        super().__init__(message)
        self.line = line
        self.col = col


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
#: A type selector. Pydrud widget types are capitalised, but a lower-case
#: element selector (``html``/``body``/``button``) is accepted too so a rule
#: copied from a web stylesheet lexes instead of failing; it simply matches
#: no widget.
_TYPE_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CUSTOM_PROPERTY = re.compile(r"--[A-Za-z0-9_-]+")
#: A vendor-prefixed property (``-webkit-appearance``); normalised by the
#: schema so the prefix does not turn into an "unknown property" error.
_VENDOR_PROPERTY = re.compile(r"-[A-Za-z][A-Za-z0-9_-]*")
_AT_NAME = re.compile(r"-?[A-Za-z_][A-Za-z0-9_-]*")
_NUMBER = re.compile(r"(?:\d+\.?\d*|\.\d+)")

#: Lexer modes (see the module docstring).
_MODE_SELECTOR = "selector"
_MODE_DECLS = "declarations"
_MODE_KEYFRAMES = "keyframes"

#: At-rules whose body is a list of rules (so selectors appear inside).
_RULE_LIST_AT = frozenset({
    "media", "supports", "layer", "container", "scope", "document",
})
#: At-rules whose body is a declaration block.
_DECL_AT = frozenset({
    "font-face", "page", "property", "viewport", "counter-style",
})
#: At-rules whose body is a list of keyframe blocks.
_KEYFRAMES_AT = frozenset({
    "keyframes", "-webkit-keyframes", "-moz-keyframes", "-o-keyframes",
})


def lex(source: str, filename: str = "") -> list[Token]:
    """Tokenise *source* and return tokens ending with :attr:`TokenKind.EOF`.

    Selector whitespace is emitted as a descendant combinator only when it
    separates two selector components. Whitespace in declarations is kept
    inside a single ``VALUE`` token and never affects selector parsing.
    """
    del filename  # reserved for future richer lexer diagnostics
    if not isinstance(source, str):
        raise TypeError("PSS source must be text")

    tokens: list[Token] = []
    pos = 0
    line = 1
    col = 1
    length = len(source)
    modes: list[str] = [_MODE_SELECTOR]
    pending_at: str | None = None

    def mode() -> str:
        return modes[-1]

    def consume(end: int) -> None:
        nonlocal pos, line, col
        fragment = source[pos:end]
        newline_count = fragment.count("\n")
        if newline_count:
            line += newline_count
            col = len(fragment) - fragment.rfind("\n")
        else:
            col += len(fragment)
        pos = end

    def location() -> tuple[int, int]:
        return line, col

    def skip_comment() -> None:
        start_line, start_col = location()
        end = source.find("*/", pos + 2)
        if end < 0:
            raise LexerError("Unterminated block comment", start_line, start_col)
        consume(end + 2)

    def selector_component_starts(at: int) -> bool:
        if at >= length:
            return False
        char = source[at]
        return char in ".#*:" or char.isalpha() or char == "_"

    def previous_is_selector_component() -> bool:
        return bool(tokens) and tokens[-1].kind in {
            TokenKind.TYPE_SEL,
            TokenKind.CLASS_SEL,
            TokenKind.ID_SEL,
            TokenKind.UNIVERSAL_SEL,
            TokenKind.PSEUDO,
        }

    def scan_prelude() -> str:
        """Consume an at-rule prelude up to a top-level ``{`` or ``;``."""
        start = pos
        scan = pos
        depth = 0
        quote: str | None = None
        escaped = False
        while scan < length:
            current = source[scan]
            if quote is not None:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == quote:
                    quote = None
                scan += 1
                continue
            if source.startswith("/*", scan):
                end = source.find("*/", scan + 2)
                if end < 0:
                    raise LexerError("Unterminated block comment", line, col)
                scan = end + 2
                continue
            if current in ("'", '"'):
                quote = current
                scan += 1
                continue
            if current == "(":
                depth += 1
                scan += 1
                continue
            if current == ")":
                if depth:
                    depth -= 1
                scan += 1
                continue
            if depth == 0 and current in "{;":
                break
            scan += 1
        raw = source[start:scan]
        consume(scan)
        return _strip_value_comments(raw).strip()

    def scan_pseudo() -> None:
        """Consume ``:name`` / ``::name`` (with optional ``(args)``)."""
        start_line, start_col = location()
        prefix = ":"
        consume(pos + 1)
        if pos < length and source[pos] == ":":
            prefix = "::"
            consume(pos + 1)
        match = _IDENTIFIER.match(source, pos)
        if not match:
            raise LexerError(
                f"Expected an identifier after {prefix!r}", start_line, start_col)
        name = prefix + match.group(0)
        consume(match.end())
        if pos < length and source[pos] == "(":
            depth = 0
            scan = pos
            while scan < length:
                char = source[scan]
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        scan += 1
                        break
                scan += 1
            name += source[pos:scan]
            consume(scan)
        tokens.append(Token(TokenKind.PSEUDO, name, start_line, start_col))

    def scan_declaration_value() -> None:
        """Consume a declaration value up to a top-level ``;`` or ``}``."""
        while pos < length and source[pos].isspace():
            consume(pos + 1)
        value_line, value_col = location()
        value_start = pos
        scan = pos
        stack: list[str] = []
        quote: str | None = None
        escaped = False
        matching = {"(": ")", "[": "]", "{": "}"}
        while scan < length:
            current = source[scan]
            if quote is not None:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == quote:
                    quote = None
                scan += 1
                continue
            if source.startswith("/*", scan):
                end = source.find("*/", scan + 2)
                if end < 0:
                    raise LexerError("Unterminated block comment", line, col)
                scan = end + 2
                continue
            if current in ("'", '"'):
                quote = current
                scan += 1
                continue
            if current in matching:
                stack.append(matching[current])
                scan += 1
                continue
            if current in ")]}" and stack and current == stack[-1]:
                stack.pop()
                scan += 1
                continue
            if not stack and current in ";}":
                break
            scan += 1

        raw = source[value_start:scan]
        value = _strip_value_comments(raw).strip()
        tokens.append(Token(TokenKind.VALUE, value, value_line, value_col))
        consume(scan)

    while pos < length:
        char = source[pos]

        if source.startswith("/*", pos):
            skip_comment()
            continue

        if char.isspace():
            start = pos
            while pos < length and source[pos].isspace():
                pos += 1
            end = pos
            # Restore the position tracker through the shared advance helper.
            pos = start
            if mode() == _MODE_SELECTOR and previous_is_selector_component():
                if selector_component_starts(end):
                    tokens.append(Token(TokenKind.COMBINATOR, " ", line, col))
            consume(end)
            continue

        start_line, start_col = location()

        # ── Declaration block ────────────────────────────────────────────
        if mode() == _MODE_DECLS:
            if char == "}":
                tokens.append(Token(TokenKind.RBRACE, char, start_line, start_col))
                consume(pos + 1)
                if len(modes) > 1:
                    modes.pop()
                continue
            if char == ";":
                tokens.append(Token(TokenKind.SEMI, char, start_line, start_col))
                consume(pos + 1)
                continue
            if char == ":":
                tokens.append(Token(TokenKind.COLON, char, start_line, start_col))
                consume(pos + 1)
                scan_declaration_value()
                continue

            custom = _CUSTOM_PROPERTY.match(source, pos)
            if custom:
                tokens.append(Token(
                    TokenKind.PROP, custom.group(0), start_line, start_col))
                consume(custom.end())
                continue
            vendor = _VENDOR_PROPERTY.match(source, pos)
            if vendor:
                tokens.append(Token(
                    TokenKind.PROP, vendor.group(0), start_line, start_col))
                consume(vendor.end())
                continue
            match = _IDENTIFIER.match(source, pos)
            if match:
                tokens.append(Token(
                    TokenKind.PROP, match.group(0), start_line, start_col))
                consume(match.end())
                continue

            raise LexerError(f"Unexpected character {char!r}", start_line, start_col)

        # ── Keyframe block ───────────────────────────────────────────────
        if mode() == _MODE_KEYFRAMES:
            if char == "{":
                tokens.append(Token(TokenKind.LBRACE, char, start_line, start_col))
                consume(pos + 1)
                modes.append(_MODE_DECLS)
                continue
            if char == "}":
                tokens.append(Token(TokenKind.RBRACE, char, start_line, start_col))
                consume(pos + 1)
                if len(modes) > 1:
                    modes.pop()
                continue
            if char == ",":
                tokens.append(Token(TokenKind.COMBINATOR, char, start_line, start_col))
                consume(pos + 1)
                continue
            match = _IDENTIFIER.match(source, pos)
            if match and match.group(0).lower() in ("from", "to"):
                tokens.append(Token(
                    TokenKind.KEYFRAME_SEL, match.group(0).lower(),
                    start_line, start_col))
                consume(match.end())
                continue
            match = _NUMBER.match(source, pos)
            if match and match.end() < length and source[match.end()] == "%":
                tokens.append(Token(
                    TokenKind.KEYFRAME_SEL, match.group(0) + "%",
                    start_line, start_col))
                consume(match.end() + 1)
                continue
            raise LexerError(
                f"Expected a keyframe selector, got {char!r}",
                start_line, start_col)

        # ── Selector / at-rule header ────────────────────────────────────
        if char == "@":
            consume(pos + 1)
            match = _AT_NAME.match(source, pos)
            if not match:
                raise LexerError(
                    "Expected an at-rule name after '@'", start_line, start_col)
            name = match.group(0)
            tokens.append(Token(TokenKind.AT, name, start_line, start_col))
            consume(match.end())
            while pos < length and source[pos].isspace():
                consume(pos + 1)
            if pos < length and source[pos] in "{;":
                if source[pos] == "{":
                    pending_at = name
                continue
            prelude = scan_prelude()
            tokens.append(Token(TokenKind.PRELUDE, prelude, start_line, start_col))
            pending_at = name
            continue
        if char == "{":
            tokens.append(Token(TokenKind.LBRACE, char, start_line, start_col))
            consume(pos + 1)
            if pending_at is not None:
                name = pending_at.lower()
                pending_at = None
                if name in _KEYFRAMES_AT:
                    modes.append(_MODE_KEYFRAMES)
                elif name in _DECL_AT:
                    modes.append(_MODE_DECLS)
                else:
                    modes.append(_MODE_SELECTOR)
            else:
                modes.append(_MODE_DECLS)
            continue
        if char == "}":
            tokens.append(Token(TokenKind.RBRACE, char, start_line, start_col))
            consume(pos + 1)
            if len(modes) > 1:
                modes.pop()
            continue
        if char == ";":
            tokens.append(Token(TokenKind.SEMI, char, start_line, start_col))
            consume(pos + 1)
            pending_at = None
            continue
        if char in ">,":
            tokens.append(Token(TokenKind.COMBINATOR, char, start_line, start_col))
            consume(pos + 1)
            continue
        if char == "*":
            tokens.append(Token(TokenKind.UNIVERSAL_SEL, char, start_line, start_col))
            consume(pos + 1)
            continue
        if char == ":":
            scan_pseudo()
            continue
        if char in ".#":
            match = _IDENTIFIER.match(source, pos + 1)
            if not match:
                raise LexerError(
                    f"Expected an identifier after {char!r}", start_line, start_col)
            kind = TokenKind.CLASS_SEL if char == "." else TokenKind.ID_SEL
            tokens.append(Token(kind, match.group(0), start_line, start_col))
            consume(match.end())
            continue
        match = _TYPE_IDENTIFIER.match(source, pos)
        if match:
            tokens.append(Token(TokenKind.TYPE_SEL, match.group(0), start_line, start_col))
            consume(match.end())
            continue

        raise LexerError(f"Unexpected character {char!r}", start_line, start_col)

    tokens.append(Token(TokenKind.EOF, "", line, col))
    return tokens


def _strip_value_comments(value: str) -> str:
    """Remove block comments from a value without touching quoted text."""
    out: list[str] = []
    pos = 0
    quote: str | None = None
    escaped = False
    while pos < len(value):
        char = value[pos]
        if quote is not None:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            pos += 1
            continue
        if char in ("'", '"'):
            quote = char
            out.append(char)
            pos += 1
            continue
        if value.startswith("/*", pos):
            end = value.find("*/", pos + 2)
            if end < 0:
                # The main scanner diagnoses unterminated comments. This
                # fallback keeps the helper total for direct use in tests.
                break
            out.append(" ")
            pos = end + 2
            continue
        out.append(char)
        pos += 1
    return "".join(out)
