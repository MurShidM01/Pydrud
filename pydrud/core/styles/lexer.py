"""Lexer for PSS (Pydrud Style Sheets).

PSS uses CSS-like selectors and declarations, but declaration values are
captured as complete source fragments. This keeps colours, units, strings,
functions, lists, and object-valued styles intact for the parser instead of
mistaking value punctuation (notably ``#`` in a colour) for selector syntax.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    TYPE_SEL = auto()
    CLASS_SEL = auto()
    ID_SEL = auto()
    COMBINATOR = auto()
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
_TYPE_IDENTIFIER = re.compile(r"[A-Z][A-Za-z0-9_]*")


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
    in_declarations = False

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
        nonlocal pos
        start_line, start_col = location()
        end = source.find("*/", pos + 2)
        if end < 0:
            raise LexerError("Unterminated block comment", start_line, start_col)
        consume(end + 2)

    def selector_component_starts(at: int) -> bool:
        if at >= length:
            return False
        char = source[at]
        return char in ".#" or char.isalpha() or char == "_"

    def previous_is_selector_component() -> bool:
        return bool(tokens) and tokens[-1].kind in {
            TokenKind.TYPE_SEL,
            TokenKind.CLASS_SEL,
            TokenKind.ID_SEL,
        }

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
            if not in_declarations and previous_is_selector_component():
                if selector_component_starts(end):
                    tokens.append(Token(TokenKind.COMBINATOR, " ", line, col))
            consume(end)
            continue

        start_line, start_col = location()

        if in_declarations:
            if char == "}":
                tokens.append(Token(TokenKind.RBRACE, char, start_line, start_col))
                consume(pos + 1)
                in_declarations = False
                continue
            if char == ";":
                tokens.append(Token(TokenKind.SEMI, char, start_line, start_col))
                consume(pos + 1)
                continue
            if char == ":":
                tokens.append(Token(TokenKind.COLON, char, start_line, start_col))
                consume(pos + 1)

                # A declaration value runs up to a top-level semicolon or
                # closing rule brace. Quoted strings and nested structures
                # may contain either delimiter.
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
                continue

            match = _IDENTIFIER.match(source, pos)
            if match:
                value = match.group(0)
                tokens.append(Token(TokenKind.PROP, value, start_line, start_col))
                consume(match.end())
                continue

            raise LexerError(f"Unexpected character {char!r}", start_line, start_col)

        # Selector/rule-header mode.
        if char == "{":
            tokens.append(Token(TokenKind.LBRACE, char, start_line, start_col))
            consume(pos + 1)
            in_declarations = True
            continue
        if char == "}":
            tokens.append(Token(TokenKind.RBRACE, char, start_line, start_col))
            consume(pos + 1)
            continue
        if char in ">,":
            tokens.append(Token(TokenKind.COMBINATOR, char, start_line, start_col))
            consume(pos + 1)
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
