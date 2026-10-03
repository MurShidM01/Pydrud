"""
Terminal UI (TUI) components and formatting for Pydrud CLI.

Provides one clean visual language for every Pydrud command:
  • Responsive command banners, sections, tables and completion summaries
  • Consistent success, information, warning and error states
  • Hot reload & hot restart badges with elapsed timings
  • Syntax/runtime error cards, key command bars and help overlays
  • Automatic colour fallback for redirected output and NO_COLOR terminals
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import textwrap
from typing import Iterable, Optional, Sequence

# ── Color Palette ────────────────────────────────────────────────────────────

def _supports_color() -> bool:
    forced = os.environ.get("PYDRUD_COLOR", "").strip().lower()
    if forced in {"1", "true", "yes", "always"}:
        return True
    if forced in {"0", "false", "no", "never"}:
        return False
    if "NO_COLOR" in os.environ or os.environ.get("TERM") == "dumb":
        return False
    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


_COLOR_ENABLED = _supports_color()


def _s(code: str) -> str:
    return f"\033[{code}m" if _COLOR_ENABLED else ""

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
C_PRIMARY   = _s("38;5;39")     # Sky Blue
C_SUCCESS   = _s("38;5;78")     # Emerald Green
C_WARN      = _s("38;5;214")    # Amber / Orange
C_ERROR     = _s("38;5;203")    # Coral Red
C_PURPLE    = _s("38;5;141")    # Soft Purple
C_CYAN      = _s("38;5;51")     # Electric Cyan
C_MUTED     = _s("38;5;244")    # Slate Gray
C_BORDER    = _s("38;5;240")    # Dark Slate Border
C_BG_ERR    = _s("48;5;52")     # Deep Red BG


# ── Status Glyphs ────────────────────────────────────────────────────────────
# One deliberately professional, monochrome symbol set. These are plain
# text glyphs (never emoji), so every terminal renders them in the ANSI
# colour we choose instead of as coloured emoji artwork.
GLYPH_OK      = "✓"    # success
GLYPH_FAIL    = "✗"    # error / failure
GLYPH_INFO    = "i"    # information
GLYPH_WARN    = "▲"    # warning
GLYPH_NEUTRAL = "•"    # neutral note
GLYPH_STEP    = "→"    # step / progress
GLYPH_RELOAD  = "↻"    # hot reload
GLYPH_RESTART = "↺"    # hot restart


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _term_width() -> int:
    """Usable width shared by one-shot commands and the live runner."""
    try:
        return max(52, min(shutil.get_terminal_size((80, 24)).columns, 100))
    except Exception:
        return 80


def _visible_len(text: object) -> int:
    return len(_ANSI_RE.sub("", str(text)))


def strip_ansi(text: str) -> str:
    """Strip terminal colour codes (useful for logs, snapshots and tests)."""
    return _ANSI_RE.sub("", text)


def _clip(text: object, width: int) -> str:
    """Clip plain or coloured text while keeping the common case fast."""
    value = str(text)
    if _visible_len(value) <= width:
        return value
    # Table/cell values are plain text. Stripping colour for a clipped value
    # avoids leaving an unterminated escape sequence in the terminal.
    plain = strip_ansi(value)
    return plain[:max(0, width - 1)] + "…"


def _box_line(text: str, inner: int, colour: str = C_PRIMARY) -> str:
    text = _clip(text, max(1, inner - 2))
    padding = " " * max(0, inner - 2 - _visible_len(text))
    return f"  {colour}│{RESET} {text}{padding} {colour}│{RESET}"


def render_brand_banner(version: str = "", tagline: str = "Native Android. Python powered.") -> str:
    """Compact brand banner used by top-level CLI help."""
    width = _term_width()
    inner = width - 4
    title = f" PYDRUD{f' {version}' if version else ''} "
    top_fill = "─" * max(2, inner - len(title) - 1)
    lines = [
        f"  {C_PRIMARY}╭─{RESET}{BOLD}{C_PRIMARY}{title}{RESET}{C_PRIMARY}{top_fill}╮{RESET}",
        _box_line(tagline, inner),
        f"  {C_PRIMARY}╰{'─' * inner}╯{RESET}",
    ]
    return "\n".join(lines) + "\n"


def render_command_header(
    command: str,
    title: str,
    *,
    subtitle: str = "",
    details: Optional[Sequence[tuple[str, object]]] = None,
    colour: str = C_PRIMARY,
) -> str:
    """Render the standard header for a one-shot Pydrud command."""
    width = _term_width()
    inner = width - 4
    label = f" PYDRUD · {command.upper()} "
    top_fill = "─" * max(2, inner - len(label) - 1)
    lines = [
        "",
        f"  {colour}╭─{RESET}{BOLD}{colour}{label}{RESET}{colour}{top_fill}╮{RESET}",
        _box_line(f"{BOLD}{title}{RESET}", inner, colour),
    ]
    if subtitle:
        for line in textwrap.wrap(subtitle, max(20, inner - 4)) or [""]:
            lines.append(_box_line(f"{C_MUTED}{line}{RESET}", inner, colour))
    if details:
        lines.append(_box_line("", inner, colour))
        for key, value in details:
            label_text = f"{C_MUTED}{key:<12}{RESET}"
            lines.append(_box_line(f"{label_text} {value}", inner, colour))
    lines.append(f"  {colour}╰{'─' * inner}╯{RESET}")
    return "\n".join(lines) + "\n"


def render_section(title: str, *, colour: str = C_PRIMARY) -> str:
    """A quiet divider for phases within a command."""
    width = _term_width() - 4
    plain = f" {title} "
    right = "─" * max(2, width - len(plain))
    return f"\n  {colour}──{RESET}{BOLD}{plain}{RESET}{C_BORDER}{right}{RESET}"


def render_key_values(items: Sequence[tuple[str, object]]) -> str:
    """Render aligned metadata without a heavy border."""
    if not items:
        return ""
    key_width = min(22, max(_visible_len(key) for key, _ in items))
    return "\n".join(
        f"  {C_MUTED}{key:<{key_width}}{RESET}  {value}" for key, value in items
    )


def render_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[object]],
    *,
    max_width: Optional[int] = None,
) -> str:
    """Render a responsive table used by devices, packages and diagnostics."""
    rows = [tuple(str(cell) for cell in row) for row in rows]
    headers = tuple(str(header) for header in headers)
    if not headers:
        return ""
    columns = len(headers)
    normalised = [row[:columns] + ("",) * max(0, columns - len(row)) for row in rows]
    widths = [len(headers[index]) for index in range(columns)]
    for row in normalised:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], _visible_len(cell))

    available = max_width or (_term_width() - 6)
    separators = 3 * (columns - 1)
    overflow = sum(widths) + separators - available
    # Descriptions and paths are normally the last column, so shrink from the
    # right while retaining useful identifiers in the first columns.
    for index in range(columns - 1, -1, -1):
        if overflow <= 0:
            break
        floor = 12 if index == columns - 1 else min(8, widths[index])
        reduction = min(overflow, max(0, widths[index] - floor))
        widths[index] -= reduction
        overflow -= reduction

    def row_text(row: Sequence[str], *, header: bool = False) -> str:
        cells = []
        for index, cell in enumerate(row):
            clipped = _clip(cell, widths[index])
            cells.append(clipped.ljust(widths[index]))
        text = "   ".join(cells).rstrip()
        return f"  {BOLD}{C_MUTED}{text}{RESET}" if header else f"  {text}"

    output = [row_text(headers, header=True)]
    output.append(f"  {C_BORDER}{'─' * min(available, sum(widths) + separators)}{RESET}")
    output.extend(row_text(row) for row in normalised)
    return "\n".join(output)


def render_summary(
    title: str,
    items: Sequence[tuple[str, object]],
    *,
    success: bool = True,
) -> str:
    """Render a compact completion card."""
    colour = C_SUCCESS if success else C_ERROR
    icon = GLYPH_OK if success else GLYPH_FAIL
    lines = [f"\n  {colour}{icon}{RESET} {BOLD}{title}{RESET}"]
    if items:
        lines.append(render_key_values(items))
    return "\n".join(lines) + "\n"


def render_next_steps(commands: Sequence[tuple[str, str] | str]) -> str:
    """Render shell commands as a consistent final action block."""
    lines = [render_section("Next steps", colour=C_PURPLE).lstrip("\n")]
    for item in commands:
        if isinstance(item, tuple):
            command, description = item
        else:
            command, description = item, ""
        suffix = f"  {C_MUTED}{description}{RESET}" if description else ""
        lines.append(f"  {C_PURPLE}${RESET} {BOLD}{command}{RESET}{suffix}")
    return "\n".join(lines) + "\n"


# ── Status Badges ────────────────────────────────────────────────────────────

def ok_badge(text: str) -> str:
    return f"  {C_SUCCESS}{GLYPH_OK}{RESET} {text}"

def info_badge(text: str) -> str:
    return f"  {C_PRIMARY}{BOLD}{GLYPH_INFO}{RESET} {text}"

def warn_badge(text: str) -> str:
    return f"  {C_WARN}{GLYPH_WARN}{RESET} {text}"

def error_badge(text: str) -> str:
    return f"  {C_ERROR}{GLYPH_FAIL}{RESET} {text}"

def neutral_badge(text: str) -> str:
    return f"  {C_MUTED}{GLYPH_NEUTRAL}{RESET} {text}"

def add_badge(text: str) -> str:
    return f"  {C_SUCCESS}[+]{RESET} {text}"

def remove_badge(text: str) -> str:
    return f"  {C_ERROR}[-]{RESET} {text}"

def step_badge(step: str, status: str = "...") -> str:
    return f"  {C_PRIMARY}{GLYPH_STEP}{RESET} {BOLD}{step:<38}{RESET} {C_MUTED}{status}{RESET}"


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
        f"\n  {C_WARN}{GLYPH_RELOAD}{RESET} {BOLD}{C_WARN}Hot reload{RESET} {BOLD}completed in {C_CYAN}{dur_str}{RESET} "
        f"{C_MUTED}({files_str}){RESET}{kept_str}\n"
    )

def hot_restart_success(duration_ms: float) -> str:
    """Format an attractive Hot Restart success message."""
    dur_str = f"{duration_ms:.0f}ms" if duration_ms >= 10 else f"{duration_ms:.1f}ms"
    return (
        f"\n  {C_PURPLE}{GLYPH_RESTART}{RESET} {BOLD}{C_PURPLE}Hot restart{RESET} {BOLD}completed in {C_CYAN}{dur_str}{RESET} "
        f"{C_MUTED}(state reset & restarted){RESET}\n"
    )


# ── Header Banner ────────────────────────────────────────────────────────────

def render_header_banner(
    app_name: str,
    package_name: str,
    device_name: str,
    python_version: str = "3.11",
) -> str:
    """Render the live runner banner using the shared command visual system."""
    return render_command_header(
        "run",
        "Pydrud Native Runner",
        subtitle="Hot reload, device logs and interactive developer tools",
        details=(
            ("App", package_name or app_name),
            ("Device", f"{C_CYAN}{device_name or 'android'}{RESET}"),
            ("Runtime", f"Python {python_version}"),
        ),
    )


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

    header_text = f" {GLYPH_FAIL} {title} "
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

    header_text = f" {GLYPH_WARN} Hot Reload Syntax Error "
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
