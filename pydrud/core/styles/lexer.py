"""
PSS (Pydrud Style Sheet) lexer.

Converts a .pss source string into a stream of typed tokens with
line/column tracking for diagnostics. Supports CSS-like selectors,
declarations, and ``/* ... */`` comments (which are discarded).
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
    SEMI = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    line: int
    col: int


class LexerError(RuntimeError):
    """Lexical error with file/line/column context."""
    def __init__(self, message: str, line: int, col: int) -> None:
        super().__init__(message)
        self.line = line
        self.col = col


# Individual patterns compiled separately to avoid verbose regex issues
_PATTERNS = [
    ("WS",        re.compile(r'\s+')),
    ("COMMENT",   re.compile(r'/\*[^*]*\*/')),
    ("COMBINATOR", re.compile(r'[`,>]')),
    ("LBRACE",    re.compile(r'\{')),
    ("RBRACE",    re.compile(r'\}')),
    ("COLON",     re.compile(r':')),
    ("SEMI",      re.compile(r';')),
    ("ID",        re.compile(r'#[A-Za-z_][A-Za-z0-9_-]*')),
    ("CLASS",     re.compile(r'\.[A-Za-z_][A-Za-z0-9_-]*')),
    ("TYPE",      re.compile(r'[A-Z][A-Za-z0-9]*')),
    ("PROP",      re.compile(r'[A-Za-z_][A-Za-z0-9_-]*')),
    ("NUMBER",    re.compile(r'-?[0-9]+(\.[0-9]+)?')),
    ("STRING",    re.compile(r'"[^"]*"|\'[^\']*\'')),
]


def lex(source: str, filename: str = "") -> list[Token]:
    """Tokenise *source* and return a list of :class:`Token`s ending with EOF."""
    tokens: list[Token] = []
    line = 1
    col = 1
    pos = 0
    length = len(source)

    while pos < length:
        matched = False
        for name, pattern in _PATTERNS:
            m = pattern.match(source, pos)
            if m:
                consumed = m.group(0)
                delta_lines = consumed.count('\n')
                if delta_lines > 0:
                    last_nl = consumed.rfind('\n')
                    col = len(consumed) - last_nl
                else:
                    col += len(consumed)
                line += delta_lines
                pos = m.end()
                matched = True

                if name == "WS":
                    continue
                if name == "COMMENT":
                    # skip comments silently
                    continue

                if name in ("TYPE", "CLASS", "ID"):
                    value = consumed.lstrip(".#")
                    tkind = {
                        "TYPE": TokenKind.TYPE_SEL,
                        "CLASS": TokenKind.CLASS_SEL,
                        "ID": TokenKind.ID_SEL,
                    }[name]
                    tokens.append(Token(tkind, value, line, col - len(value)))
                elif name == "COMBINATOR":
                    tokens.append(Token(TokenKind.COMBINATOR, consumed, line, col))
                elif name == "NUMBER":
                    tokens.append(Token(TokenKind.PROP, consumed, line, col - len(consumed)))
                elif name in ("STRING",):
                    # Strip quotes
                    val = consumed.strip('"').strip("'")
                    tokens.append(Token(TokenKind.PROP, val, line, col - len(consumed)))
                else:
                    tkind = {
                        "LBRACE": TokenKind.LBRACE,
                        "RBRACE": TokenKind.RBRACE,
                        "COLON": TokenKind.COLON,
                        "SEMI": TokenKind.SEMI,
                        "PROP": TokenKind.PROP,
                    }[name]
                    tokens.append(Token(tkind, consumed, line, col - len(consumed)))
                break

        if not matched:
            raise LexerError(
                f"Unexpected character {source[pos]!r}", line, col
            )

    tokens.append(Token(TokenKind.EOF, "", line, col))
    return tokens
