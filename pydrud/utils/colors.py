"""Backward-compatible CLI colour helpers backed by the shared TUI.

Older command modules import these names directly. Keeping the shim lets the
whole CLI share the same visual language as Hot Reload without forcing every
call site to know about ANSI styling.
"""

from __future__ import annotations

from pydrud.utils import tui

RESET = tui.RESET
BOLD = tui.BOLD
DIM = tui.DIM
RED = tui.RED
GREEN = tui.GREEN
YELLOW = tui.YELLOW
BLUE = tui.BLUE
MAGENTA = tui.MAGENTA
CYAN = tui.CYAN
GRAY = tui.GRAY


def ok(text: str) -> str:
    return tui.ok_badge(text)


def fail(text: str) -> str:
    return tui.error_badge(text)


def warn(text: str) -> str:
    return tui.warn_badge(text)


def info(text: str) -> str:
    return tui.info_badge(text)


def header(text: str) -> str:
    return f"{tui.BOLD}{tui.C_PRIMARY}{text}{tui.RESET}"


def print_step(step: str, status: str = "working") -> None:
    """Print a build step with the global Pydrud TUI formatting."""
    print(tui.step_badge(step, status))
