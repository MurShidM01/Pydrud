"""
Terminal UI (TUI) components and formatting for Pydrud CLI.

Provides a clean, modern, and attractive Flutter-like interactive experience:
  • Header banners with rounded Unicode borders
  • Hot reload & hot restart badges with elapsed timings
  • Syntax error & runtime exception cards with syntax highlighting
  • Key command bars & help overlays
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from typing import Optional

# ── Color Palette ────────────────────────────────────────────────────────────

def _s(code: str) -> str:
    return f"\033[{code}m"

RESET       = _s("0")
BOLD        = _s("1")
DIM         = _s("2")
ITALIC      = _s("3")
UNDERLINE   = _s("4")

# Standard ANSI
RED         = _s("31")
GREEN       = _s("32")
YELLOW      = _s("33")
BLUE        = _s("34")
MAGENTA     = _s("35")
CYAN        = _s("36")
WHITE       = _s("37")
GRAY        = _s("90")

# 256-Color Vibrant Palette
C_PRIMARY   = "\033[38;5;39m"    # Sky Blue
C_SUCCESS   = "\033[38;5;78m"    # Emerald Green
C_WARN      = "\033[38;5;214m"   # Amber / Orange
C_ERROR     = "\033[38;5;203m"   # Coral Red
C_PURPLE    = "\033[38;5;141m"   # Soft Purple
C_CYAN      = "\033[38;5;51m"    # Electric Cyan
C_MUTED     = "\033[38;5;244m"   # Slate Gray
C_BORDER    = "\033[38;5;240m"   # Dark Slate Border
C_BG_ERR    = "\033[48;5;52m"    # Deep Red BG


def _term_width() -> int:
    try:
        return min(shutil.get_terminal_size((80, 24)).columns, 90)
    except Exception:
        return 80


# ── Status Badges ────────────────────────────────────────────────────────────

def ok_badge(text: str) -> str:
    return f"  {C_SUCCESS}✓{RESET} {text}"

def info_badge(text: str) -> str:
    return f"  {C_PRIMARY}ℹ{RESET} {text}"

def warn_badge(text: str) -> str:
    return f"  {C_WARN}▲{RESET} {text}"

def error_badge(text: str) -> str:
    return f"  {C_ERROR}✗{RESET} {text}"

def step_badge(step: str, status: str = "...") -> str:
    return f"  {C_PRIMARY}➜{RESET} {BOLD}{step:<38}{RESET} {C_MUTED}{status}{RESET}"


# ── Hot Reload & Hot Restart Badges ──────────────────────────────────────────

def hot_reload_success(duration_ms: float, reloaded: list[str] | str, states_kept: int = 0) -> str:
    """Format an attractive Hot Reload success message."""
    dur_str = f"{duration_ms:.0f}ms" if duration_ms >= 10 else f"{duration_ms:.1f}ms"
    if isinstance(reloaded, list):
        if len(reloaded) == 1:
            files_str = reloaded[0]
        elif len(reloaded) > 1:
            files_str = f"{len(reloaded)} modules ({', '.join(reloaded[:2])}{'…' if len(reloaded) > 2 else ''})"
        else:
            files_str = "code synced"
    else:
        files_str = str(reloaded)

    kept_str = f" • {C_MUTED}kept {states_kept} state(s){RESET}" if states_kept > 0 else ""
    return (
        f"\n  {C_WARN}⚡{RESET} {BOLD}{C_WARN}Hot reload{RESET} {BOLD}completed in {C_CYAN}{dur_str}{RESET} "
        f"{C_MUTED}({files_str}){RESET}{kept_str}\n"
    )

def hot_restart_success(duration_ms: float) -> str:
    """Format an attractive Hot Restart success message."""
    dur_str = f"{duration_ms:.0f}ms" if duration_ms >= 10 else f"{duration_ms:.1f}ms"
    return (
        f"\n  {C_PURPLE}🔄{RESET} {BOLD}{C_PURPLE}Hot restart{RESET} {BOLD}completed in {C_CYAN}{dur_str}{RESET} "
        f"{C_MUTED}(state reset & restarted){RESET}\n"
    )


# ── Header Banner ────────────────────────────────────────────────────────────

def render_header_banner(
    app_name: str,
    package_name: str,
    device_name: str,
    python_version: str = "3.11",
) -> str:
    """Render the startup banner with rounded box border."""
    width = _term_width()
    inner = width - 4

    title = f" ⚡ Pydrud Native Runner  (Python {python_version}) "
    details = f" App: {BOLD}{package_name or app_name}{RESET}  •  Device: {C_CYAN}{device_name or 'android'}{RESET}"

    # Build top border
    bar_len = inner - len(title)
    if bar_len < 0:
        bar_len = 2
    top = f"  {C_PRIMARY}╭─{RESET}{BOLD}{C_PRIMARY}{title}{RESET}{C_PRIMARY}{'─' * (inner - len(title) - 2)}╮{RESET}"
    line1 = f"  {C_PRIMARY}│{RESET}  {details}{' ' * max(0, inner - len(package_name or app_name) - len(device_name or 'android') - 26)}{C_PRIMARY}│{RESET}"
    bottom = f"  {C_PRIMARY}╰{'─' * inner}╯{RESET}"

    return f"\n{top}\n{line1}\n{bottom}\n"


# ── Interactive Key Commands Bar ─────────────────────────────────────────────

def render_shortcuts_bar() -> str:
    """Render the compact keyboard shortcuts hint bar."""
    return (
        f"  {C_MUTED}Key commands:{RESET} "
        f"{BOLD}[r]{RESET} {C_WARN}Hot reload{RESET}  •  "
        f"{BOLD}[R]{RESET} {C_PURPLE}Hot restart{RESET}  •  "
        f"{BOLD}[t]{RESET} Tree  •  "
        f"{BOLD}[c]{RESET} Clear  •  "
        f"{BOLD}[h]{RESET} Help  •  "
        f"{BOLD}[q]{RESET} Quit"
    )

def render_help_box() -> str:
    """Render the full interactive commands help overlay."""
    lines = [
        f"  {C_PRIMARY}╭── Flutter-style Interactive Key Commands ────────────────────────╮{RESET}",
        f"  {C_PRIMARY}│{RESET}  {BOLD}r{RESET}           Hot reload (sync Python changes, update UI, keep state)  {C_PRIMARY}│{RESET}",
        f"  {C_PRIMARY}│{RESET}  {BOLD}R{RESET} (Shift+r)  Hot restart (reset app state & re-render from start)     {C_PRIMARY}│{RESET}",
        f"  {C_PRIMARY}│{RESET}  {BOLD}t{RESET} or {BOLD}p{RESET}      Dump widget tree to terminal                             {C_PRIMARY}│{RESET}",
        f"  {C_PRIMARY}│{RESET}  {BOLD}c{RESET}           Clear the terminal screen                                {C_PRIMARY}│{RESET}",
        f"  {C_PRIMARY}│{RESET}  {BOLD}h{RESET} or {BOLD}?{RESET}      Show this list of interactive commands                   {C_PRIMARY}│{RESET}",
        f"  {C_PRIMARY}│{RESET}  {BOLD}d{RESET}           Detach (exit terminal runner, keep app on device)        {C_PRIMARY}│{RESET}",
        f"  {C_PRIMARY}│{RESET}  {BOLD}q{RESET}           Quit (terminate app on device and exit)                  {C_PRIMARY}│{RESET}",
        f"  {C_PRIMARY}╰───────────────────────────────────────────────────────────────────╯{RESET}",
    ]
    return "\n" + "\n".join(lines) + "\n"


# ── Error Boxes ──────────────────────────────────────────────────────────────

def render_error_box(
    title: str,
    message: str,
    traceback_str: Optional[str] = None,
    filename: Optional[str] = None,
    lineno: Optional[int] = None,
) -> str:
    """Render a prominent, clean error card in the terminal TUI."""
    width = _term_width()
    inner = width - 4

    header_text = f" ❌ {title} "
    top = f"  {C_ERROR}╭──{RESET}{BOLD}{C_ERROR}{header_text}{RESET}{C_ERROR}{'─' * max(2, inner - len(header_text) - 2)}╮{RESET}"
    bottom = f"  {C_ERROR}╰{'─' * inner}╯{RESET}"

    out_lines = [f"\n{top}"]

    if filename:
        loc = f"File \"{filename}\"" + (f", line {lineno}" if lineno else "")
        out_lines.append(f"  {C_ERROR}│{RESET}  {C_WARN}{loc}{RESET}")

    if traceback_str:
        # Format traceback nicely
        tb_lines = traceback_str.strip().splitlines()
        for tb_line in tb_lines:
            # Highlight traceback location lines
            if tb_line.strip().startswith("File "):
                out_lines.append(f"  {C_ERROR}│{RESET}  {C_MUTED}{tb_line.strip()}{RESET}")
            elif tb_line.strip().startswith("Traceback"):
                continue
            else:
                out_lines.append(f"  {C_ERROR}│{RESET}    {BOLD}{tb_line.strip()}{RESET}")
    elif message:
        for m_line in message.strip().splitlines():
            out_lines.append(f"  {C_ERROR}│{RESET}  {BOLD}{m_line}{RESET}")

    out_lines.append(bottom + "\n")
    return "\n".join(out_lines)


def render_syntax_error_box(
    filename: str,
    lineno: int,
    offset: int,
    text: str,
    message: str,
) -> str:
    """Render a syntax error card for failed hot reload attempts."""
    width = _term_width()
    inner = width - 4

    header_text = " ⚠️ Hot Reload Syntax Error "
    top = f"  {C_WARN}╭──{RESET}{BOLD}{C_WARN}{header_text}{RESET}{C_WARN}{'─' * max(2, inner - len(header_text) - 2)}╮{RESET}"
    bottom = f"  {C_WARN}╰{'─' * inner}╯{RESET}"

    out_lines = [
        f"\n{top}",
        f"  {C_WARN}│{RESET}  {BOLD}File \"{filename}\", line {lineno}{RESET}",
    ]

    if text:
        out_lines.append(f"  {C_WARN}│{RESET}    {text.strip()}")
        caret_pos = max(1, offset or 1) - 1
        out_lines.append(f"  {C_WARN}│{RESET}    {C_ERROR}{' ' * caret_pos}^{RESET}")

    out_lines.append(f"  {C_WARN}│{RESET}  {BOLD}{C_ERROR}SyntaxError: {message}{RESET}")
    out_lines.append(f"  {C_WARN}│{RESET}  {C_MUTED}(Hot reload skipped — running app state kept intact){RESET}")
    out_lines.append(bottom + "\n")

    return "\n".join(out_lines)


def render_log_divider() -> str:
    """Render divider above live logs."""
    width = _term_width()
    inner = width - 4
    title = " Live Output & Logs "
    bar = inner - len(title) - 2
    left = bar // 2
    right = bar - left
    return f"  {C_BORDER}{'─' * left}{RESET}{C_MUTED}{title}{RESET}{C_BORDER}{'─' * right}{RESET}\n"


def clear_screen() -> None:
    """Clear terminal screen and move cursor to top."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
