"""
Detection of the Python interpreter and ABI Chaquopy will embed.
"""

from __future__ import annotations

import os
import shutil
import sys

from pydrud.compatibility import HOST_COMPATIBILITY
from pydrud.utils.colors import info

#: CPython versions Chaquopy accepts as ``buildPython``, newest first.
BUILD_PYTHON_VERSIONS = ("3.13", "3.12", "3.11", "3.10")


#: The Python version the app itself runs on the device.
APP_PYTHON_VERSION = HOST_COMPATIBILITY.python_version


def _python_version_of(exe: str, args: list[str] | None = None) -> str:
    """Return ``"3.11"`` for an interpreter, or ``""`` when it will not run."""
    import subprocess

    try:
        probe = subprocess.run(
            [exe, *(args or []), "-c",
             "import sys; print('%d.%d' % sys.version_info[:2]); "
             "print(sys.executable)"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return ""
    if probe.returncode != 0:
        return ""
    lines = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
    return lines[0] if lines else ""


def _build_python_candidates(
        target: str = APP_PYTHON_VERSION) -> list[tuple[str, list[str]]]:
    """Interpreter commands to probe, most desirable first.

    Each entry is ``(command, extra_args)``. The app's own Python
    (``target``) always comes first so Chaquopy can pre-compile; on
    Windows the ``py`` launcher (``py -3.11``) is preferred because
    versioned ``python3.11.exe`` names rarely exist there.
    """
    preferred = [target] if target else []
    supported = preferred + [v for v in BUILD_PYTHON_VERSIONS
                             if v not in preferred]
    candidates = [(f"python{v}", []) for v in supported]
    if os.name == "nt":
        candidates = [("py", [f"-{v}"]) for v in supported] + candidates
    return candidates


def _detect_build_python(target: str = APP_PYTHON_VERSION) -> str:
    """Pick an interpreter Chaquopy can actually use for ``buildPython``.

    Chaquopy only pre-compiles the app to ``.pyc`` when ``buildPython``
    is the *same* minor version as the Python the APK ships (``target``).
    Otherwise the build prints

        Warning: Failed to compile to .pyc format: [python.exe] is not a
        valid Python 3.11 command: it is version 3.12.

    and ships plain source — the app still works, it just starts a little
    slower. ``target`` is therefore tried first, then any other supported
    version, and the user is told what happened instead of being left to
    decode Chaquopy's warning.
    """
    preferred = [target] if target else []
    supported = preferred + [v for v in BUILD_PYTHON_VERSIONS
                             if v not in preferred]
    candidates = _build_python_candidates(target)

    for command, args in candidates:
        exe = shutil.which(command)
        if not exe:
            continue
        version = _python_version_of(exe, args)
        if not version or version not in supported:
            continue
        resolved = _resolve_executable(exe, args)
        if version != target:
            print(info(
                f"buildPython: using Python {version} "
                f"(the app ships Python {target}); Pydrud will disable "
                f".pyc pre-compilation automatically. The app still runs "
                f"normally, with only a slightly slower first start. Install "
                f"Python {target} or set PYDRUD_PYTHON to enable it."))
        return resolved

    fallback = (shutil.which("python") or shutil.which("python3")
                or sys.executable)
    print(info(
        f"buildPython: no Chaquopy-compatible Python found "
        f"(need {BUILD_PYTHON_VERSIONS[-1]}-{BUILD_PYTHON_VERSIONS[0]}, "
        f"ideally {target}); using {fallback}. "
        f"Set PYDRUD_PYTHON to override."))
    return fallback.replace("\\", "/")


def _resolve_executable(exe: str, args: list[str]) -> str:
    """The real interpreter path behind ``py -3.11`` / ``python3.11``."""
    import subprocess

    try:
        probe = subprocess.run(
            [exe, *args, "-c", "import sys; print(sys.executable)"],
            capture_output=True, text=True, timeout=15,
        )
        path = probe.stdout.strip()
        if probe.returncode == 0 and path:
            return path.replace("\\", "/")
    except Exception:
        pass
    return exe.replace("\\", "/")
