"""
Colour utilities for the CLI output.
"""

# ── ANSI helpers ─────────────────────────────────────────────────────────────

def _s(code: int) -> str:
    return f"\033[{code}m"

RESET = _s(0)
BOLD = _s(1)
DIM = _s(2)
RED = _s(31)
GREEN = _s(32)
YELLOW = _s(33)
BLUE = _s(34)
MAGENTA = _s(35)
CYAN = _s(36)
GRAY = _s(90)


def ok(text: str) -> str:
    return f"{GREEN}✔{RESET} {text}"

def fail(text: str) -> str:
    return f"{RED}✘{RESET} {text}"

def warn(text: str) -> str:
    return f"{YELLOW}⚠{RESET} {text}"

def info(text: str) -> str:
    return f"{CYAN}ℹ{RESET} {text}"

def header(text: str) -> str:
    return f"{BOLD}{text}{RESET}"


def print_step(step: str, status: str = "..."):
    """Print a build step with consistent formatting."""
    print(f"  {BLUE}→{RESET} {step:<40} {GRAY}{status}{RESET}")
