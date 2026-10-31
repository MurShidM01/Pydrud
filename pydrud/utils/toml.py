"""Minimal, dependency-free helpers for reading Pydrud's TOML files.

Pydrud reads a few small sections out of pydrud.toml on every sync and
build. The values are user-editable and often carry a trailing comment, so
the line readers must strip comments exactly like a real parser: a hash
inside a quoted value is data, not the start of a comment.
"""

from __future__ import annotations


def strip_inline_comment(text: str) -> str:
    """Remove a trailing comment, ignoring hashes inside quotes."""
    out: list[str] = []
    quote = ""
    escaped = False
    for ch in text:
        if quote:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).strip()


def unquote(value: str) -> str:
    """Strip an inline comment and surrounding quotes from a TOML value."""
    text = strip_inline_comment(value)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    return text
